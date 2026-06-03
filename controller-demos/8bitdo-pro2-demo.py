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
            if event.code == 305 and event.value == 1:
                for i, v in enumerate(values):
                    values[i] = rnd.random()
                led.pulse(
                    fade_in_time=1,
                    fade_out_time=1,
                    on_color=tuple(values),
                    off_color=(0, 0, 0),
                    n=None,
                    background=True
                )
                # led.color = (values[0], values[1], values[2])
                # print(values)
                # sleep(3)
                # values = shiftList(values)
                # led.color = (values[0], values[1], values[2])
                # print(values)
                # sleep(3)
                # values = shiftList(values)
                # led.color = (values[0], values[1], values[2])
                # print(values)
                # sleep(3)
            if event.code == 304 and event.value == 1:
                led.off()
        # elif event.type == ecodes.EV_ABS:
        #     print(categorize(event))
except OSError as e:
    if e.errno == 19:
        print("Controller device disconnected")
    # print(f"Error occurred: {e}")
    exit(1)
except KeyboardInterrupt:
    print("\nKeyboard interrupt received")
    led.off()
    exit(0)
