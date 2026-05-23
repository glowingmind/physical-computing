from gpiozero import Button, RGBLED
from random import Random
from time import sleep

button = Button(21)
led = RGBLED(18, 23, 24)
rnd = Random()
values = [0, 0, 0]

try:
    while True:
        for i, v in enumerate(values):
            values[i] = rnd.random()
        led.color = (values[0], values[1], values[2])
        # print(values)
        sleep(3)
        values = values[-1:]+values[:-1]
        led.color = (values[0], values[1], values[2])
        # print(values)
        sleep(3)
        values = values[-1:]+values[:-1]
        led.color = (values[0], values[1], values[2])
        # print(values)
        sleep(3)

except KeyboardInterrupt:
    led.off()
