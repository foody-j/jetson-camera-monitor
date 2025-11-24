import Jetson.GPIO as GPIO
import time

# 29번 핀만 집중 테스트
try:
    GPIO.setmode(GPIO.BOARD)

    print("=== 29번 핀 테스트 ===")

    # 출력 모드로 설정
    GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)
    print("1. 출력 모드, LOW 설정")
    input("멀티미터로 확인 >>> ")

    # HIGH 출력
    GPIO.output(29, GPIO.HIGH)
    print("2. HIGH 출력")
    input("멀티미터로 확인 >>> ")

    # LOW 출력
    GPIO.output(29, GPIO.LOW)
    print("3. LOW 출력")
    input("멀티미터로 확인 >>> ")

    # 입력 모드로 변경 (풀다운)
    GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    print("4. 입력 모드(풀다운)로 변경")
    input("멀티미터로 확인 >>> ")

    # cleanup
    GPIO.cleanup()
    print("5. cleanup 완료")
    input("멀티미터로 최종 확인 >>> ")

finally:
    print("테스트 종료")
