import Jetson.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)

print('Pin 31 (ON) 펄스...')
GPIO.output(31, GPIO.HIGH)
time.sleep(0.5)
GPIO.output(31, GPIO.LOW)

time.sleep(1)

print('Pin 29 (OFF) 펄스...')
GPIO.output(29, GPIO.HIGH)
time.sleep(0.5)
GPIO.output(29, GPIO.LOW)

GPIO.cleanup()
print('완료')
