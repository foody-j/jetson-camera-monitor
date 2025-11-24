#!/bin/bash
# 오프라인 배포 패키지 생성 스크립트
# WiFi 없는 환경에서도 설치 가능하도록 모든 것을 포함

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "오프라인 배포 패키지 생성 중..."
echo "=========================================="

# 출력 파일명
OUTPUT_FILE="jetson-camera-offline-$(date +%Y%m%d_%H%M%S).zip"
TEMP_DIR="/tmp/jetson-offline-package"

echo "프로젝트 루트: $PROJECT_ROOT"
echo "임시 디렉토리: $TEMP_DIR"
echo "출력 파일: $OUTPUT_FILE"
echo ""

# 임시 디렉토리 생성
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# 1. 프로젝트 파일 복사
echo "[1/4] 프로젝트 파일 복사 중..."
mkdir -p "$TEMP_DIR/jetson-camera-monitor"
cp -r "$PROJECT_ROOT/autostart_autodown" "$TEMP_DIR/jetson-camera-monitor/"
cp -r "$PROJECT_ROOT/src" "$TEMP_DIR/jetson-camera-monitor/"
cp -r "$PROJECT_ROOT/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3" "$TEMP_DIR/jetson-camera-monitor/"

# Python 캐시 파일 제거
find "$TEMP_DIR/jetson-camera-monitor" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR/jetson-camera-monitor" -type f -name "*.pyc" -delete 2>/dev/null || true

echo "✓ 프로젝트 파일 복사 완료"

# 2. Python 패키지 복사 (site-packages)
echo "[2/4] Python 패키지 복사 중..."
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
USER_SITE_PACKAGES="$HOME/.local/lib/python${PYTHON_VERSION}/site-packages"

