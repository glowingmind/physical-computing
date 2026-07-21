#!/usr/bin/python

from Adafruit_CharLCD import Adafruit_CharLCD
from subprocess import *
from time import sleep, strftime
from datetime import datetime

lcd = Adafruit_CharLCD()

# cmd = "ip addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1"
cmd =  "vcgencmd measure_temp"

lcd.begin(16, 1)


def run_cmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    output = p.communicate()[0]
    return output

def get_temp(input):
    parts = input.split(b"=")
    return parts[-1]

while 1:
    lcd.clear()
    output = run_cmd(cmd)
    curr_temp = get_temp(output)
    clean = curr_temp.decode('utf-8').strip().replace("'", " ")
    lcd.message(datetime.now().strftime('%b %d  %H:%M\n'))
    # lcd.message('%s' % (ipclean))
    lcd.message('CPU: %s' % (clean))
    sleep(5)
