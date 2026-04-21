#!/bin/bash
# Remove Jetson web kiosk deployment files.

set -euo pipefail

CURRENT_USER="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$CURRENT_USER")"

echo "=========================================="
echo "Jetson Web Kiosk Uninstaller"
echo "=========================================="
echo ""
echo "제거할 Jetson을 선택하세요:"
echo "  [1] Jetson #1"
echo "  [2] Jetson #2"
echo ""
read -r -p "선택 (1 또는 2): " JETSON_NUM

case "$JETSON_NUM" in
    1)
        JETSON_NAME="jetson1"
        SERVICE_NAME="jetson1-web.service"
        ;;
    2)
        JETSON_NAME="jetson2"
        SERVICE_NAME="jetson2-web.service"
        ;;
    *)
        echo "ERROR: 1 또는 2를 입력하세요."
        exit 1
        ;;
esac

DESKTOP_FILE="$USER_HOME/.config/autostart/${JETSON_NAME}-web-browser.desktop"
LAUNCHER_SCRIPT="$USER_HOME/.local/bin/${JETSON_NAME}-launch-firefox.sh"

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl stop "${JETSON_NAME}-web-restart.timer" 2>/dev/null || true
sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl disable "${JETSON_NAME}-web-restart.timer" 2>/dev/null || true

sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo rm -f "/etc/systemd/system/${JETSON_NAME}-web-restart.service"
sudo rm -f "/etc/systemd/system/${JETSON_NAME}-web-restart.timer"
sudo systemctl daemon-reload

rm -f "$DESKTOP_FILE"
rm -f "$LAUNCHER_SCRIPT"

echo ""
echo "제거 완료:"
echo "  Service: $SERVICE_NAME"
echo "  Browser autostart: $DESKTOP_FILE"
