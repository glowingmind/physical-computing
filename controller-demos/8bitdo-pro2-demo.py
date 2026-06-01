# import evdev
from evdev imiport InputDevice, categorize, ecodes

# create callable object to access controller data
rmtctl = InputDevice('/dev/input/event7')

# print out controller data
print(rmtctl)

# loop to read controller data
for event in rmtctl.read_loop():
    if event.type == ecodes.E_KEY:
        print(categorize(event))
    elif event.type == ecodes.E_ABS:
        print(categorize(event))
