from gpiozero import Button

button = Button(5)

button.wait_for_press()
print('Button pressed!')
