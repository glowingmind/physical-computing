from Adafruit_CharLCD import Adafruit_CharLCD
from time import sleep

lcd = Adafruit_CharLCD()
lcd.clear()
sleep(2)
lcd.message("Raspberry Pi 4B\nMemory: 8GB")
sleep(2)

# lcd.noDisplay()
# lcd.message("MESSAGE")
# lcd.display()
# lcd.clear()
# lcd.message("MESSAGE")

# lcd.cursor()
# lcd.blink()
# lcd.noCursor()
# lcd.noBlink()

# lcd.home()
# lcd.clear()
# lcd.begin(16,2)
# lcd.setCursor(9,1)
# lcd.message("X")
# lcd.setCursor(8,0)
# lcd.message("YZ")
# lcd.clear()

for x in range(0, 16):
    lcd.scrollDisplayRight()
    sleep(.2)

for x in range(0, 16):
    lcd.DisplayLeft()
    sleep(.2)

# lcd.noBlink()
# lcd.clear()
# lcd.message("Raspberry Pi 4B\nMemory: 8GB")

exit(0)
