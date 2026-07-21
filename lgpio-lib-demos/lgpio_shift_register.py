import lgpio
import time
import evdev
from evdev import InputDevice, categorize, ecodes

# GPIO Pin Definitions
SCLK = 13   # Serial Clock (SRCLK)
RCLK = 19   # Register Clock / Latch (RCLK)
SER = 26    # Serial Data Input (SER)
SRCLR = 6   # Shift Register Clear (Active Low)
OE = 5      # Output Enable (Active Low)

class ShiftRegister74HC595:
    def __init__(self, chip_handle, sclk, rclk, ser, srclr, oe):
        self.h = chip_handle
        self.sclk = sclk
        self.rclk = rclk
        self.ser = ser
        self.srclr = srclr
        self.oe = oe
        
        # Initialize pins
        lgpio.gpio_claim_output(self.h, self.sclk, 0)
        lgpio.gpio_claim_output(self.h, self.rclk, 0)
        lgpio.gpio_claim_output(self.h, self.ser, 0)
        lgpio.gpio_claim_output(self.h, self.srclr, 1) # Normal state is High
        lgpio.gpio_claim_output(self.h, self.oe, 0)    # Normal state is Low (Enabled)
        
        self.oe_state = 0 # Currently enabled

    def shift_bit(self, bit):
        """Shifts a single bit into the register."""
        lgpio.gpio_write(self.h, self.ser, bit)
        time.sleep(0.001)
        # Pulse SCLK
        lgpio.gpio_write(self.h, self.sclk, 1)
        time.sleep(0.001)
        lgpio.gpio_write(self.h, self.sclk, 0)
        print(f"Shifted bit: {bit}")

    def latch(self):
        """Latches the internal register to the output pins."""
        lgpio.gpio_write(self.h, self.rclk, 1)
        time.sleep(0.001)
        lgpio.gpio_write(self.h, self.rclk, 0)
        print("Latched data to outputs")

    def clear(self):
        """Clears the shift register (active low)."""
        lgpio.gpio_write(self.h, self.srclr, 0)
        time.sleep(0.001)
        lgpio.gpio_write(self.h, self.srclr, 1)
        print("Cleared shift register")

    def toggle_output_enable(self):
        """Toggles the Output Enable state."""
        self.oe_state = 1 if self.oe_state == 0 else 0
        lgpio.gpio_write(self.h, self.oe, self.oe_state)
        status = "Disabled" if self.oe_state else "Enabled"
        print(f"Output Enable {status}")

def find_controller():
    """Finds an 8BitDo or common gaming controller."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        print(f"Found device: {device.name} at {device.path}")
        if "8BitDo" in device.name or "Controller" in device.name:
            return device
    return None

def main():
    chip = lgpio.gpiochip_open(0)
    sr = ShiftRegister74HC595(chip, SCLK, RCLK, SER, SRCLR, OE)
    
    print("Searching for controller...")
    dev = find_controller()
    
    if not dev:
        print("No controller found. Please connect your Bluetooth controller.")
        lgpio.gpiochip_close(chip)
        return

    print(f"Using {dev.name}. Controls:")
    print("  A: Shift 1")
    print("  B: Shift 0")
    print("  X: Latch (Show output)")
    print("  Y: Clear Register")
    print("  L1: Toggle Output Enable")

    try:
        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY:
                # print(event)  # Debug: print the event
                # event.value == 1 is press, 0 is release, 2 is hold
                if event.value == 1:
                    if event.code == 305: # Button A
                        sr.shift_bit(1)
                    elif event.code == 304: # Button B
                        sr.shift_bit(0)
                    elif event.code == 307: # Button X
                        sr.latch()
                    elif event.code == 306: # Button Y
                        sr.clear()
                    elif event.code == 308: # Button L1
                        sr.toggle_output_enable()
                    else:
                        print(f"Unhandled button code: {event.code}")
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        lgpio.gpiochip_close(chip)

if __name__ == "__main__":
    main()
