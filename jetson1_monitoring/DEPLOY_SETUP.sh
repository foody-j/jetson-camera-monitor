#!/bin/bash
# Jetson Orin Nano 자동 배포 스크립트
# JETSON1_INTEGRATED.py 배포용

set -e  # Exit on error

echo "=========================================="
echo "Jetson Orin Nano 배포 설정 시작"
echo "=========================================="

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. 시스템 업데이트
echo -e "${YELLOW}[1/7] 시스템 업데이트 중...${NC}"
sudo apt update
sudo apt upgrade -y

# 2. 한글 지원 설치
echo -e "${YELLOW}[2/7] 한글 폰트 및 로케일 설치 중...${NC}"
sudo apt install -y fonts-nanum fonts-nanum-coding fonts-nanum-extra
sudo apt install -y language-pack-ko
sudo locale-gen ko_KR.UTF-8
sudo update-locale LANG=ko_KR.UTF-8 LC_MESSAGES=POSIX

echo -e "${GREEN}한글 지원 설치 완료!${NC}"
echo "로케일 확인:"
locale | grep LANG

# 3. Python 기본 패키지 설치
echo -e "${YELLOW}[3/7] Python 기본 패키지 설치 중...${NC}"
sudo apt install -y python3-pip python3-tk python3-pil python3-pil.imagetk

# 4. GStreamer 패키지 설치 (GMSL 카메라용)
echo -e "${YELLOW}[4/7] GStreamer 패키지 설치 중...${NC}"
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0
sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
sudo apt install -y v4l-utils

# 5. Python 라이브러리 설치
echo -e "${YELLOW}[5/7] Python 라이브러리 설치 중...${NC}"

# OpenCV (Jetson에 이미 설치되어 있을 수 있음)
python3 -c "import cv2" 2>/dev/null && echo "OpenCV 이미 설치됨" || pip3 install opencv-python

# MQTT
pip3 install paho-mqtt

# Pillow (이미지 처리)
pip3 install Pillow

# Ultralytics YOLO
pip3 install ultralytics

# NumPy (이미 설치되어 있을 수 있음)
python3 -c "import numpy" 2>/dev/null && echo "NumPy 이미 설치됨" || pip3 install numpy

echo -e "${GREEN}Python 라이브러리 설치 완료!${NC}"

# 6. 프로젝트 디렉토리 권한 설정
echo -e "${YELLOW}[6/7] 프로젝트 디렉토리 권한 설정 중...${NC}"

# 데이터 저장 디렉토리 생성 (홈 디렉토리에)
mkdir -p ~/StirFry_Data/left
mkdir -p ~/StirFry_Data/right
mkdir -p ~/Detection

echo -e "${GREEN}디렉토리 생성 완료:${NC}"
echo "  - ~/StirFry_Data/left"
echo "  - ~/StirFry_Data/right"
echo "  - ~/Detection"

# 7. GMSL 드라이버 확인
echo -e "${YELLOW}[7/7] GMSL 드라이버 확인 중...${NC}"

GMSL_DRIVER_DIR="/home/$USER/jetson-camera-monitor/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3"

if [ -d "$GMSL_DRIVER_DIR/ko" ]; then
    echo -e "${GREEN}GMSL 드라이버 디렉토리 발견: $GMSL_DRIVER_DIR${NC}"

    # 드라이버 파일 확인
    if [ -f "$GMSL_DRIVER_DIR/ko/max96712.ko" ] && [ -f "$GMSL_DRIVER_DIR/ko/sgx-yuv-gmsl2.ko" ]; then
        echo -e "${GREEN}GMSL 드라이버 파일 확인 완료!${NC}"
    else
        echo -e "${RED}경고: GMSL 드라이버 파일(.ko)이 없습니다!${NC}"
    fi
else
    echo -e "${RED}경고: GMSL 드라이버 디렉토리를 찾을 수 없습니다!${NC}"
    echo "예상 경로: $GMSL_DRIVER_DIR"
fi

# 카메라 디바이스 확인
echo ""
echo "카메라 디바이스 확인:"
ls -la /dev/video* 2>/dev/null || echo "카메라 디바이스가 없습니다. 드라이버를 로드하세요."

echo ""
echo "=========================================="
echo -e "${GREEN}배포 설정 완료!${NC}"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. YOLO 모델 다운로드:"
echo "   cd ~/jetson-camera-monitor/autostart_autodown"
echo "   python3 -c 'from ultralytics import YOLO; YOLO(\"yolo11n.pt\")'"
echo ""
echo "2. config.json 설정 확인"
echo "   - 카메라 인덱스"
echo "   - GMSL 드라이버 경로"
echo "   - MQTT 설정"
echo ""
echo "3. 프로그램 실행:"
echo "   cd ~/jetson-camera-monitor/autostart_autodown"
echo "   python3 JETSON1_INTEGRATED.py"
echo ""
echo -e "${YELLOW}참고: 로케일 변경 사항을 적용하려면 재부팅이 필요할 수 있습니다.${NC}"
