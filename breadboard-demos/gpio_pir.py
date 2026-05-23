from gpiozero import RGBLED, MotionSensor
from random import Random
from time import sleep

pir = MotionSensor(21)
led = RGBLED(18, 23, 24)
rnd = Random()
values = [0, 0, 0]

try:
    while True:
        pir.wait_for_motion()
        for i, v in enumerate(values):
            values[i] = rnd.random()
        led.color = (values[0], values[1], values[2])
        sleep(2)
        values = values[-1:]+values[:-1]
        led.color = (values[0], values[1], values[2])
        sleep(2)
        values = values[-1:]+values[:-1]
        led.color = (values[0], values[1], values[2])
        sleep(2)
        pir.wait_for_no_motion()
        led.off()
except KeyboardInterrupt:
    led.off()
