import Jetson.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)

print('Pin 29 LOW 상태 (5초간 측정하세요)')
time.sleep(5)

print('Pin 29 HIGH로 변경 (10초간 측정하세요)')
GPIO.output(29, GPIO.HIGH)
time.sleep(10)

print('Pin 29 LOW로 변경')
GPIO.output(29, GPIO.LOW)

GPIO.cleanup()
print('완료')
