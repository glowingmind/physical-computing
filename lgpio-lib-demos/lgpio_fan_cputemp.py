#!/usr/bin/env python3
import lgpio
import subprocess
import time
import sys

# === CONFIGURATION ===
FAN_PIN = 21          # BCM 21 = Physical pin 40. Change to 9 if using Physical pin 21.
TEMP_THRESHOLD = 40.0 # Degrees Celsius (set to 40 for your test)
CHECK_INTERVAL = 15   # Seconds between temp checks
HOLD_DURATION = 30    # Seconds to keep fan ON after temp drops
POST_WAIT_DURATION = 60 # Seconds to wait with fan OFF before re-checking

# === HELPER FUNCTIONS ===
def get_cpu_temp():
    try:
        output = subprocess.check_output(['vcgencmd', 'measure_temp'], text=True)
        temp_str = output.split('=')[1].strip().split("'")[0]
        return float(temp_str)
    except Exception as e:
        print(f"\n⚠️  Error reading temperature: {e}")
        return 0.0

def fan_on(chip):
    lgpio.gpio_write(chip, FAN_PIN, 1)

def fan_off(chip):
    lgpio.gpio_write(chip, FAN_PIN, 0)

def status_line(msg):
    """Print a status message, completely clearing the current line first."""
    sys.stdout.write(f'\r\033[K{msg}')  # \033[K clears from cursor to end of line
    sys.stdout.flush()

def newline():
    """Move the cursor to the next line without printing any extra spaces."""
    sys.stdout.write('\n')
    sys.stdout.flush()

# === MAIN STATE MACHINE ===
def main():
    chip = lgpio.gpiochip_open(0)
    try:
        lgpio.gpio_claim_output(chip, FAN_PIN, 0)
        print(f"🚀 Fan controller started. Threshold: {TEMP_THRESHOLD}°C")
        print(f"   Check interval: {CHECK_INTERVAL}s | Hold time: {HOLD_DURATION}s")
        print("─" * 50)

        while True:
            # ---------- STATE: IDLE ----------
            while True:
                temp = get_cpu_temp()
                if temp > TEMP_THRESHOLD:
                    newline()  # <-- CRITICAL: move to a fresh line before printing
                    print(f"🔥 {temp:.1f}°C exceeded {TEMP_THRESHOLD}°C – turning fan ON.")
                    fan_on(chip)
                    break
                else:
                    status_line(f"⏳ [IDLE] Temp: {temp:.1f}°C | Fan OFF | Next check in {CHECK_INTERVAL}s")
                time.sleep(CHECK_INTERVAL)

            # ---------- STATE: COOLING ----------
            while True:
                temp = get_cpu_temp()
                if temp <= TEMP_THRESHOLD:
                    newline()  # <-- CRITICAL: move to a fresh line before printing
                    print(f"✅ {temp:.1f}°C dropped to threshold – fan will stay ON for hold period.")
                    break
                else:
                    status_line(f"🌬️  [COOLING] Temp: {temp:.1f}°C | Fan ON  | Cooling down...")
                time.sleep(CHECK_INTERVAL)

            # ---------- STATE: HOLD ----------
            print(f"⏱️  [HOLD] Keeping fan ON for {HOLD_DURATION}s (ignoring temp).")
            for remaining in range(HOLD_DURATION, 0, -1):
                status_line(f"⏱️  [HOLD] Fan ON | Countdown: {remaining:3}s remaining")
                time.sleep(1)
            newline()  # Move to next line after countdown finishes

            fan_off(chip)
            print("🔴 Fan turned OFF.")

            # ---------- STATE: POST_OFF_WAIT ----------
            print(f"🕒 [POST_OFF_WAIT] Waiting {POST_WAIT_DURATION}s before resuming checks.")
            for remaining in range(POST_WAIT_DURATION, 0, -1):
                status_line(f"🕒 [POST_OFF_WAIT] Countdown: {remaining:3}s until re-checking")
                time.sleep(1)
            newline()  # Move to next line
            print("↩️  Returning to IDLE state.")
            print("─" * 50)

    except KeyboardInterrupt:
        print("\n🛑 Script interrupted.")
    finally:
        fan_off(chip)
        lgpio.gpiochip_close(chip)
        print("🧹 GPIO cleaned up. Goodbye!")

if __name__ == "__main__":
    main()
