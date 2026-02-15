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
# GPIO 핀 설정 (Pin 29 = GPIO07, Pin 31 = GPIO416)
echo 416 > /sys/class/gpio/export 2>/dev/null || true
echo 7 > /sys/class/gpio/export 2>/dev/null || true
echo out > /sys/class/gpio/gpio416/direction
echo out > /sys/class/gpio/gpio7/direction

# 릴레이 OFF (LOW)
echo 0 > /sys/class/gpio/gpio416/value
echo 0 > /sys/class/gpio/gpio7/value
sleep 10  # 커패시터 완전 방전 대기

# 3단계: 릴레이 ON (Pulse 방식)
echo "[3/6] 카메라 전원 ON (5초 대기)..."
echo 1 > /sys/class/gpio/gpio416/value
echo 1 > /sys/class/gpio/gpio7/value
sleep 0.2
echo 0 > /sys/class/gpio/gpio416/value
echo 0 > /sys/class/gpio/gpio7/value
sleep 5  # 전원 안정화 대기

# 4단계: 드라이버 재로드
echo "[4/6] 드라이버 재로드 (quick_bring_up.sh)..."
cd "$DRIVER_DIR"
sudo ./quick_bring_up.sh
sleep 3

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
