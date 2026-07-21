# Camera Capture System Documentation

This document explains the architecture and logic of `camera_capture.py`, a Raspberry Pi security camera application utilizing dual-sensor detection, automated recording, and a web dashboard.

## 1. Imports and Libraries

- **`threading`**: Used to run the sensor monitoring, logic controller, and Flask server concurrently. This prevents the hardware polling from freezing the video stream.
- **`time`**: Manages the 30-second idle capture intervals and the mandatory 10-second recording cooldown.
- **`cv2` (OpenCV)**: Handles image processing, such as adding timestamp overlays and converting BGR frames (raw camera format) to RGB for web browsers.
- **`lgpio`**: The library for interfacing with the Raspberry Pi's GPIO pins. It is chosen for its stability and low-latency on Pi 4/5 hardware.
- **`datetime`**: Generates human-readable timestamps for filenames and text overlays.
- **`flask` & `flask_socketio`**: Provides the web server and real-time bi-directional communication between the Python script and your browser.
- **`picamera2`**: The high-level Python library for the modern Raspberry Pi camera system (Libcamera).
- **`libcamera`**: Used specifically to apply hardware-level transforms (180° rotation) directly to the sensor configuration.

## 2. Configuration and Global State

The script maintains several "Event" flags to keep all threads in sync:

- **`motion_event`**: Set by the sensors the instant activity is detected. It is "raw" and can flicker.
- **`streaming_event`**: A "smoothed" signal. It turns on when motion starts and stays on throughout the 10-second cooldown period. This is what the UI actually watches.
- **`current_mode`**: Tracks if the system is in `manual` (user-led) or `detection` (sensor-led) mode.

## 3. Key Methods

### Camera Control
- **`init_camera()`**: Sets up the camera with a 180° flip using `libcamera.Transform`. This is more efficient than rotating the image in Python after it's captured.
- **`capture_image()`**: Grabs a single frame, adds a red timestamp, and saves it. It uses a small delay before notifying the UI to ensure the file is fully written to the SD card.
- **`start_video_recording()`**: A helper method that initializes the H264 encoder and begins saving video to an `.mp4` file. (Note: currently intended for manual invocation, not automated in this script's detection loop to avoid encoder conflicts).
- **`stop_video_recording()`**: Safely ends the recording and triggers a "sidebar" refresh in the UI.

### Logic and Monitoring
- **`sensor_worker()`**: The "Hardware Listener." It polls Pins 17 (PIR) and 27 (MIC) 10 times per second. It emits raw sensor data via SocketIO so you can see the blinking dots on the dashboard ("Sensor Diagnostics").
- **`controller_loop()`**: The "Brain."
    - **In Detection Mode**: It waits for `motion_event`. When hair-triggered by sensors, it sets the `streaming_event` to activate the web feed.
    - **The Cooldown**: When sensors go quiet, it keeps the stream alive for exactly 10 seconds. If motion happens *during* that wait, the timer resets.
    - **Idle Capture**: If nothing has happened for 30 seconds (and it's not currently streaming), it takes a "snapshot" so you can see the current environment.
- **`get_sorted_files()`**: A utility that sorts the `captures/` folder by **modification time** rather than name. This ensures the viewer doesn't get stuck on the alphabetically superior "manual" images.

### Web API
- **`@app.route('/stream.mjpg')`**: Generates the live feed. It's smart enough to only capture frames when someone is actually watching or a recording is in progress.
- **`@app.route('/latest_capture')`**: Allows the browser to identify the newest photo for the main viewer without having to refresh the whole page.

## 4. UI Logic (The JavaScript Part)

- **`socket.on('status_update')`**: The primary state synchronizer. When the `motion` flag in this payload becomes `true` (controlled by the server's cooldown logic), the browser switches the `<img>` tag from a still image to the live MJPEG stream.
- **Transition Back**: When motion ends (after the 10s cooldown), the JS detects the state change, waits briefly to let disk operations conclude, and then automatically switches the view back to the most recent photo.
- **Cache Busting**: Every image update includes a timestamp in the URL (`?t=...`). This tricks the browser into downloading the new file instead of showing you a cached version of the previous one.
