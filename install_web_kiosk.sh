#!/bin/bash
# Install Jetson web dashboard for field deployment:
# - systemd service for backend
# - desktop autostart for Firefox
# - optional auto-login for gdm3/lightdm

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$CURRENT_USER")"
PYTHON3_PATH="$(command -v python3)"
AUTOSTART_DIR="$USER_HOME/.config/autostart"
LOCAL_BIN_DIR="$USER_HOME/.local/bin"

if [[ -z "${PYTHON3_PATH:-}" ]]; then
    echo "ERROR: python3 not found"
    exit 1
fi

echo "=========================================="
echo "Jetson Web Kiosk Installer"
echo "=========================================="
echo ""
echo "설치할 Jetson을 선택하세요:"
echo "  [1] Jetson #1 Web Dashboard"
echo "  [2] Jetson #2 Web Dashboard"
echo ""
read -r -p "선택 (1 또는 2): " JETSON_NUM

case "$JETSON_NUM" in
    1)
        JETSON_NAME="jetson1"
        SERVICE_NAME="jetson1-web.service"
        WORK_DIR="$SCRIPT_DIR/jetson1_monitoring"
        MAIN_SCRIPT="JETSON1_web.py"
        DESCRIPTION="Jetson #1 Web Dashboard (FastAPI + YOLO Detection)"
        DEFAULT_PORT="7000"
        ;;
    2)
        JETSON_NAME="jetson2"
        SERVICE_NAME="jetson2-web.service"
        WORK_DIR="$SCRIPT_DIR/jetson2_frying_ai"
        MAIN_SCRIPT="JETSON2_web.py"
        DESCRIPTION="Jetson #2 Web Dashboard (FastAPI + Frying AI + Bucket Detection)"
        DEFAULT_PORT="8000"
        ;;
    *)
        echo "ERROR: 1 또는 2를 입력하세요."
        exit 1
        ;;
esac

URL="http://127.0.0.1:${DEFAULT_PORT}"
LAUNCHER_SCRIPT="$LOCAL_BIN_DIR/${JETSON_NAME}-launch-firefox.sh"
DESKTOP_FILE="$AUTOSTART_DIR/${JETSON_NAME}-web-browser.desktop"
AUTLOGIN_SERVICE=""

echo ""
echo "설정 정보"
echo "  User: $CURRENT_USER"
echo "  Home: $USER_HOME"
echo "  Work dir: $WORK_DIR"
echo "  Backend: $MAIN_SCRIPT"
echo "  URL: $URL"
echo ""

mkdir -p "$AUTOSTART_DIR"
mkdir -p "$LOCAL_BIN_DIR"

if [[ ! -f "$WORK_DIR/$MAIN_SCRIPT" ]]; then
    echo "ERROR: main script not found: $WORK_DIR/$MAIN_SCRIPT"
    exit 1
fi

if ! command -v firefox >/dev/null 2>&1; then
    echo "ERROR: firefox not found. Install Firefox first."
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl not found. Install curl first."
    exit 1
fi

echo "[1/5] 기존 서비스 중지..."
sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl stop "${JETSON_NAME}-web-restart.timer" 2>/dev/null || true
sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl disable "${JETSON_NAME}-web-restart.timer" 2>/dev/null || true

echo "[2/5] systemd 서비스 설치..."
sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null <<EOF
[Unit]
Description=$DESCRIPTION
After=multi-user.target graphical.target network-online.target
Wants=network-online.target gmsl-driver-load.service

[Service]
Type=simple
User=$CURRENT_USER
Environment="DISPLAY=:0"
Environment="XAUTHORITY=$USER_HOME/.Xauthority"
Environment="HOME=$USER_HOME"
Environment="PYTHONPATH=$USER_HOME/.local/lib/python3.10/site-packages"
Environment="PYTHONUNBUFFERED=1"
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

sudo tee "/etc/systemd/system/${JETSON_NAME}-web-restart.service" >/dev/null <<EOF
[Unit]
Description=Restart $DESCRIPTION (daily at 2 AM)
After=$SERVICE_NAME

[Service]
Type=oneshot
ExecStart=/bin/systemctl restart $SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

sudo tee "/etc/systemd/system/${JETSON_NAME}-web-restart.timer" >/dev/null <<EOF
[Unit]
Description=Daily restart timer for $DESCRIPTION (2 AM)

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "[3/5] Firefox 자동실행 스크립트 설치..."
cat > "$LAUNCHER_SCRIPT" <<EOF
#!/bin/bash
set -euo pipefail

URL="$URL"
WAIT_SECONDS=180
PROFILE_DIR="\$HOME/.mozilla/firefox"

if [[ ! -d "\$PROFILE_DIR" ]]; then
    mkdir -p "\$PROFILE_DIR"
fi

for ((i=1; i<=WAIT_SECONDS; i++)); do
    if curl -fsS "\$URL" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -fsS "\$URL" >/dev/null 2>&1; then
    exit 1
fi

if pgrep -x firefox >/dev/null 2>&1; then
    firefox --new-window "\$URL" >/dev/null 2>&1 &
else
    firefox --kiosk "\$URL" >/dev/null 2>&1 &
fi
EOF
chmod 755 "$LAUNCHER_SCRIPT"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${JETSON_NAME^} Web Browser
Comment=Open the local Jetson web dashboard after boot
Exec=$LAUNCHER_SCRIPT
Path=$SCRIPT_DIR
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=15
EOF
chmod 644 "$DESKTOP_FILE"

echo "[4/5] 자동 로그인 설정..."
if systemctl list-unit-files | grep -q '^gdm3\.service'; then
    sudo mkdir -p /etc/gdm3
    sudo tee /etc/gdm3/custom.conf >/dev/null <<EOF
[daemon]
AutomaticLoginEnable=true
AutomaticLogin=$CURRENT_USER
EOF
    AUTLOGIN_SERVICE="gdm3"
elif systemctl list-unit-files | grep -q '^lightdm\.service'; then
    sudo mkdir -p /etc/lightdm
    sudo tee /etc/lightdm/lightdm.conf >/dev/null <<EOF
[Seat:*]
autologin-user=$CURRENT_USER
autologin-user-timeout=0
user-session=ubuntu
greeter-hide-users=false
EOF
    AUTLOGIN_SERVICE="lightdm"
else
    echo "WARNING: gdm3/lightdm을 찾지 못했습니다. 자동 로그인은 수동 설정이 필요합니다."
fi

echo "[5/5] 서비스 활성화..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl enable "${JETSON_NAME}-web-restart.timer"
sudo systemctl start "$SERVICE_NAME"
sudo systemctl start "${JETSON_NAME}-web-restart.timer"

echo ""
echo "=========================================="
echo "설치 완료"
echo "=========================================="
echo "Backend service: $SERVICE_NAME"
echo "Browser autostart: $DESKTOP_FILE"
if [[ -n "$AUTLOGIN_SERVICE" ]]; then
    echo "Auto-login: $AUTLOGIN_SERVICE"
else
    echo "Auto-login: not configured automatically"
fi
echo ""
echo "확인 명령어:"
echo "  sudo systemctl status $SERVICE_NAME --no-pager"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo "  ls $AUTOSTART_DIR"
echo ""
echo "재부팅 후 동작:"
echo "  1. 백엔드 서비스 자동 시작"
echo "  2. GUI 자동 로그인"
echo "  3. Firefox가 $URL 자동 오픈"
