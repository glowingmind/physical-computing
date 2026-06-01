# import evdev
from evdev import InputDevice, categorize, ecodes

# create callable object to access controller data
rmtctl = InputDevice('/dev/input/event7')

# print out controller data
print(rmtctl)

try:
    # loop to read controller data
    for event in rmtctl.read_loop():
        if event.type == ecodes.EV_KEY:
            print(categorize(event))
        elif event.type == ecodes.EV_ABS:
            print(categorize(event))
except KeyboardInterrupt:
    print("\nExiting program")