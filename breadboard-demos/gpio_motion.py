from gpiozero import RGBLED, DistanceSensor
from random import Random

motion = DistanceSensor(echo=17, trigger=4, threshold_distance=0.5)
led = RGBLED(18, 23, 24)
rnd = Random()
values = [0, 0, 0]

try:
    while True:
        motion.wait_for_in_range()
        for i, v in enumerate(values):
            values[i] = rnd.random()
        led.color = (values[0], values[1], values[2])
        motion.wait_for_out_of_range()
        led.off()
except KeyboardInterrupt:
    led.off()
