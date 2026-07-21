#!/usr/bin/env python3
import lgpio
import subprocess
import time
import sys

# === CONFIGURATION ===
FAN_PIN = 21          # BCM 21 = Physical pin 40. Change if you used a different BCM number.
TEMP_THRESHOLD = 45.0 # Degrees Celsius
CHECK_INTERVAL = 15   # Seconds between temp checks in IDLE/COOLING
HOLD_DURATION = 60    # Seconds to keep fan ON after temp drops
POST_WAIT_DURATION = 60 # Seconds to wait with fan OFF before re-checking

# === HELPER FUNCTIONS ===
def get_cpu_temp():
    """Reads CPU temp via vcgencmd and returns it as a float."""
    try:
        # Run the command
        output = subprocess.check_output(['vcgencmd', 'measure_temp'], text=True)
        # Output looks like: "temp=39.4'C"
        temp_str = output.split('=')[1].strip()   # Get "39.4'C"
        temp_str = temp_str.split("'")[0]         # Get "39.4"
        return float(temp_str)
    except Exception as e:
        print(f"⚠️  Error reading temperature: {e}")
        # Return a safe value (e.g., 0) to avoid false triggers, but print error.
        # Alternatively, return float('inf') to force fan ON as a safety measure.
        # I'll return 0 so it doesn't accidentally turn on due to read error.
        return 0.0

def fan_on(chip):
    lgpio.gpio_write(chip, FAN_PIN, 1)
    print("🟢 Fan: ON")

def fan_off(chip):
    lgpio.gpio_write(chip, FAN_PIN, 0)
    print("🔴 Fan: OFF")

# === MAIN STATE MACHINE ===
def main():
    # Open GPIO chip
    chip = lgpio.gpiochip_open(0)
    try:
        # Claim the pin as output, starting in OFF state
        lgpio.gpio_claim_output(chip, FAN_PIN, 0)
        print(f"🚀 Fan controller started. Threshold: {TEMP_THRESHOLD}°C")
        print(f"   Checking every {CHECK_INTERVAL}s. Hold time: {HOLD_DURATION}s.\n")

        while True:
            # ---------- STATE: IDLE ----------
            print("⏳ [IDLE] Fan OFF. Monitoring temp...")
            while True:
                temp = get_cpu_temp()
                print(f"   Temp: {temp:.1f}°C", end="")
                if temp > TEMP_THRESHOLD:
                    print(" → 🔥 Threshold exceeded! Activating fan.")
                    fan_on(chip)
                    break  # Exit IDLE loop, go to COOLING
                else:
                    print(" (Below threshold, waiting)")
                time.sleep(CHECK_INTERVAL)

            # ---------- STATE: COOLING ----------
            print("🌬️  [COOLING] Fan ON. Watching for temp drop...")
            while True:
                temp = get_cpu_temp()
                print(f"   Temp: {temp:.1f}°C", end="")
                if temp <= TEMP_THRESHOLD:
                    print(" → ✅ Temperature dropped! Entering HOLD state.")
                    break  # Exit COOLING loop, go to HOLD
                else:
                    print(" (Still hot, continuing)")
                time.sleep(CHECK_INTERVAL)

            # ---------- STATE: HOLD ----------
            # (Fan stays ON, we stop checking temp completely)
            print(f"⏱️  [HOLD] Keeping fan ON for {HOLD_DURATION}s (ignoring temp).")
            time.sleep(HOLD_DURATION)
            fan_off(chip)

            # ---------- STATE: POST_OFF_WAIT ----------
            print(f"🕒 [POST_OFF_WAIT] Fan OFF. Waiting {POST_WAIT_DURATION}s before resuming checks.")
            time.sleep(POST_WAIT_DURATION)
            print("↩️  Returning to IDLE state.\n")

    except KeyboardInterrupt:
        print("\n🛑 Script interrupted by user.")
    finally:
        # Safety: turn fan off and release GPIO
        fan_off(chip)
        lgpio.gpiochip_close(chip)
        print("🧹 GPIO cleaned up. Goodbye!")

if __name__ == "__main__":
    main()
