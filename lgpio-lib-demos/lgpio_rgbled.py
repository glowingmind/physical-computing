import lgpio
import time

# Set up pins for RGB LED
red_pin = 18
green_pin = 23
blue_pin = 24

h = lgpio.gpiochip_open(0)  # Open GPIO chip 0

# Set up GPIO mode and pin direction
lgpio.gpio_claim_output(h, red_pin, 0)
lgpio.gpio_claim_output(h, green_pin, 0)
lgpio.gpio_claim_output(h, blue_pin, 0)

try:
    while True:
        # Pulse red LED
        lgpio.gpio_write(h, red_pin, 1)
        time.sleep(1)
        lgpio.gpio_write(h, red_pin, 0)

        # Pulse green LED
        lgpio.gpio_write(h, green_pin, 1)
        time.sleep(1)
        lgpio.gpio_write(h, green_pin, 0)

        # Pulse blue LED
        lgpio.gpio_write(h, blue_pin, 1)
        time.sleep(1)
        lgpio.gpio_write(h, blue_pin, 0)
except KeyboardInterrupt:
    # Clean up GPIO settings
    lgpio.gpio_write(h, red_pin, 0)
    lgpio.gpio_write(h, green_pin, 0)
    lgpio.gpio_write(h, blue_pin, 0)
lgpio.gpiochip_close(h)
