# import evdev
from evdev import InputDevice, categorize, ecodes
from gpiozero import RGBLED
from random import Random
from time import sleep

# create callable object to access controller data
rmtctl = InputDevice('/dev/input/event7')

# create RGBLED object to control LED colors
led = RGBLED(18, 23, 24)
rnd = Random()
values = [0, 0, 0]
isManualConfig = False
activeValue = 0

# print out controller data
print(rmtctl)

def shiftList(l):
    return l[-1:]+l[:-1]

try:
    # loop to read controller data
    for event in rmtctl.read_loop():
        if event.type == ecodes.EV_KEY:
            # print(categorize(event))
            # print(event.code)
            if event.code == 310 and event.value == 1:
                isManualConfig = not isManualConfig
                if not isManualConfig:
                    led.pulse(
                        fade_in_time=1,
                        fade_out_time=1,
                        on_color=tuple(values),
                        off_color=(0, 0, 0),
                        n=None,
                        background=True
                    )
                continue
            if not isManualConfig:
                if event.code == 305 and event.value == 1:
                    for i, v in enumerate(values):
                        values[i] = round(rnd.random(), 2)
                    led.pulse(
                        fade_in_time=1,
                        fade_out_time=1,
                        on_color=tuple(values),
                        off_color=(0, 0, 0),
                        n=None,
                        background=True
                    )
                if event.code == 304 and event.value == 1:
                    led.off()
        elif event.type == ecodes.EV_ABS and isManualConfig:
            # print(event)
            # print(categorize(event))
            if event.code == 17 and event.value < 0 and values[activeValue] < 1:
                values[activeValue] = round(values[activeValue] + 0.01, 2)
                led.color = (tuple(values))
                print(values)
            if event.code == 17 and event.value > 0 and values[activeValue] > 0:
                values[activeValue] = round(values[activeValue] - 0.01, 2)
                led.color = (tuple(values))
                print(values)
            if event.code == 16 and event.value > 0:
                activeValue = activeValue + 1
                if activeValue > 2:
                    activeValue = 0
                continue
            if event.code == 16 and event.value < 0:
                activeValue = activeValue - 1
                if activeValue < 0:
                    activeValue = 2
                continue

except OSError as e:
    if e.errno == 19:
        print("Controller device disconnected")
    # print(f"Error occurred: {e}")
    exit(1)
except KeyboardInterrupt:
    print("\nKeyboard interrupt received")
    led.off()
    exit(0)
