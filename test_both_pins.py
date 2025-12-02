import Jetson.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setup(29, GPIO.OUT)
GPIO.setup(31, GPIO.OUT)

print('5초간 HIGH 유지 - 멀티미터로 Pin 29, 31 전압 측정')
GPIO.output(29, GPIO.HIGH)
GPIO.output(31, GPIO.HIGH)
time.sleep(5)

GPIO.cleanup()
print('완료')
