#!/usr/bin/env python3
import lgpio
import time

# WARNING: lgpio uses BCM numbering!
# BCM 21 = Physical pin 40. If you used Physical pin 21, change this to BCM 9.
FAN_PIN = 21
ON_DELAY = 10

# Open the GPIO chip (chip 0 is the main one on Pi 4)
chip = lgpio.gpiochip_open(0)

try:
    # Claim the pin as output, starting in OFF (0) state to be safe
    lgpio.gpio_claim_output(chip, FAN_PIN, 0)

    print(f"Turning fan ON for {ON_DELAY} seconds...")
    lgpio.gpio_write(chip, FAN_PIN, 1)   # 1 = 3.3V -> Transistor turns ON -> Fan spins

    time.sleep(ON_DELAY)

    print("Turning fan OFF.")
    lgpio.gpio_write(chip, FAN_PIN, 0)   # 0 = 0V -> Transistor turns OFF -> Fan stops

except KeyboardInterrupt:
    print("\nTest interrupted by user.")

finally:
    # CRITICAL: Always release the GPIO chip to free the pin
    lgpio.gpiochip_close(chip)
    print("Cleanup complete. Pin is released.")
