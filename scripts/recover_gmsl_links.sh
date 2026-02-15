#!/bin/bash
# GMSL 멀티채널 링크 복구 스크립트
# 사용법: sudo ./recover_gmsl_links.sh

set -e

DRIVER_DIR="$HOME/jetson-food-ai/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3"

echo "🔧 GMSL 링크 복구 시작..."

# 1단계: 기존 드라이버 언로드
echo "[1/6] 기존 드라이버 언로드..."
sudo rmmod sgx_yuv_gmsl2 2>/dev/null || true
sleep 2

# 2단계: 릴레이 OFF (카메라 어댑터 전원 차단)
echo "[2/6] 카메라 전원 OFF (10초 대기)..."
# Jetson.GPIO를 사용한 릴레이 제어 (Python 스크립트 호출)
python3 - <<'PYTHON_RELAY_OFF'
import Jetson.GPIO as GPIO
import time

RELAY_PIN_1 = 29  # Pin 29 (GPIO07)
RELAY_PIN_2 = 31  # Pin 31 (GPIO416)

GPIO.setmode(GPIO.BOARD)
GPIO.setup(RELAY_PIN_1, GPIO.OUT)
GPIO.setup(RELAY_PIN_2, GPIO.OUT)

# 릴레이 OFF (LOW)
GPIO.output(RELAY_PIN_1, GPIO.LOW)
GPIO.output(RELAY_PIN_2, GPIO.LOW)
time.sleep(10)  # 커패시터 완전 방전 대기

# 릴레이 ON (Pulse)
GPIO.output(RELAY_PIN_1, GPIO.HIGH)
GPIO.output(RELAY_PIN_2, GPIO.HIGH)
time.sleep(0.2)
GPIO.output(RELAY_PIN_1, GPIO.LOW)
GPIO.output(RELAY_PIN_2, GPIO.LOW)

GPIO.cleanup()
PYTHON_RELAY_OFF

echo "[3/6] 카메라 전원 ON 완료 (5초 대기)..."
sleep 5  # 전원 안정화 대기

# 4단계: 드라이버 재로드
echo "[4/6] 드라이버 재로드 (quick_bring_up.sh)..."
DRIVER_DIR_EXPANDED="${DRIVER_DIR/#\~/$HOME}"
if [ -d "$DRIVER_DIR_EXPANDED" ]; then
    cd "$DRIVER_DIR_EXPANDED"
    ./quick_bring_up.sh
    sleep 3
else
    echo "⚠️ 드라이버 디렉토리를 찾을 수 없습니다: $DRIVER_DIR"
    echo "   수동으로 quick_bring_up.sh를 실행하세요."
fi

# 5단계: 링크 상태 확인
echo "[5/6] 링크 상태 확인..."
sudo dmesg | grep -E "dser_link_check|link:0x" | tail -8

# 6단계: 카메라 인식 확인
echo "[6/6] 카메라 디바이스 확인..."
v4l2-ctl --list-devices

echo ""
echo "✅ 복구 완료! 위 출력에서 확인:"
echo "  - link:0xda (정상) vs link:0x00 (실패)"
echo "  - /dev/video0~3 모두 표시되는지"
echo ""
echo "📌 테스트 명령:"
echo "  gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=30 ! fakesink"
