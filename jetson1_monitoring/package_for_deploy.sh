#!/bin/bash
# 배포용 패키지 생성 스크립트
# 새 Jetson에 복사할 최소 파일만 압축

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "배포 패키지 생성 중..."
echo "=========================================="

# 출력 파일명
OUTPUT_FILE="jetson-camera-deploy-$(date +%Y%m%d_%H%M%S).zip"

echo "프로젝트 루트: $PROJECT_ROOT"
echo "출력 파일: $OUTPUT_FILE"
echo ""

cd "$PROJECT_ROOT/.."

# 필수 파일만 압축
echo "파일 압축 중..."
zip -r "$OUTPUT_FILE" \
  jetson-camera-monitor/autostart_autodown \
  jetson-camera-monitor/src \
  jetson-camera-monitor/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3 \
  -x '*.pyc' '*__pycache__*' '*.git*' '*.backup' '*_backup_*'

# 파일 크기 확인
SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)

echo ""
echo "=========================================="
echo "✅ 배포 패키지 생성 완료!"
echo "=========================================="
echo "파일: $OUTPUT_FILE"
echo "크기: $SIZE"
echo ""
echo "포함된 내용:"
echo "  - autostart_autodown/ (메인 프로그램)"
echo "  - src/ (공통 라이브러리)"
echo "  - SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/ (GMSL 드라이버)"
echo ""
echo "=========================================="
echo "새 Jetson에서 실행:"
echo "=========================================="
echo "1. 파일 전송 (USB 또는 SCP)"
echo "   scp $OUTPUT_FILE user@NEW_JETSON:~/"
echo ""
echo "2. 압축 해제"
echo "   cd ~"
echo "   unzip $OUTPUT_FILE"
echo ""
echo "3. 자동 설치"
echo "   cd ~/jetson-camera-monitor/autostart_autodown"
echo "   ./DEPLOY_SETUP.sh"
echo ""
echo "4. 실행"
echo "   python3 JETSON1_INTEGRATED.py"
echo "=========================================="
