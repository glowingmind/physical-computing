from gpiozero import RGBLED, MotionSensor
from random import Random
from time import sleep
from picamera2 import Picamera2
from datetime import datetime
import os

# Setup folders and camera
VIDEO_DIR = "gpio_captures"
os.makedirs(VIDEO_DIR, exist_ok=True)

pir = MotionSensor(21)
led = RGBLED(18, 23, 24)
rnd = Random()
values = [0, 0, 0]

picam2 = Picamera2()

def record_short_video(duration=10):
    """Record a short video with timestamped filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(VIDEO_DIR, f"capture_{timestamp}.mp4")
    
    print(f"Motion detected! Recording {duration}s video to {filename}")
    
    # Simple one-liner for video recording
    picam2.start_and_record_video(filename, duration=duration)
    print("Recording finished.")

try:
    while True:
        pir.wait_for_motion()
        
        # Trigger LED sequence
        for i, v in enumerate(values):
            values[i] = rnd.random()
        led.color = (values[0], values[1], values[2])
        sleep(2)
        values = values[-1:] + values[:-1]
        led.color = (values[0], values[1], values[2])
        sleep(2)
        values = values[-1:] + values[:-1]
        led.color = (values[0], values[1], values[2])
        sleep(2)
        
        # Record video while LED is active
        record_short_video(duration=5)  # Adjust duration as needed
        
        pir.wait_for_no_motion()
        led.off()
        
except KeyboardInterrupt:
    led.off()
    picam2.close()  # Clean up camera
    print("Program stopped.")
