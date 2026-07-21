import RPi.GPIO as GPIO
from time import sleep

ldr_pin = 21

GPIO.setmode(GPIO.BCM)

GPIO.setup(ldr_pin, GPIO.IN)
try:
    while True:
        light_level = GPIO.input(ldr_pin)
        print("Light level: ", light_level)
        sleep(1)
except KeyboardInterrupt:
    GPIO.cleanup()
    exit(0)
