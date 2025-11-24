#!/bin/bash
# Jetson 모니터링 시스템 자동 시작 설치 스크립트

echo "===== Jetson 모니터링 자동 시작 설치 ====="

# 현재 디렉토리
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Jetson 타입 선택
echo ""
echo "어떤 Jetson 시스템을 설치하시겠습니까?"
echo "1) Jetson #1 (볶음 모니터링 - JETSON1_INTEGRATED.py)"
echo "2) Jetson #2 (튀김 AI - JETSON2_INTEGRATED.py)"
read -p "선택 (1 또는 2): " JETSON_TYPE

if [ "$JETSON_TYPE" == "1" ]; then
    PYTHON_SCRIPT="$SCRIPT_DIR/jetson1_monitoring/JETSON1_INTEGRATED.py"
    SERVICE_NAME="jetson1-monitor"
    DESCRIPTION="Jetson #1 Monitoring System (StirFry + Person Detection)"
    echo "Jetson #1 (볶음 모니터링) 선택됨"
elif [ "$JETSON_TYPE" == "2" ]; then
    PYTHON_SCRIPT="$SCRIPT_DIR/jetson2_frying_ai/JETSON2_INTEGRATED.py"
    SERVICE_NAME="jetson2-monitor"
    DESCRIPTION="Jetson #2 AI System (Frying + Bucket Detection)"
    echo "Jetson #2 (튀김 AI) 선택됨"
else
    echo "잘못된 선택입니다. 1 또는 2를 입력하세요."
    exit 1
fi

# Python 스크립트 존재 확인
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: Python 스크립트를 찾을 수 없습니다: $PYTHON_SCRIPT"
    exit 1
fi

# systemd 서비스 파일 생성
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

echo ""
echo "서비스 파일 생성 중: $SERVICE_FILE"

# sudo로 실행 시 실제 사용자 확인
REAL_USER=${SUDO_USER:-$USER}

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=$DESCRIPTION
After=multi-user.target gmsl-driver-load.service graphical.target
Wants=network-online.target
Requires=gmsl-driver-load.service

[Service]
Type=simple
User=$REAL_USER
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$REAL_USER/.Xauthority"
Environment="HOME=/home/$REAL_USER"
Environment="PYTHONPATH=/home/$REAL_USER/.local/lib/python3.10/site-packages"
WorkingDirectory=$(dirname $PYTHON_SCRIPT)
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 $PYTHON_SCRIPT
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

# 사용자를 video 그룹에 추가 (카메라 접근)
sudo usermod -a -G video $REAL_USER
sudo usermod -a -G dialout $REAL_USER

# systemd 리로드
echo "systemd 데몬 리로드..."
sudo systemctl daemon-reload

# 서비스 활성화
echo "서비스 활성화..."
sudo systemctl enable $SERVICE_NAME.service

echo ""
echo "===== 설치 완료 ====="
echo "재부팅 시 자동으로 실행됩니다."
echo ""
echo "실행 순서:"
echo "  1. GMSL 카메라 초기화 (gmsl-driver-load.service)"
echo "     - 커널 모듈 로드 + 4개 카메라 1920x1536 설정"
echo "  2. 5초 대기"
echo "  3. $SERVICE_NAME 시작"
echo ""
echo "서비스 관리 명령어:"
echo "  상태 확인: sudo systemctl status $SERVICE_NAME"
echo "  로그 확인: sudo journalctl -u $SERVICE_NAME -f"
echo "  수동 시작: sudo systemctl start $SERVICE_NAME"
echo "  수동 중지: sudo systemctl stop $SERVICE_NAME"
echo "  비활성화: sudo systemctl disable $SERVICE_NAME"
echo ""
echo "지금 테스트하시겠습니까? (y/n)"
read -p "> " TEST

if [ "$TEST" == "y" ] || [ "$TEST" == "Y" ]; then
    echo ""
    echo "서비스 시작 중..."
    sudo systemctl start $SERVICE_NAME
    sleep 3
    echo ""
    sudo systemctl status $SERVICE_NAME --no-pager
fi
