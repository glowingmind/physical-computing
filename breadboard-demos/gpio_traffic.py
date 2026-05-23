from gpiozero import Button, Buzzer, TrafficLights
from time import sleep

button = Button(21)
buzzer = Buzzer(18)
lights = TrafficLights(25, 8, 7)

try:
    while True:
        button.wait_for_press()
        lights.red.on()
        sleep(5)
        lights.red.blink(0.5, 0.5)
        sleep(5)
        buzzer.beep(0.5, 0.5)
        lights.amber.blink(0.5, 0.5)
        sleep(5)
        buzzer.off()
        lights.red.off()
        lights.amber.off()
        lights.green.on()
        sleep(10)
        lights.green.blink(0.5, 0.5)
        sleep(5)
        buzzer.beep(0.5, 0.5)
        lights.amber.blink(0.5, 0.5)
        sleep(5)
        buzzer.off()
        lights.green.off()
        lights.amber.off()
        lights.red.on()

except KeyboardInterrupt:
    lights.off()
