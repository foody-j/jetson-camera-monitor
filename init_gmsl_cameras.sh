#!/bin/bash
# GMSL 카메라 자동 초기화 스크립트
# 4개 카메라 모두 GMSL2/3G, 1920x1536으로 설정

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KO_DIR="$SCRIPT_DIR/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/ko"

echo "===== GMSL 카메라 자동 초기화 ====="

# 커널 모듈 로드
echo "[1/4] 커널 모듈 로드 중..."
cd $KO_DIR

if ! lsmod | grep -q max96712; then
    sudo insmod max96712.ko
    echo "  - max96712 로드 완료"
fi

if ! lsmod | grep -q gmsl2; then
    # GMSL2/3G 모드 (2,2,2,2)
    sudo insmod sgx-yuv-gmsl2.ko GMSLMODE_1=2,2,2,2
    echo "  - sgx-yuv-gmsl2 로드 완료 (모드: GMSL2/3G)"
fi

sleep 2

# 카메라 장치 확인
echo ""
echo "[2/4] 카메라 장치 확인..."
ls -l /dev/video* 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: 카메라 장치가 생성되지 않았습니다!"
    exit 1
fi

# 클럭 설정
echo ""
echo "[3/4] 카메라 클럭 설정..."
chmod +x $SCRIPT_DIR/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/clock_config.sh
$SCRIPT_DIR/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/clock_config.sh 2>/dev/null
echo "  ✓ 클럭 설정 완료"

# 각 카메라 초기화 (1920x1536 = mode 1)
echo ""
echo "[4/4] 카메라 초기화 중 (1920x1536)..."

for port in 0 1 2 3; do
    echo "  - video${port} 초기화..."
    v4l2-ctl --set-ctrl bypass_mode=0,sensor_mode=1 -d /dev/video${port} 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "    ✓ video${port} 초기화 완료"
    else
        echo "    ✗ video${port} 초기화 실패"
    fi
done

echo ""
echo "===== 초기화 완료 ====="
echo ""
echo "카메라 장치:"
ls -l /dev/video*
echo ""
echo "이제 프로그램을 실행하세요:"
echo "  cd ~/jetson-food-ai/jetson2_frying_ai"
echo "  python3 JETSON2_INTEGRATED.py"
