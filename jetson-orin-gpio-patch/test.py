import Jetson.GPIO as GPIO
import time

try:
    # BOARD 모드 사용
    GPIO.setmode(GPIO.BOARD)

    # Pin 29, 31을 출력으로 설정
    GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)

    # HIGH 출력 (3.3V)
    GPIO.output(29, GPIO.HIGH)
    GPIO.output(31, GPIO.HIGH)
    print("핀 29, 31 HIGH 출력 중...")
    input("멀티미터로 확인 후 엔터 >>> ")

    # LOW 출력 (0V)
    print("핀 29, 31 LOW 출력으로 변경...")
    GPIO.output(29, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(31, GPIO.LOW)
    time.sleep(0.1)
    input("멀티미터로 확인 후 엔터 >>> ")

    print("cleanup 실행합니다...")

finally:
    # 정리 - cleanup 전에 명시적으로 LOW 설정 후 입력 모드로 변경
    print("GPIO cleanup 실행 중...")
    GPIO.output(29, GPIO.LOW)
    GPIO.output(31, GPIO.LOW)
    time.sleep(0.1)

    # 입력 모드로 변경 (풀다운)
    GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(31, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    time.sleep(0.1)

    GPIO.cleanup()
    print("완료 - 멀티미터로 최종 상태 확인하세요")