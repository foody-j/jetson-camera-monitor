#!/bin/bash
# GMSL 멀티채널 링크 복구 스크립트
# 사용법: sudo ./recover_gmsl_links.sh

set -e

DRIVER_DIR="$HOME/jetson-food-ai/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3"

echo "🔧 GMSL 링크 복구 시작..."
echo "⚠️  카메라 전원 OFF/ON은 수동으로 먼저 진행하세요!"
echo ""

# 1단계: 기존 드라이버 언로드
echo "[1/4] 기존 드라이버 언로드..."
sudo rmmod sgx_yuv_gmsl2 2>/dev/null || true
sleep 2

# 2단계: 드라이버 재로드
echo "[2/4] 드라이버 재로드 (quick_bring_up.sh)..."
DRIVER_DIR_EXPANDED="${DRIVER_DIR/#\~/$HOME}"
if [ -d "$DRIVER_DIR_EXPANDED" ]; then
    cd "$DRIVER_DIR_EXPANDED"
    ./quick_bring_up.sh
    sleep 3
else
    echo "⚠️ 드라이버 디렉토리를 찾을 수 없습니다: $DRIVER_DIR"
    echo "   수동으로 quick_bring_up.sh를 실행하세요."
fi

# 3단계: 링크 상태 확인
echo "[3/4] 링크 상태 확인..."
sudo dmesg | grep -E "dser_link_check|link:0x" | tail -8

# 4단계: 카메라 인식 확인
echo "[4/4] 카메라 디바이스 확인..."
v4l2-ctl --list-devices

echo ""
echo "✅ 복구 완료! 위 출력에서 확인:"
echo "  - link:0xda (정상) vs link:0x00 (실패)"
echo "  - /dev/video0~3 모두 표시되는지"
echo ""
echo "📌 테스트 명령:"
echo "  gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=30 ! fakesink"
