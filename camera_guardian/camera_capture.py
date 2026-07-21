import threading
import time
import cv2
import lgpio
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, Response, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
import libcamera

# ========================= CONFIG =========================
CAPTURES_DIR = Path("captures")
CAPTURES_DIR.mkdir(exist_ok=True)

PIR_PIN = 17
MIC_PIN = 27

# ========================= STATE =========================
app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

picam2 = None
h = None  # lgpio handle

# Global state variables
current_mode = "manual"  # manual or detection
is_live_feed = False
is_recording = False
motion_event = threading.Event()
streaming_event = threading.Event()  # New event to track when we should be streaming
stop_event = threading.Event()

current_config = {
    "resolution": (1920, 1080),
    "fps": 30,
}

# ========================= CAMERA FUNCTIONS =========================
def init_camera():
    global picam2
    picam2 = Picamera2(camera_num=0)
    
    # 180 degree flip using libcamera Transform object
    # This is the most reliable way to ensure the orientation is baked into the stream
    t = libcamera.Transform()
    t.hflip = True
    t.vflip = True
    
    config = picam2.create_video_configuration(main={"size": current_config["resolution"]}, transform=t)
    picam2.configure(config)
    
    picam2.start()
    print("✅ Camera initialized and started (180° flip applied using libcamera.Transform)")

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def capture_image(is_idle=True):
    """Captures a still image and saves it to the captures folder."""
    timestamp = get_timestamp()
    prefix = "idle" if is_idle else "manual"
    filename = CAPTURES_DIR / f"{prefix}_{timestamp}.jpg"
    
    # In picamera2, capture_array is a convenient way to get a frame for OpenCV
    frame = picam2.capture_array()
    
    # Convert BGR to RGB to match the color correction used in the stream
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Add timestamp overlay
    ts_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Using (0, 0, 255) for Red to match digital stream overlay
    cv2.putText(frame, ts_text, (20, frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
    cv2.imwrite(str(filename), frame)
    print(f"📸 Image saved: {filename.name}")
    
    # Small delay to ensure filesystem metadata is updated before broadcasting
    def delayed_broadcast():
        # Force a refresh of the file list
        broadcast_files()
        
    # Using a slightly longer delay (0.5s) to ensure JPG is fully written to disk
    # and st_mtime is correctly updated by the OS
    threading.Timer(0.5, delayed_broadcast).start()
    return filename

def start_video_recording():
    global is_recording
    
    # Absolutely ensure we're in a clean state
    if is_recording:
        print("⚠️ Recording flag already set, forcing complete reset")
        try:
            picam2.stop_recording()
        except Exception as e:
            print(f"⚠️ Cleanup exception (expected if not actually recording): {e}")
        is_recording = False
        print("⏳ Waiting 1.0s for camera to stabilize after stop...")
        time.sleep(1.0)  # Increased to 1.0s - camera needs time to fully reset
    
    timestamp = get_timestamp()
    filename = CAPTURES_DIR / f"motion_{timestamp}.mp4"
    print(f"🎥 STARTING VIDEO RECORDING: {filename.name}")
    
    try:
        encoder = H264Encoder()
        picam2.start_recording(encoder, str(filename))
        is_recording = True
        print(f"✅ RECORDING ACTIVE: is_recording={is_recording}")
        # Small delay to let recording stabilize before frames are requested
        time.sleep(0.2)
    except Exception as e:
        print(f"❌ CRITICAL: Failed to start recording: {e}")
        is_recording = False
        # Emergency cleanup
        try:
            picam2.stop_recording()
        except:
            pass
    # broadcast_files()  # Removed to hide incomplete video from list

def stop_video_recording():
    global is_recording
    if not is_recording:
        print("⚠️ stop_video_recording called but not recording")
        return
    
    print(f"🛑 STOPPING VIDEO RECORDING: is_recording={is_recording}")
    try:
        picam2.stop_recording()
        print("✅ VIDEO SAVED SUCCESSFULLY")
    except Exception as e:
        print(f"❌ Error stopping recording: {e}")
    finally:
        # ALWAYS set to False to prevent stuck state
        is_recording = False
        print(f"✅ Recording flag cleared: is_recording={is_recording}")
        print("⏳ Waiting 2.0s for camera to stabilize...")
        time.sleep(2.0)  # Critical: camera needs substantial time to reset encoder state
        broadcast_files()

def broadcast_files():
    files = get_sorted_files()
    socketio.emit('file_update', {'files': files})

def broadcast_status():
    socketio.emit('status_update', {
        'mode': current_mode,
        'live_feed': is_live_feed,
        'motion': streaming_event.is_set()
    })

def get_sorted_files(extension=None):
    """Returns a list of filenames sorted by modification time (newest first)."""
    try:
        files = [f for f in CAPTURES_DIR.iterdir() if f.is_file()]
        if extension:
            files = [f for f in files if f.suffix.lower() == extension.lower()]
        
        # Sort by mtime, fallback to name if mtimes are identical
        files.sort(key=lambda x: (x.stat().st_mtime, x.name), reverse=True)
        return [f.name for f in files]
    except Exception as e:
        print(f"Error sorting files: {e}")
        return []

# ========================= SENSOR MONITORING =========================
def sensor_worker():
    global h
    h = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(h, PIR_PIN)
    lgpio.gpio_claim_input(h, MIC_PIN)
    
    last_pir, last_mic = -1, -1
    
    while not stop_event.is_set():
        pir_state = lgpio.gpio_read(h, PIR_PIN)
        mic_state = lgpio.gpio_read(h, MIC_PIN)
        
        # Broadcast raw values to UI for debugging
        if pir_state != last_pir or mic_state != last_mic:
            socketio.emit('sensor_debug', {'pir': pir_state, 'mic': mic_state})
            last_pir, last_mic = pir_state, mic_state
        
        if pir_state or mic_state:
            if not motion_event.is_set():
                motion_event.set()
                # Don't emit socket here, let controller_loop handle it with 10s logic
                print(f"🚨 Motion detected! (PIR: {pir_state}, MIC: {mic_state})")
        else:
            if motion_event.is_set():
                motion_event.clear()
        
        time.sleep(0.1)

# ========================= CONTROLLER LOOP =========================
def controller_loop():
    last_idle_capture = time.time()
    idle_interval = 30
    
    # Detection mode state tracking
    detection_active = False
    detection_started_at = None
    motion_ended_at = None
    cooldown_duration = 10
    min_detection_duration = 5  # Minimum seconds to keep detection active
    
    # Take initial startup image
    time.sleep(2)
    capture_image(is_idle=False)
    print(f"🎬 CONTROLLER LOOP STARTED (idle_interval={idle_interval}s)")
    
    while not stop_event.is_set():
        now = time.time()
        time_since_idle = now - last_idle_capture
        
        print(f"\r🔄 Loop: mode={current_mode}, live={is_live_feed}, motion={motion_event.is_set()}, recording={is_recording}, cooldown={motion_ended_at is not None}, idle_in={idle_interval-time_since_idle:.1f}s", end='', flush=True)
        
        # ========== DETECTION MODE ==========
        if current_mode == "detection":
            # Handle active motion detection
            if motion_event.is_set():
                # If in cooldown and motion resumes, cancel cooldown
                if motion_ended_at is not None:
                    print(f"\n  🚨 Motion resumed during cooldown! Canceling cooldown...")
                    motion_ended_at = None
                
                # If not yet in detection mode, start it
                if not detection_active:
                    print(f"\n🚨 MOTION DETECTED - Starting detection session (STREAM ONLY)")
                    detection_active = True
                    detection_started_at = now
                    streaming_event.set()
                    broadcast_status()
                    # NOTE: Recording disabled - H264 encoder prevents multiple start/stop cycles
                # Already in detection mode, keep it active
                else:
                    # Just keep detection_active, streaming should continue
                    pass
            
            # No motion currently
            else:
                # If detection was active, check if we can start cooldown
                if detection_active and motion_ended_at is None:
                    # Only start cooldown if minimum detection duration has passed
                    time_in_detection = now - detection_started_at if detection_started_at else 0
                    
                    if time_in_detection >= min_detection_duration:
                        print(f"\n  ⏳ Motion ended (after {time_in_detection:.1f}s), starting {cooldown_duration}s cooldown...")
                        motion_ended_at = now
                    else:
                        # Too soon - keep detection active to debounce sensor
                        remaining = min_detection_duration - time_in_detection
                        print(f"\r  ⏱️ Detection debounce: {remaining:.1f}s remaining", end='', flush=True)
                
                # If in cooldown, check if complete
                elif motion_ended_at is not None:
                    time_since_motion_ended = now - motion_ended_at
                    
                    if time_since_motion_ended >= cooldown_duration:
                        print(f"\n  ✅ Cooldown complete, ending detection session")
                        streaming_event.clear()
                        detection_active = False
                        detection_started_at = None
                        motion_ended_at = None
                        broadcast_status()
                        capture_image(is_idle=True)
                        last_idle_capture = now
                        print(f"\n🔄 Detection mode: Back to idle")
                
                # Fully idle - check for periodic capture
                elif not detection_active:
                    if time_since_idle >= idle_interval:
                        print(f"\n📸 IDLE CAPTURE (detection mode, {time_since_idle:.1f}s since last)")
                        capture_image(is_idle=True)
                        last_idle_capture = now
        
        # ========== MANUAL MODE ==========
        else:
            if is_live_feed:
                # Live feed active - just stream, don't record
                if not streaming_event.is_set():
                    print(f"\n👁️ MANUAL LIVE FEED - Starting streaming")
                    streaming_event.set()
                    broadcast_status()
                
                # Keep resetting idle timer while live
                last_idle_capture = now
            
            else:
                # Live feed not active
                if streaming_event.is_set():
                    print(f"\n  🛑 Manual feed stopped, ending streaming")
                    streaming_event.clear()
                    broadcast_status()
                    capture_image(is_idle=True)
                    last_idle_capture = time.time()
                    print(f"\n🔄 Manual mode: Back to idle")
                
                # ALWAYS check for idle capture when not live
                if time_since_idle >= idle_interval:
                    print(f"\n📸 IDLE CAPTURE (manual mode, {time_since_idle:.1f}s since last)")
                    capture_image(is_idle=True)
                    last_idle_capture = now
        
        time.sleep(0.5)

# ========================= WEB ROUTES =========================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream.mjpg')
def stream():
    def generate():
        print(f"📡 STREAM REQUEST RECEIVED (live={is_live_feed}, event={streaming_event.is_set()}, recording={is_recording})")
        
        # Wait up to 5 seconds for streaming conditions to be met
        wait_start = time.time()
        max_wait = 5.0
        
        while not (is_live_feed or streaming_event.is_set()):
            if time.time() - wait_start > max_wait:
                print(f"⏰ Stream timeout - no streaming conditions after {max_wait}s")
                return
            time.sleep(0.05)
        
        print(f"✅ STREAM STARTING - Waiting briefly for conditions to stabilize...")
        time.sleep(0.5)  # Give everything time to settle
        
        print(f"✅ STREAM ACTIVE - Starting frame delivery")
        frame_count = 0
        consecutive_errors = 0
        
        while True:
            # Only serve frames if we're supposed to be streaming
            if is_live_feed or streaming_event.is_set():
                try:
                    # Capture frame - this should work even during recording
                    frame = picam2.capture_array()
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    ts_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, ts_text, (20, frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                    frame_count += 1
                    consecutive_errors = 0  # Reset error counter on success
                    if frame_count == 1:
                        print(f"✅ First frame delivered successfully!")
                    if frame_count % 50 == 0:
                        print(f"📹 Streamed {frame_count} frames")
                except GeneratorExit:
                    print(f"📡 STREAM DISCONNECTED (after {frame_count} frames)")
                    raise
                except Exception as e:
                    consecutive_errors += 1
                    print(f"❌ Stream frame error ({consecutive_errors}): {e}")
                    if consecutive_errors > 10:
                        print(f"🛑 Too many consecutive errors, closing stream")
                        break
                    time.sleep(0.2)
                    continue
            else:
                # Conditions no longer met - close stream
                print(f"🛑 Streaming conditions ended (after {frame_count} frames)")
                break
                
            time.sleep(0.1)  # ~10 FPS
    
    response = Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/latest_capture')
def latest_capture():
    # Return the URL of the most recent still image
    try:
        # Use glob for a fresh, immediate disk scan
        files = list(CAPTURES_DIR.glob("*.jpg"))
        if not files:
            return jsonify({"url": None})
            
        # Sort by mtime (newest first). Using absolute path for stat.
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        # Ensure we return the absolute newest
        latest = files[0]
        print(f"DEBUG: Serving latest still: {latest.name} (mtime: {latest.stat().st_mtime})")
        return jsonify({"url": f"/captures/{latest.name}"})
    except Exception as e:
        print(f"Error in latest_capture: {e}")
    return jsonify({"url": None})

@app.route('/api/clear_captures', methods=['POST'])
def clear_captures():
    try:
        for f in CAPTURES_DIR.iterdir():
            if f.is_file():
                f.unlink()
        print("📁 Captures directory cleared")
        broadcast_files()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/captures/<filename>')
def download(filename):
    return send_from_directory(CAPTURES_DIR, filename)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    global current_mode, is_live_feed
    data = request.get_json() or {}
    
    if 'mode' in data:
        new_mode = data['mode']
        if new_mode != current_mode:
            # Force cleanup of recording/streaming state when switching modes
            if is_recording:
                stop_video_recording()
            streaming_event.clear()
            is_live_feed = False # Reset live feed on mode change
            current_mode = new_mode
            print(f"🔄 Mode switched to: {current_mode}")
            # Reset motion event so we don't carry over a trigger
            motion_event.clear()
            broadcast_status()
    
    if 'live_feed' in data:
        new_value = bool(data['live_feed'])
        if new_value != is_live_feed:
            is_live_feed = new_value
            print(f"🔄 Live feed set to: {is_live_feed}")
            # If turning off live feed in manual mode, ensure cleanup
            if not is_live_feed and current_mode == 'manual':
                print("🧹 Cleaning up manual live feed state")
                # Controller loop will handle stopping recording on next iteration
            broadcast_status()
        
    return jsonify({"status": "success", "mode": current_mode, "live_feed": is_live_feed})

@socketio.on('connect')
def handle_connect():
    files = get_sorted_files()
    emit('file_update', {'files': files})
    emit('status_update', {
        'mode': current_mode,
        'live_feed': is_live_feed,
        'motion': streaming_event.is_set()
    })

# ========================= UI TEMPLATE =========================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guardian Camera System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        .status-pulse { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
<div class="max-w-6xl mx-auto p-4 md:p-8">
    <header class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div>
            <h1 class="text-3xl font-black italic tracking-tighter text-blue-500">GUARDIAN <span class="text-slate-100 underline decoration-red-500">CAM</span></h1>
            <p class="text-xs text-slate-500 font-mono mt-1">LGPIO + PICAMERA2 SECURITY ENGINE</p>
        </div>
        <div class="bg-slate-800 p-1 rounded-xl border border-slate-700 flex gap-1">
            <button id="manualModeBtn" onclick="sendMode('manual')" 
                class="px-6 py-2 rounded-lg font-bold transition-all bg-blue-700 text-sm">MANUAL</button>
            <button id="detectionModeBtn" onclick="sendMode('detection')" 
                class="px-6 py-2 rounded-lg font-bold transition-all bg-slate-800 text-sm">DETECTION</button>
        </div>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <!-- Main Viewport -->
        <div class="lg:col-span-8 space-y-6">
            <div class="bg-black rounded-2xl overflow-hidden aspect-video relative ring-1 ring-slate-700 shadow-2xl group">
                <img id="mainView" src="" 
                     class="w-full h-full object-contain transition-opacity duration-300"
                     onload="this.style.opacity=1" 
                     onerror="handleImageError()">
                
                <div id="loadingOverlay" class="absolute inset-0 flex items-center justify-center bg-slate-900/50 hidden">
                    <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                </div>

                <div class="absolute top-4 left-4 flex gap-2 pointer-events-none">
                    <div id="motionBadge" class="hidden px-3 py-1 bg-red-600 text-[10px] font-black rounded-full shadow-lg border border-red-500 status-pulse">MOTION DETECTED</div>
                    <div id="recordingBadge" class="hidden px-3 py-1 bg-blue-600 text-[10px] font-black rounded-full shadow-lg border border-blue-500">REC ACTIVE</div>
                </div>
                
                <div class="absolute bottom-4 right-4 text-[10px] font-mono text-white/50 bg-black/40 px-2 py-1 rounded backdrop-blur-sm">
                    LIVE HD FEED
                </div>
            </div>

            <!-- Diagnostics -->
            <div class="bg-slate-800/50 backdrop-blur p-4 rounded-2xl border border-slate-700/50 flex flex-wrap gap-6 items-center">
                <div class="flex-1 min-w-[200px]">
                    <h2 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Hardware Sensors</h2>
                    <div class="flex gap-6">
                        <div class="flex items-center gap-3">
                            <div id="pirDot" class="w-3 h-3 rounded-full bg-slate-700 transition-colors shadow-sm"></div>
                            <div>
                                <p class="text-[10px] text-slate-500 leading-none mb-1">PIR SENSOR</p>
                                <p id="pirVal" class="text-xs font-mono font-bold">0</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-3">
                            <div id="micDot" class="w-3 h-3 rounded-full bg-slate-700 transition-colors shadow-sm"></div>
                            <div>
                                <p class="text-[10px] text-slate-500 leading-none mb-1">ACOUSTIC</p>
                                <p id="micVal" class="text-xs font-mono font-bold">0</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="w-px h-10 bg-slate-700 hidden md:block"></div>
                <div id="manualControls" class="flex-1 min-w-[240px]">
                    <button id="liveFeedBtn" onclick="toggleLiveFeed()" 
                        class="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-black text-sm tracking-tight transition-all active:scale-95 shadow-lg shadow-blue-900/20">
                        START LIVE SESSION
                    </button>
                </div>
                <div id="detectionControls" class="flex-1 hidden">
                    <div class="bg-green-500/10 text-green-500 border border-green-500/20 p-3 rounded-xl flex items-center gap-3">
                        <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                        <p class="text-xs font-bold">SYSTEM ARMED: AUTO-CAPTURE ENABLED</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Capture History -->
        <div class="lg:col-span-4 bg-slate-800/80 backdrop-blur rounded-3xl border border-slate-700 p-6 flex flex-col h-[600px] shadow-xl">
            <div class="flex justify-between items-center mb-6">
                <div>
                    <h2 class="text-xl font-black tracking-tight">STORAGE</h2>
                    <p class="text-[10px] text-slate-500 font-mono">/home/pi/captures</p>
                </div>
                <button onclick="clearCaptures()" 
                    class="text-[10px] font-bold bg-slate-700 hover:bg-red-900 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-600 transition-all">
                    WIPE DISK
                </button>
            </div>
            <div id="fileList" class="flex-1 overflow-y-auto space-y-2 custom-scrollbar">
                <!-- Entries -->
            </div>
        </div>
    </div>
</div>

<script>
    const socket = io();
    let state = {
        mode: 'manual',
        liveRequest: false,      // Manual toggle state
        serverMotionActive: false // Motion event state from server
    };

    // Helper to log with timestamps
    const log = (msg, level = 'info') => {
        const time = new Date().toLocaleTimeString();
        console[level](`[${time}] ${msg}`);
    };

    function updateUIState() {
        log(`Updating UI State: Mode=${state.mode}, LiveReq=${state.liveRequest}, Motion=${state.serverMotionActive}`);
        
        const mainView = document.getElementById('mainView');
        const manualBtn = document.getElementById('manualModeBtn');
        const detectionBtn = document.getElementById('detectionModeBtn');
        const manualCtrl = document.getElementById('manualControls');
        const detectionCtrl = document.getElementById('detectionControls');
        const liveBtn = document.getElementById('liveFeedBtn');
        const motionBadge = document.getElementById('motionBadge');
        const recBadge = document.getElementById('recordingBadge');

        // 1. Mode Buttons
        manualBtn.className = state.mode === 'manual' ? "px-6 py-2 rounded-lg font-bold bg-blue-700 text-sm" : "px-6 py-2 rounded-lg font-bold bg-slate-800 text-sm hover:bg-slate-700";
        detectionBtn.className = state.mode === 'detection' ? "px-6 py-2 rounded-lg font-bold bg-blue-700 text-sm" : "px-6 py-2 rounded-lg font-bold bg-slate-800 text-sm hover:bg-slate-700";

        // 2. Mode Panels
        manualCtrl.classList.toggle('hidden', state.mode !== 'manual');
        detectionCtrl.classList.toggle('hidden', state.mode !== 'detection');

        // 3. Conditional Badges
        motionBadge.classList.toggle('hidden', !state.serverMotionActive);
        recBadge.classList.toggle('hidden', !state.liveRequest && !state.serverMotionActive);
        
        // 4. Live Button Text
        if (state.liveRequest) {
            liveBtn.innerText = "STOP LIVE SESSION";
            liveBtn.classList.replace('bg-blue-600', 'bg-red-600');
        } else {
            liveBtn.innerText = "START LIVE SESSION";
            liveBtn.classList.replace('bg-red-600', 'bg-blue-600');
        }

        // 5. Stream Routing - Load stream when needed, clear when not
        const shouldStream = state.liveRequest || state.serverMotionActive;
        const currentSrc = mainView.src;
        const isShowingStream = currentSrc.includes('stream.mjpg');
        
        if (shouldStream) {
            if (!isShowingStream) {
                log("Loading NEW stream");
                // Clear first, then load stream with unique timestamp
                mainView.src = "";
                setTimeout(() => {
                    mainView.src = `/stream.mjpg?t=${Date.now()}`;
                }, 100);
            } else {
                // Already showing stream, keep it
                log("Stream already active");
            }
        } else {
            if (isShowingStream || currentSrc === "") {
                log("Stopping stream, loading still");
                mainView.src = "";
                setTimeout(fetchLatestStill, 500);
            }
        }
    }

    function fetchLatestStill() {
        if (state.liveRequest || state.serverMotionActive) return;
        
        log("Fetching latest still...");
        fetch('/latest_capture')
            .then(r => r.json())
            .then(data => {
                if (data.url && !state.liveRequest && !state.serverMotionActive) {
                    const mainView = document.getElementById('mainView');
                    mainView.src = data.url + '?t=' + Date.now();
                }
            })
            .catch(err => log("Fetch error: " + err, 'error'));
    }

    // Socket Event Handlers - SIMPLIFIED
    socket.on('status_update', (data) => {
        log(`Status: mode=${data.mode}, live=${data.live_feed}, motion=${data.motion}`);
        state.mode = data.mode;
        state.liveRequest = data.live_feed;
        state.serverMotionActive = data.motion;
        updateUIState();
    });

    socket.on('motion_state', (data) => {
        log("Motion state received: " + data.active);
        state.serverMotionActive = data.active;
        updateUIState();
    });

    socket.on('file_update', (data) => {
        const list = document.getElementById('fileList');
        if (!data.files || data.files.length === 0) {
            list.innerHTML = '<div class="text-slate-600 text-[10px] italic p-4 text-center">Empty directory</div>';
            return;
        }

        list.innerHTML = data.files.map(f => {
            const isVideo = f.endsWith('.mp4');
            const icon = isVideo ? '🎬' : '📸';
            return `
                <div class="bg-slate-700/50 p-3 rounded-xl flex justify-between items-center group/item hover:bg-slate-700 border border-slate-600/30 transition-all">
                    <div class="flex items-center gap-3 truncate">
                        <span class="text-lg">${icon}</span>
                        <div class="truncate">
                            <p class="text-[11px] font-bold text-slate-200 truncate">${f}</p>
                            <p class="text-[9px] text-slate-500 font-mono italic">CAPTURE_LOG</p>
                        </div>
                    </div>
                    <a href="/captures/${f}" download class="opacity-0 group-hover/item:opacity-100 p-2 hover:bg-blue-600 rounded-lg transition-all text-xs">⬇️</a>
                </div>
            `;
        }).join('');
        
        // If not streaming, update view to the absolute newest jpg
        if (!state.liveRequest && !state.serverMotionActive) {
            const latestJpg = data.files.find(f => f.toLowerCase().endsWith('.jpg'));
            if (latestJpg) {
                const mainView = document.getElementById('mainView');
                mainView.src = `/captures/${latestJpg}?t=${Date.now()}`;
            }
        }
    });

    socket.on('sensor_debug', (data) => {
        document.getElementById('pirVal').textContent = data.pir;
        document.getElementById('micVal').textContent = data.mic;
        document.getElementById('pirDot').className = data.pir ? 'w-3 h-3 rounded-full bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'w-3 h-3 rounded-full bg-slate-700';
        document.getElementById('micDot').className = data.mic ? 'w-3 h-3 rounded-full bg-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.5)]' : 'w-3 h-3 rounded-full bg-slate-700';
    });

    // Control Functions
    function sendMode(newMode) {
        log(`Change mode to: ${newMode}`);
        
        fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mode: newMode})
        });
        
        // Optimistic update
        state.mode = newMode;
        if (newMode === 'detection') state.liveRequest = false;
        updateUIState();
    }

    function toggleLiveFeed() {
        const newState = !state.liveRequest;
        log(`Toggle live feed: ${newState}`);
        
        fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({live_feed: newState})
        });
        
        // Optimistic update
        state.liveRequest = newState;
        updateUIState();
    }

    function handleImageError() {
        const mainView = document.getElementById('mainView');
        // Prevent infinite loop if still image fails
        if (mainView.src.includes('stream.mjpg')) {
            log("Stream tag failed, retrying...", "error");
            setTimeout(updateUIState, 1000);
        }
    }

    function clearCaptures() {
        if (!confirm("Permanently wipe all captures from disk?")) return;
        fetch('/api/clear_captures', { method: 'POST' })
            .then(() => {
                document.getElementById('mainView').src = '';
                log("Disk wiped");
            });
    }

    document.addEventListener('DOMContentLoaded', () => {
        log("UI Initialized");
        // Initial state depends on status_update which server sends on connect
    });
</script>
</body>
</html>
"""

# ========================= MAIN =========================
def main():
    init_camera()
    
    # Start threads
    threading.Thread(target=sensor_worker, daemon=True).start()
    threading.Thread(target=controller_loop, daemon=True).start()
    
    print("🌐 Web UI → http://0.0.0.0:5000")
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_event.set()
        if h is not None:
            lgpio.gpiochip_close(h)
        if picam2 is not None:
            picam2.stop()

if __name__ == "__main__":
    main()
