#!/bin/bash
# Jetson Web Dashboard 서비스 설치 스크립트 (대화식)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 현재 사용자 및 경로 자동 감지
CURRENT_USER="$USER"
CURRENT_HOME="$HOME"
PYTHON3_PATH="$(which python3)"

echo "=========================================="
echo "Jetson Web Dashboard 서비스 설치"
echo "=========================================="
echo ""
echo "설치할 Jetson을 선택하세요:"
echo "  [1] Jetson #1 (사람 감지 + 볶음 모니터링)"
echo "  [2] Jetson #2 (튀김 AI + 바켓 감지)"
echo ""
read -p "선택 (1 또는 2): " JETSON_NUM

case $JETSON_NUM in
    1)
        JETSON_NAME="jetson1"
        SERVICE_NAME="jetson1-web.service"
        WORK_DIR="$SCRIPT_DIR/jetson1_monitoring"
        MAIN_SCRIPT="JETSON1_web.py"
        DESCRIPTION="Jetson #1 Web Dashboard (FastAPI + YOLO Detection)"
        ;;
    2)
        JETSON_NAME="jetson2"
        SERVICE_NAME="jetson2-web.service"
        WORK_DIR="$SCRIPT_DIR/jetson2_frying_ai"
        MAIN_SCRIPT="JETSON2_web.py"
        DESCRIPTION="Jetson #2 Web Dashboard (FastAPI + Frying AI + Bucket Detection)"
        ;;
    *)
        echo "ERROR: 1 또는 2를 입력하세요!"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "선택: Jetson #$JETSON_NUM"
echo "=========================================="
echo "사용자: $CURRENT_USER"
echo "홈 디렉토리: $CURRENT_HOME"
echo "Python3: $PYTHON3_PATH"
echo "프로젝트 경로: $SCRIPT_DIR"
echo "작업 디렉토리: $WORK_DIR"
echo ""

# 1. 기존 서비스 중지
echo "[1] 기존 서비스 중지..."
sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
sudo systemctl stop ${JETSON_NAME}-web-restart.timer 2>/dev/null || true
sudo systemctl disable $SERVICE_NAME 2>/dev/null || true
sudo systemctl disable ${JETSON_NAME}-web-restart.timer 2>/dev/null || true

# 2. 서비스 파일 동적 생성
echo ""
echo "[2] 서비스 파일 생성..."

# Main Web Service
cat > /tmp/$SERVICE_NAME << EOF
[Unit]
Description=$DESCRIPTION
After=multi-user.target graphical.target network-online.target
Wants=network-online.target gmsl-driver-load.service

[Service]
Type=simple
User=$CURRENT_USER
Environment="DISPLAY=:0"
Environment="XAUTHORITY=$CURRENT_HOME/.Xauthority"
Environment="HOME=$CURRENT_HOME"
Environment="PYTHONPATH=$CURRENT_HOME/.local/lib/python3.10/site-packages"
WorkingDirectory=$WORK_DIR
ExecStartPre=/bin/sleep 5
ExecStart=$PYTHON3_PATH $WORK_DIR/$MAIN_SCRIPT
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

# Restart Service
cat > /tmp/${JETSON_NAME}-web-restart.service << EOF
[Unit]
Description=Restart $DESCRIPTION (daily at 2 AM)
After=$SERVICE_NAME

[Service]
Type=oneshot
ExecStart=/bin/systemctl restart $SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

# Restart Timer
cat > /tmp/${JETSON_NAME}-web-restart.timer << EOF
[Unit]
Description=Daily restart timer for $DESCRIPTION (2 AM)

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 3. 서비스 파일 복사
echo ""
echo "[3] 서비스 + 타이머 파일 복사..."
sudo cp /tmp/$SERVICE_NAME /etc/systemd/system/
sudo cp /tmp/${JETSON_NAME}-web-restart.service /etc/systemd/system/
sudo cp /tmp/${JETSON_NAME}-web-restart.timer /etc/systemd/system/

# 4. 권한 설정
echo ""
echo "[4] 권한 설정..."
sudo chmod 644 /etc/systemd/system/$SERVICE_NAME
sudo chmod 644 /etc/systemd/system/${JETSON_NAME}-web-restart.service
sudo chmod 644 /etc/systemd/system/${JETSON_NAME}-web-restart.timer

# 5. systemd 리로드
echo ""
echo "[5] systemd 리로드..."
sudo systemctl daemon-reload

# 6. 서비스 + 타이머 활성화
echo ""
echo "[6] 서비스 + 타이머 활성화..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl enable ${JETSON_NAME}-web-restart.timer

# 7. 서비스 + 타이머 시작
echo ""
echo "[7] 서비스 + 타이머 시작..."
sudo systemctl start $SERVICE_NAME
sudo systemctl start ${JETSON_NAME}-web-restart.timer

# 8. 상태 확인
echo ""
echo "=========================================="
echo "서비스 상태 확인"
echo "=========================================="
echo ""
sudo systemctl status $SERVICE_NAME --no-pager -l

echo ""
echo "=========================================="
echo "타이머 상태 확인"
echo "=========================================="
sudo systemctl list-timers ${JETSON_NAME}-web-restart.timer --no-pager

echo ""
echo "=========================================="
echo "설치 완료!"
echo "=========================================="
echo ""
echo "메인 서비스:"
echo "  로그 확인: sudo journalctl -u ${JETSON_NAME}-web -f"
echo "  재시작:   sudo systemctl restart ${JETSON_NAME}-web"
echo "  중지:     sudo systemctl stop ${JETSON_NAME}-web"
echo ""
echo "자동 재시작 타이머:"
echo "  타이머 확인: systemctl list-timers"
echo "  타이머 중지: sudo systemctl stop ${JETSON_NAME}-web-restart.timer"
echo "  재시작 로그: sudo journalctl -u ${JETSON_NAME}-web-restart.service"
echo ""
echo "현재 설정:"
echo "  Jetson: #$JETSON_NUM"
echo "  사용자: $CURRENT_USER"
echo "  경로: $SCRIPT_DIR"
echo "  자동 재시작: 매일 새벽 2시"
echo ""
