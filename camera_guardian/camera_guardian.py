#!/usr/bin/env python3
"""
Pi Camera Guardian - Web Dashboard
"""

from datetime import datetime
from pathlib import Path
from time import sleep
import threading
import time

from gpiozero import RGBLED, MotionSensor
from random import Random

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
import cv2

from flask import Flask, render_template_string, send_from_directory, request, jsonify
from flask_socketio import SocketIO, emit

# ========================= CONFIG =========================
VIDEO_DIR = Path("motion_captures")
VIDEO_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Global state
picam2 = None
motion_enabled = True          # Start in motion-detection mode
motion_event = threading.Event()  # Set while motion is actively detected

current_config = {
    "mode": "video",
    "duration": 8,
    "resolution": (1280, 720),
    "overlay": True,
    "ExposureTime": 0,
    "AnalogueGain": 1.0,
}

def broadcast_files():
    files = sorted([f.name for f in VIDEO_DIR.iterdir() if f.is_file()], reverse=True)
    socketio.emit('file_update', {'files': files})

# ========================= CAMERA =========================
def init_camera():
    global picam2
    picam2 = Picamera2()
    config = picam2.create_video_configuration(main={"size": current_config["resolution"]})
    picam2.configure(config)
    picam2.start()
    print("✅ Camera started")

def apply_camera_controls():
    controls = {}
    if current_config.get("ExposureTime", 0) > 0:
        controls["ExposureTime"] = current_config["ExposureTime"]
    if current_config.get("AnalogueGain", 1.0) != 1.0:
        controls["AnalogueGain"] = current_config["AnalogueGain"]
    if controls:
        picam2.set_controls(controls)

