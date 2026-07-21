import RPi.GPIO as GPIO

MicPin = 5
RelayPin = 6

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(MicPin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(RelayPin, GPIO.OUT, initial=GPIO.LOW)

try:
    while True:
        # if (GPIO.input(MicPin) > 0):
        #     print("Sound detected")
        GPIO.output(RelayPin, GPIO.input(MicPin))
except KeyboardInterrupt:
    GPIO.cleanup()
    exit(0)
