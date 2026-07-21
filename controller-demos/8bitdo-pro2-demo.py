# import evdev
from evdev import InputDevice, categorize, ecodes
from gpiozero import RGBLED
from random import Random
from time import sleep

def find_device(device_name):
    for device in evdev.list_devices():
        dev = evdev.InputDevice(device)
        if device_name in dev.name:
            return dev
    return None

def handle_input_event(event, button_map):
    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
        button = button_map.get(event.code)
        if button:
            print(f"Button {button} pressed")

def main():
    device_name = "Your Device Name"
    button_map = {
        evdev.ecodes.KEY_A: "A",
        evdev.ecodes.KEY_B: "B",
        # Add more key mappings as needed
    }

    dev = find_device(device_name)
    if not dev:
        print(f"Device '{device_name}' not found")
        return

    for event in dev.read_loop():
        handle_input_event(event, button_map)

if __name__ == "__main__":
    main()

# create callable object to access controller data
rmtctl = InputDevice('/dev/input/event7')

# create RGBLED object to control LED colors
led = RGBLED(18, 23, 24)
rnd = Random()
values = [0, 0, 0]
is_manual_config = False
active_value = 0

# print out controller data
print(rmtctl)

def shift_list(l):
    return l[-1:]+l[:-1]

try:
    # loop to read controller data
    for event in rmtctl.read_loop():
        if event.type == ecodes.EV_KEY:
            # print(categorize(event))
            # print(event.code)
            if event.code == 310 and event.value == 1:
                is_manual_config = not is_manual_config
                if not is_manual_config:
                    led.pulse(
                        fade_in_time=1,
                        fade_out_time=1,
                        on_color=tuple(values),
                        off_color=(0, 0, 0),
                        n=None,
                        background=True
                    )
                continue
            if not is_manual_config:
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
        elif event.type == ecodes.EV_ABS and is_manual_config:
            # print(event)
            # print(categorize(event))
            if event.code == 17 and event.value < 0 and values[active_value] < 1:
                values[active_value] = round(values[active_value] + 0.01, 2)
                led.color = (tuple(values))
                print(values)
            if event.code == 17 and event.value > 0 and values[active_value] > 0:
                values[active_value] = round(values[active_value] - 0.01, 2)
                led.color = (tuple(values))
                print(values)
            if event.code == 16 and event.value > 0:
                active_value = active_value + 1
                if active_value > 2:
                    active_value = 0
                continue
            if event.code == 16 and event.value < 0:
                active_value = active_value - 1
                if active_value < 0:
                    active_value = 2
                continue
# except FileNotFoundError as e:
#     if e.errno == 2:
#         print("Controller device not found")
#     # print(f"Error occurred: {e}")
#     exit(1)
except OSError as e:
    if e.errno == 19:
        print("Controller device disconnected")
    # print(f"Error occurred: {e}")
    exit(1)
except KeyboardInterrupt:
    print("\nKeyboard interrupt received")
    led.off()
    exit(0)