def add_timestamp(frame):
    if not current_config.get("overlay", True):
        return frame
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, ts, (20, frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    return frame

def record_video():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = VIDEO_DIR / f"motion_{timestamp}.mp4"
    print(f"🎥 Recording {current_config['duration']}s → {filename.name}")
    encoder = H264Encoder()
    picam2.start_recording(encoder, str(filename))
    sleep(current_config["duration"])
    picam2.stop_recording()
    print("✅ Video saved")
    broadcast_files()

def capture_photo():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = VIDEO_DIR / f"motion_{timestamp}.jpg"
    array = picam2.capture_array()
    array = add_timestamp(array)
    cv2.imwrite(str(filename), array)
    print("✅ Photo saved")
    broadcast_files()

def capture_snapshot():
    """Periodic still image saved during the no-motion idle phase."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = VIDEO_DIR / f"snapshot_{timestamp}.jpg"
    array = picam2.capture_array()
    array = add_timestamp(array)
    cv2.imwrite(str(filename), array)
    print(f"📸 Snapshot saved: {filename.name}")
    broadcast_files()

def led_loop(led, rnd):
    """Flash LED with random colours while motion_event is set."""
    while motion_event.is_set():
        led.color = (rnd.random(), rnd.random(), rnd.random())
        sleep(1.1)
    led.off()

# ========================= HTML =========================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi Camera Guardian</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        .stream-border { border: 3px solid #1f2937; border-radius: 12px; }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.25); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .fade-in { animation: fadeIn 0.25s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: none; } }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
<div class="max-w-7xl mx-auto p-6">

    <h1 class="text-3xl font-bold mb-6 text-center">🎥 Pi Camera Guardian</h1>

    <!-- Mode toggle -->
    <div class="flex justify-center gap-3 mb-5">
        <button id="motionBtn" onclick="setMode(true)"
                class="px-6 py-2.5 rounded-xl font-medium transition-all bg-blue-600 hover:bg-blue-500">
            🔍 Motion Detection
        </button>
        <button id="liveFeedBtn" onclick="setMode(false)"
                class="px-6 py-2.5 rounded-xl font-medium transition-all bg-gray-700 hover:bg-gray-600">
            📷 Live Feed
        </button>
    </div>

    <!-- Status bar -->
    <div class="flex items-center justify-center gap-3 mb-6 p-3 bg-gray-800 rounded-xl text-sm">
        <span id="statusDot" class="w-3 h-3 rounded-full bg-blue-500 shrink-0"></span>
        <span id="statusText">Motion detection active — watching for movement</span>
        <span id="savingBadge" class="hidden items-center gap-1.5 text-yellow-400 ml-2">
            <span class="spinner"></span> Saving…
        </span>
    </div>

    <!-- Stream -->
    <div class="mb-8">
        <div class="relative max-w-4xl mx-auto">
            <img id="stream" src="/stream.mjpg" alt="Live stream"
                 class="stream-border w-full block"
                 onload="streamLoaded()" onerror="streamError()">
            <div id="streamOverlay"
                 class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/60 rounded-xl">
                <span class="spinner" style="width:32px;height:32px;border-width:4px"></span>
                <p class="text-gray-300 text-sm">Connecting to camera…</p>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <!-- LEFT: motion info panel (visible in motion mode) -->
        <div id="motionPanel" class="bg-gray-800 p-6 rounded-2xl space-y-4">
            <h2 class="text-xl font-semibold">🔍 Motion Detection Status</h2>
            <div class="p-4 bg-gray-700 rounded-xl">
                <div class="flex items-center gap-3 mb-2">
                    <span id="motionLight" class="w-4 h-4 rounded-full bg-gray-500 shrink-0 transition-all duration-300"></span>
                    <span id="motionStatus" class="font-medium text-sm">Watching for movement…</span>
                </div>
                <p class="text-xs text-gray-400">A still image is saved every 30 seconds while quiet</p>
            </div>
            <div class="p-4 bg-gray-700 rounded-xl text-sm text-gray-300 space-y-1">
                <p class="font-medium mb-2">When motion is detected:</p>
                <ul class="text-xs text-gray-400 list-disc list-inside space-y-1">
                    <li>LED flashes random colours</li>
                    <li>Video clips are recorded back-to-back while movement continues</li>
                    <li>Recording and LED stop once motion ends</li>
                </ul>
            </div>
            <p class="text-xs text-gray-500">Switch to <em>Live Feed</em> to adjust camera settings.</p>
        </div>

        <!-- LEFT: live feed settings (visible in live feed mode) -->
        <div id="controlsPanel" class="hidden bg-gray-800 p-6 rounded-2xl">
            <h2 class="text-xl font-semibold mb-5">📷 Live Feed Settings</h2>
            <div class="space-y-5">

                <div>
                    <label class="block text-sm font-medium mb-0.5">Capture Format</label>
                    <p class="text-xs text-gray-400 mb-2">What is saved to disk on each capture trigger</p>
                    <select id="captureMode" onchange="updateSettings()"
                            class="w-full bg-gray-700 p-2.5 rounded-xl text-sm">
                        <option value="video">Video clip (.mp4)</option>
                        <option value="photo">Still photo (.jpg)</option>
                    </select>
                </div>

                <div>
                    <label class="block text-sm font-medium mb-0.5">
                        Clip Duration — <span id="durationValue">8</span> s
                    </label>
                    <p class="text-xs text-gray-400 mb-2">
                        How long each individual video clip lasts before a new one starts
                    </p>
                    <input type="range" id="duration" min="3" max="30" value="8"
                           oninput="document.getElementById('durationValue').textContent=this.value; scheduleUpdate()"
                           class="w-full accent-blue-500">
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-0.5">Exposure Time (μs)</label>
                        <p class="text-xs text-gray-400 mb-2">
                            0 = auto. Raise for brighter image in low light (may add motion blur)
                        </p>
                        <input type="number" id="ExposureTime" value="0" min="0" onchange="updateSettings()"
                               class="w-full bg-gray-700 p-2.5 rounded-xl text-sm">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-0.5">ISO Gain</label>
                        <p class="text-xs text-gray-400 mb-2">
                            1.0 = auto. Higher = brighter but more digital noise
                        </p>
                        <input type="number" id="AnalogueGain" value="1.0" step="0.1" min="1" onchange="updateSettings()"
                               class="w-full bg-gray-700 p-2.5 rounded-xl text-sm">
                    </div>
                </div>

                <div class="flex items-start gap-3">
                    <input type="checkbox" id="overlay" checked onchange="updateSettings()"
                           class="mt-0.5 accent-blue-500">
                    <div>
                        <label for="overlay" class="text-sm font-medium">Timestamp Overlay</label>
                        <p class="text-xs text-gray-400">Burn the current date and time into every captured frame</p>
                    </div>
                </div>

                <div id="settingsSpinner" class="hidden items-center gap-2 text-yellow-400 text-xs">
                    <span class="spinner"></span> Applying settings…
                </div>
            </div>
        </div>

        <!-- RIGHT: saved captures -->
        <div class="bg-gray-800 p-6 rounded-2xl">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">
                    📁 Saved Captures
                    <span id="fileCount" class="text-sm text-gray-400 font-normal ml-1"></span>
                </h2>
                <span id="fileSpinner" class="hidden items-center gap-1.5 text-yellow-400 text-xs">
                    <span class="spinner"></span> Updating…
                </span>
            </div>
            <div id="fileList" class="max-h-96 overflow-y-auto space-y-2 text-sm"></div>
        </div>

    </div><!-- grid -->
</div><!-- container -->

<script>
    const socket = io();
    let motionMode = true;
    let updateTimer = null;

    // ---- Socket.IO ----
    socket.on('connect', () => {
        setStatus('blue', motionMode
            ? 'Motion detection active — watching for movement'
            : 'Live feed mode — motion detection paused');
    });

    socket.on('disconnect', () => setStatus('gray', 'Reconnecting…'));

    socket.on('file_update', (data) => {
        showSpinner('fileSpinner', true);
        setTimeout(() => {
            const icons = f => f.startsWith('snapshot') ? '📸' : f.endsWith('.mp4') ? '🎥' : '🖼️';
            document.getElementById('fileList').innerHTML = data.files.map(f => `
                <a href="/download/${f}" download
                   class="fade-in flex items-center gap-2 p-2.5 bg-gray-700 hover:bg-gray-600 rounded-xl transition">
                    ${icons(f)} ${f}
                </a>`).join('');
            document.getElementById('fileCount').textContent = `(${data.files.length})`;
            showSpinner('fileSpinner', false);
        }, 250);
    });

    socket.on('motion_state', (data) => {
        const light  = document.getElementById('motionLight');
        const status = document.getElementById('motionStatus');
        if (data.active) {
            light.className  = 'w-4 h-4 rounded-full bg-red-500 shrink-0 transition-all duration-300 animate-pulse';
            status.textContent = '🔴 Motion detected — recording';
            setStatus('red', 'Motion detected — recording');
        } else {
            light.className  = 'w-4 h-4 rounded-full bg-green-500 shrink-0 transition-all duration-300';
            status.textContent = '🟢 Watching for movement…';
            setStatus('blue', 'Motion detection active — watching for movement');
        }
    });

    // ---- Mode toggle ----
    function setMode(motion) {
        motionMode = motion;
        const active   = 'px-6 py-2.5 rounded-xl font-medium transition-all bg-blue-600 hover:bg-blue-500';
        const inactive = 'px-6 py-2.5 rounded-xl font-medium transition-all bg-gray-700 hover:bg-gray-600';
        document.getElementById('motionBtn').className    = motion ? active : inactive;
        document.getElementById('liveFeedBtn').className  = motion ? inactive : active;
        document.getElementById('motionPanel').classList.toggle('hidden', !motion);
        document.getElementById('controlsPanel').classList.toggle('hidden', motion);
        setStatus(motion ? 'blue' : 'gray',
            motion ? 'Motion detection active — watching for movement'
                   : 'Live feed mode — motion detection paused');
        updateSettings();
    }

    // ---- Settings ----
    function scheduleUpdate() {
        clearTimeout(updateTimer);
        updateTimer = setTimeout(updateSettings, 400);
    }

    function updateSettings() {
        const data = {
            mode:           document.getElementById('captureMode').value,
            duration:       parseInt(document.getElementById('duration').value),
            overlay:        document.getElementById('overlay').checked,
            ExposureTime:   parseInt(document.getElementById('ExposureTime').value || 0),
            AnalogueGain:   parseFloat(document.getElementById('AnalogueGain').value || 1.0),
            motion_enabled: motionMode,
        };
        showSpinner('settingsSpinner', true);
        fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        })
        .then(r => r.json())
        .then(() => showSpinner('settingsSpinner', false))
        .catch(() => showSpinner('settingsSpinner', false));
    }

    // ---- Stream ----
    function streamLoaded() {
        document.getElementById('streamOverlay').style.display = 'none';
    }
    function streamError() {
        document.getElementById('streamOverlay').style.display = 'flex';
        setTimeout(() => {
            document.getElementById('stream').src = '/stream.mjpg?' + Date.now();
        }, 3000);
    }

    // ---- Helpers ----
    function setStatus(color, text) {
        const map = { blue: 'bg-blue-500', green: 'bg-green-500', red: 'bg-red-500 animate-pulse', gray: 'bg-gray-500', yellow: 'bg-yellow-500' };
        document.getElementById('statusDot').className  = `w-3 h-3 rounded-full shrink-0 ${map[color] || map.blue}`;
        document.getElementById('statusText').textContent = text;
    }

    function showSpinner(id, show) {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('hidden', !show);
        el.classList.toggle('flex', show);
    }

    // DOMContentLoaded fires immediately when the DOM is ready, without waiting
    // for the MJPEG stream (which never fully "loads" and would block window.onload)
    document.addEventListener('DOMContentLoaded', () => setMode(true));
</script>
</body>
</html>
"""

# ========================= ROUTES =========================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    global motion_enabled
    data = request.get_json(silent=True) or {}
    print("📥 Received settings:", data)

    current_config.update({
        "mode":         data.get("mode", "video"),
        "duration":     int(data.get("duration", 8)),
        "overlay":      bool(data.get("overlay", True)),
        "ExposureTime": int(data.get("ExposureTime", 0)),
        "AnalogueGain": float(data.get("AnalogueGain", 1.0)),
    })
    motion_enabled = bool(data.get("motion_enabled", True))

    apply_camera_controls()
    return jsonify({"status": "success", "motion_enabled": motion_enabled})

@app.route('/stream.mjpg')
def stream():
    def generate():
        while True:
            frame = picam2.capture_array()
            frame = add_timestamp(frame)
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    return app.response_class(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/download/<filename>')
def download(filename):
    # send_from_directory prevents path traversal automatically
    safe_name = Path(filename).name
    return send_from_directory(VIDEO_DIR, safe_name)

@socketio.on('connect')
def handle_connect():
    print("🔌 Client connected")
    # Use room-scoped emit() so the file list reaches the connecting client directly
    files = sorted([f.name for f in VIDEO_DIR.iterdir() if f.is_file()], reverse=True)
    emit('file_update', {'files': files})
    emit('motion_state', {'active': motion_event.is_set()})

# ========================= MAIN =========================
def main():
    global picam2
    init_camera()
    apply_camera_controls()

    pir = MotionSensor(21)
    led = RGBLED(18, 23, 24)
    rnd = Random()

    threading.Thread(
        target=lambda: socketio.run(app, host='0.0.0.0', port=5000, debug=False),
        daemon=True,
    ).start()
    print("🌐 Web UI → http://<PI_IP>:5000")

    SNAPSHOT_INTERVAL = 30  # seconds between idle snapshots
    last_snapshot = 0.0

    try:
        while True:
            if not motion_enabled:
                # Live-feed mode — just idle, clear any active motion state
                if motion_event.is_set():
                    motion_event.clear()
                    socketio.emit('motion_state', {'active': False})
                sleep(0.5)
                continue

            if pir.motion_detected:
                # --- Motion phase ---
                if not motion_event.is_set():
                    motion_event.set()
                    socketio.emit('motion_state', {'active': True})
                    print("🚨 Motion detected")
                    threading.Thread(target=led_loop, args=(led, rnd), daemon=True).start()
                    last_snapshot = time.time()  # reset idle timer

                if current_config["mode"] == "video":
                    record_video()
                else:
                    capture_photo()
                    sleep(1)

            else:
                # --- Idle phase ---
                if motion_event.is_set():
                    motion_event.clear()
                    socketio.emit('motion_state', {'active': False})
                    print("✅ Motion ended")

                now = time.time()
                if now - last_snapshot >= SNAPSHOT_INTERVAL:
                    capture_snapshot()
                    last_snapshot = now

                sleep(1)

    except KeyboardInterrupt:
        print("Shutting down…")
    finally:
        motion_event.clear()
        picam2.stop()
        led.off()

if __name__ == "__main__":
    main()
