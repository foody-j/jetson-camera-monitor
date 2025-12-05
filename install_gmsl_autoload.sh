#!/bin/bash
# GMSL 카메라 자동 초기화 서비스 설치 스크립트

echo "===== GMSL 카메라 자동 초기화 서비스 설치 ====="

# 현재 디렉토리
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INIT_SCRIPT="$SCRIPT_DIR/init_gmsl_cameras.sh"

# 실행 권한 부여
chmod +x $INIT_SCRIPT

# systemd 서비스 파일 생성
SERVICE_FILE="/etc/systemd/system/gmsl-driver-load.service"

echo "서비스 파일 생성 중: $SERVICE_FILE"

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=GMSL Camera Initialization (Driver Load + Camera Setup)
After=multi-user.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$INIT_SCRIPT
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# systemd 리로드
echo "systemd 데몬 리로드..."
sudo systemctl daemon-reload

# 서비스 활성화
echo "서비스 활성화..."
sudo systemctl enable gmsl-driver-load.service

# 서비스 시작
echo "서비스 시작..."
sudo systemctl start gmsl-driver-load.service

# 상태 확인
echo ""
echo "===== 서비스 상태 ====="
sudo systemctl status gmsl-driver-load.service --no-pager

echo ""
echo "===== 설치 완료 ====="
echo "재부팅 시 자동으로 GMSL 카메라가 초기화됩니다."
echo "(커널 모듈 로드 + 4개 카메라 1920x1536 설정)"
echo ""
echo "서비스 관리 명령어:"
echo "  상태 확인: sudo systemctl status gmsl-driver-load"
echo "  로그 확인: sudo journalctl -u gmsl-driver-load"
echo "  수동 시작: sudo systemctl start gmsl-driver-load"
echo "  비활성화: sudo systemctl disable gmsl-driver-load"