if [ -d "$USER_SITE_PACKAGES" ]; then
    mkdir -p "$TEMP_DIR/python_packages"

    # 필수 패키지만 복사 (ultralytics는 크므로 전체 복사)
    echo "  - paho-mqtt 복사 중..."
    cp -r "$USER_SITE_PACKAGES"/paho* "$TEMP_DIR/python_packages/" 2>/dev/null || echo "    (paho-mqtt 없음, 건너뜀)"

    echo "  - PIL/Pillow 복사 중..."
    cp -r "$USER_SITE_PACKAGES"/PIL* "$TEMP_DIR/python_packages/" 2>/dev/null || echo "    (Pillow 없음, 건너뜀)"

    echo "  - ultralytics 복사 중... (크기가 크므로 시간이 걸립니다)"
    cp -r "$USER_SITE_PACKAGES"/ultralytics* "$TEMP_DIR/python_packages/" 2>/dev/null || echo "    (ultralytics 없음, 건너뜀)"

    echo "  - numpy 복사 중..."
    cp -r "$USER_SITE_PACKAGES"/numpy* "$TEMP_DIR/python_packages/" 2>/dev/null || echo "    (numpy 없음, 건너뜀)"

    echo "  - 기타 의존성 복사 중..."
    # ultralytics 의존성들
    cp -r "$USER_SITE_PACKAGES"/torch* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/torchvision* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/yaml* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/tqdm* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/matplotlib* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/scipy* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/pandas* "$TEMP_DIR/python_packages/" 2>/dev/null || true
    cp -r "$USER_SITE_PACKAGES"/seaborn* "$TEMP_DIR/python_packages/" 2>/dev/null || true

    # .dist-info 디렉토리도 복사 (패키지 정보)
    cp -r "$USER_SITE_PACKAGES"/*.dist-info "$TEMP_DIR/python_packages/" 2>/dev/null || true

    echo "✓ Python 패키지 복사 완료"
else
    echo "⚠ 경고: $USER_SITE_PACKAGES 디렉토리가 없습니다!"
fi

# 3. YOLO 모델 파일 복사
echo "[3/4] YOLO 모델 파일 복사 중..."
YOLO_MODEL="$PROJECT_ROOT/autostart_autodown/yolo11n.pt"

if [ -f "$YOLO_MODEL" ]; then
    cp "$YOLO_MODEL" "$TEMP_DIR/jetson-camera-monitor/autostart_autodown/"
    echo "✓ YOLO 모델 파일 복사 완료"
else
    echo "⚠ 경고: YOLO 모델 파일이 없습니다!"
    echo "  다음 명령으로 다운로드하세요:"
    echo "  python3 -c 'from ultralytics import YOLO; YOLO(\"yolo11n.pt\")'"
fi

# 4. 오프라인 설치 스크립트 생성
echo "[4/4] 오프라인 설치 스크립트 생성 중..."
cat > "$TEMP_DIR/OFFLINE_INSTALL.sh" << 'OFFLINE_SCRIPT'
#!/bin/bash
# 오프라인 설치 스크립트
# WiFi 없이 설치 가능

set -e

echo "=========================================="
echo "Jetson 오프라인 배포 설치 시작"
echo "=========================================="

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

INSTALL_DIR="$HOME/jetson-camera-monitor"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
USER_SITE_PACKAGES="$HOME/.local/lib/python${PYTHON_VERSION}/site-packages"

# 1. 프로젝트 파일 복사
echo -e "${YELLOW}[1/5] 프로젝트 파일 복사 중...${NC}"
mkdir -p "$INSTALL_DIR"
cp -r jetson-camera-monitor/* "$INSTALL_DIR/"
echo -e "${GREEN}✓ 프로젝트 파일 복사 완료${NC}"

# 2. Python 패키지 설치
echo -e "${YELLOW}[2/5] Python 패키지 설치 중...${NC}"
if [ -d "python_packages" ]; then
    mkdir -p "$USER_SITE_PACKAGES"
    cp -r python_packages/* "$USER_SITE_PACKAGES/"
    echo -e "${GREEN}✓ Python 패키지 설치 완료${NC}"
else
    echo -e "${RED}⚠ python_packages 디렉토리가 없습니다!${NC}"
fi

# 3. 시스템 패키지 확인 (인터넷 불필요)
echo -e "${YELLOW}[3/5] 시스템 패키지 확인 중...${NC}"
echo "다음 시스템 패키지가 필요합니다 (JetPack에 대부분 포함됨):"
echo "  - python3-gi (GStreamer 바인딩)"
echo "  - python3-pil (PIL/Pillow)"
echo "  - gstreamer1.0-tools"
echo "  - v4l-utils"
echo ""
echo "만약 누락된 패키지가 있다면, WiFi 연결 후:"
echo "  sudo apt install python3-gi python3-pil gstreamer1.0-tools v4l-utils"
echo ""

# 4. 데이터 디렉토리 생성
echo -e "${YELLOW}[4/5] 데이터 디렉토리 생성 중...${NC}"
mkdir -p ~/StirFry_Data/left
mkdir -p ~/StirFry_Data/right
mkdir -p ~/Detection
chmod -R 755 ~/StirFry_Data ~/Detection
echo -e "${GREEN}✓ 데이터 디렉토리 생성 완료${NC}"

# 5. GMSL 드라이버 확인
echo -e "${YELLOW}[5/5] GMSL 드라이버 확인 중...${NC}"
GMSL_DRIVER_DIR="$INSTALL_DIR/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3"

if [ -d "$GMSL_DRIVER_DIR/ko" ]; then
    echo -e "${GREEN}✓ GMSL 드라이버 디렉토리 발견${NC}"
    if [ -f "$GMSL_DRIVER_DIR/ko/max96712.ko" ] && [ -f "$GMSL_DRIVER_DIR/ko/sgx-yuv-gmsl2.ko" ]; then
        echo -e "${GREEN}✓ GMSL 드라이버 파일 확인 완료${NC}"
    else
        echo -e "${RED}⚠ 드라이버 파일이 없습니다!${NC}"
    fi
else
    echo -e "${RED}⚠ GMSL 드라이버 디렉토리를 찾을 수 없습니다!${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}오프라인 설치 완료!${NC}"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. config.json 확인 및 수정 (필요시)"
echo "   nano $INSTALL_DIR/autostart_autodown/config.json"
echo ""
echo "2. 프로그램 실행"
echo "   cd $INSTALL_DIR/autostart_autodown"
echo "   python3 JETSON1_INTEGRATED.py"
echo ""
echo "3. 간단한 3-카메라 테스트"
echo "   python3 JETSON1_INTEGRATED_v2.py"
echo ""
OFFLINE_SCRIPT

chmod +x "$TEMP_DIR/OFFLINE_INSTALL.sh"
echo "✓ 오프라인 설치 스크립트 생성 완료"

# README 파일 생성
cat > "$TEMP_DIR/README.txt" << 'README'
===================================================
Jetson Camera Monitor - 오프라인 배포 패키지
===================================================

이 패키지는 WiFi 없는 환경에서 설치할 수 있도록
모든 필요한 파일을 포함하고 있습니다.

■ 설치 방법:

1. USB에서 이 ZIP 파일을 Jetson으로 복사
2. 압축 해제
   cd ~
   unzip jetson-camera-offline-YYYYMMDD_HHMMSS.zip

3. 설치 스크립트 실행
   cd jetson-camera-offline-YYYYMMDD_HHMMSS
   ./OFFLINE_INSTALL.sh

4. 프로그램 실행
   cd ~/jetson-camera-monitor/autostart_autodown
   python3 JETSON1_INTEGRATED.py

■ 포함된 내용:
  - jetson-camera-monitor/ (프로젝트 파일)
  - python_packages/ (Python 라이브러리)
  - OFFLINE_INSTALL.sh (설치 스크립트)
  - README.txt (이 파일)

■ 시스템 요구사항:
  - Jetson Orin Nano
  - JetPack 6.2
  - L4T 36.4.3

■ 주의사항:
  - JetPack SDK가 설치되어 있어야 합니다
  - GStreamer, Python3는 JetPack에 포함되어 있습니다

===================================================
README

echo "✓ README 파일 생성 완료"

# ZIP 파일 생성
echo ""
echo "ZIP 파일 생성 중..."
cd /tmp
zip -r "$OUTPUT_FILE" jetson-offline-package/ \
  -x '*__pycache__*' '*.pyc' '*.git*' > /dev/null

# 원래 디렉토리로 이동
mv "$OUTPUT_FILE" "$PROJECT_ROOT/.."
cd "$PROJECT_ROOT/.."

# 임시 디렉토리 삭제
rm -rf "$TEMP_DIR"

# 파일 크기 확인
SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)

echo ""
echo "=========================================="
echo "✅ 오프라인 배포 패키지 생성 완료!"
echo "=========================================="
echo "파일: $OUTPUT_FILE"
echo "크기: $SIZE"
echo ""
echo "포함된 내용:"
echo "  - jetson-camera-monitor/ (프로젝트)"
echo "  - python_packages/ (Python 라이브러리)"
echo "  - OFFLINE_INSTALL.sh (설치 스크립트)"
echo "  - README.txt (설명서)"
echo ""
echo "=========================================="
echo "새 Jetson에서 설치:"
echo "=========================================="
echo "1. USB로 파일 복사"
echo ""
echo "2. 압축 해제"
echo "   cd ~"
echo "   unzip $OUTPUT_FILE"
echo ""
echo "3. 설치"
echo "   cd jetson-offline-package-*"
echo "   ./OFFLINE_INSTALL.sh"
echo ""
echo "4. 실행"
echo "   cd ~/jetson-camera-monitor/autostart_autodown"
echo "   python3 JETSON1_INTEGRATED.py"
echo "=========================================="
