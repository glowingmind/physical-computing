#!/usr/bin/env python3
"""
Pi Camera Feed  —  v1
Simple web viewer: still on load, one button to toggle live feed on/off.
LED cycles random colours while live feed is active. No file saving.
"""

import threading
from random import Random
from time import sleep

import cv2
from flask import Flask, Response, render_template_string
from flask_socketio import SocketIO, emit
from gpiozero import RGBLED
from picamera2 import Picamera2

# ========================= APP =========================
app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# ========================= STATE =========================
picam2: Picamera2 | None = None
led:    RGBLED     | None = None
rnd = Random()

_live_feed   = threading.Event()   # set  → live feed ON;  clear → live feed OFF
_led_stop    = threading.Event()   # set  → LED worker should exit
_stream_gen  = 0                    # incremented each time the feed is turned on

# ========================= CAMERA =========================
def init_camera() -> None:
    global picam2
    picam2 = Picamera2()
    config = picam2.create_video_configuration(main={"size": (1280, 720)})
    picam2.configure(config)
    picam2.start()
    print("✅ Camera started")

def capture_jpeg(quality: int = 85) -> bytes:
    frame = picam2.capture_array()
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()

# ========================= LED =========================
def _led_worker() -> None:
    """Cycle random colours until _led_stop is set."""
    while not _led_stop.wait(0):          # non-blocking check
        led.color = (rnd.random(), rnd.random(), rnd.random())
        _led_stop.wait(1.1)               # interruptible sleep
    led.off()

def start_led() -> None:
    _led_stop.clear()
    threading.Thread(target=_led_worker, daemon=True).start()

def stop_led() -> None:
    _led_stop.set()

# ========================= ROUTES =========================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/still')
def still():
    return Response(capture_jpeg(), mimetype='image/jpeg')

@app.route('/stream.mjpg')
def stream():
    my_gen = _stream_gen   # capture generation at request time
    def generate():
        while _live_feed.is_set() and _stream_gen == my_gen:
            jpeg = capture_jpeg()
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ========================= SOCKET EVENTS =========================
@socketio.on('connect')
def handle_connect():
    emit('feed_state', {'active': _live_feed.is_set()})

@socketio.on('toggle_feed')
def handle_toggle():
    global _stream_gen
    if _live_feed.is_set():
        _live_feed.clear()
        stop_led()
    else:
        _stream_gen += 1   # invalidate any lingering generator from a previous session
        _live_feed.set()
        start_led()
    socketio.emit('feed_state', {'active': _live_feed.is_set()})

# ========================= HTML =========================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi Camera Feed</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        #player { aspect-ratio: 16/9; object-fit: cover; }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen flex flex-col items-center justify-center p-6">
<div class="w-full max-w-3xl space-y-5">

    <h1 class="text-2xl font-bold text-center tracking-tight">📷 Pi Camera Feed</h1>

    <!-- Player -->
    <div class="rounded-2xl overflow-hidden bg-black shadow-xl ring-1 ring-white/10">
        <img id="player" src="/still" alt="Camera" class="w-full block" id="player">
    </div>

    <!-- Toggle button -->
    <div class="flex flex-col items-center gap-3">
        <button id="toggleBtn" onclick="toggleFeed()"
                class="px-10 py-3 rounded-xl font-semibold text-sm tracking-wide transition-all
                       bg-blue-600 hover:bg-blue-500 active:scale-95 select-none">
            ▶ Start Live Feed
        </button>
        <p id="statusText" class="text-sm text-gray-400">Still frame captured at page load</p>
    </div>

</div>

<script>
    const socket = io();
    let isLive = false;

    const BTN_BASE  = 'px-10 py-3 rounded-xl font-semibold text-sm tracking-wide transition-all active:scale-95 select-none';
    const BTN_START = BTN_BASE + ' bg-blue-600 hover:bg-blue-500';
    const BTN_STOP  = BTN_BASE + ' bg-red-600 hover:bg-red-500';

    // ---- Socket ----
    socket.on('feed_state', (data) => {
        isLive = data.active;
        const player = document.getElementById('player');
        const btn    = document.getElementById('toggleBtn');
        const status = document.getElementById('statusText');

        if (isLive) {
            player.src         = '/stream.mjpg?' + Date.now();
            btn.className      = BTN_STOP;
            btn.textContent    = '⏹ Stop Live Feed';
            status.textContent = 'Live feed active — LED flashing';
        } else {
            btn.className      = BTN_START;
            btn.textContent    = '▶ Start Live Feed';
            status.textContent = 'Live feed stopped';
        }
    });

    // ---- Toggle ----
    function toggleFeed() {
        if (isLive) {
            // Switch away from MJPEG immediately so there's no dead-stream gap
            document.getElementById('player').src = '/still?' + Date.now();
        }
        socket.emit('toggle_feed');
    }
</script>
</body>
</html>
"""

# ========================= MAIN =========================
def main() -> None:
    global led
    init_camera()
    led = RGBLED(18, 23, 24)

    threading.Thread(
        target=lambda: socketio.run(app, host='0.0.0.0', port=5000, debug=False),
        daemon=True,
    ).start()
    print("🌐 Web UI → http://<PI_IP>:5000")

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        _live_feed.clear()
        stop_led()
        picam2.stop()

if __name__ == "__main__":
    main()
