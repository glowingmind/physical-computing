from gpiozero import Button, RGBLED
from time import sleep

button = Button(21)
led = RGBLED(18, 23, 24)

try:
    while True:
        led.blink(2, 4)
        button.wait_for_press()
        led.color = (1, 1, 1)
        sleep(3)
        led.color = (0.75, 1, 0)
        sleep(3)
        led.color = (0, 1, 0.75)
        sleep(3)
        led.color = (0.75, 0, 0.75)
        sleep(3)
        led.color = (1, 0.25, 0.25)
        sleep(3)
        led.color = (0.25, 1, 0.25)
        sleep(3)
        led.color = (0.25, 0.25, 1)
        sleep(3)

except KeyboardInterrupt:
    led.off()
