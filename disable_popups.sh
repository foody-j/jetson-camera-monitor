#!/bin/bash
# Disable annoying popups on Jetson for production deployment

echo "=================================================="
echo "Jetson 팝업 비활성화 스크립트"
echo "=================================================="
echo ""

# 1. System Program Problem Detected 팝업 비활성화
echo "[1/3] System Program Problem Detected 팝업 비활성화 중..."
sudo systemctl stop apport.service 2>/dev/null
sudo systemctl disable apport.service 2>/dev/null
sudo systemctl mask apport.service 2>/dev/null
sudo sed -i 's/enabled=1/enabled=0/g' /etc/default/apport
echo "  ✓ apport 비활성화 완료"

# 2. 업데이트 알림 팝업 비활성화
echo "[2/3] 업데이트 알림 팝업 비활성화 중..."
gsettings set com.ubuntu.update-notifier no-show-notifications true 2>/dev/null
echo "  ✓ update-notifier 비활성화 완료"

# 3. 자동 업데이트 체크 비활성화
echo "[3/3] 자동 업데이트 체크 비활성화 중..."
if [ -f /etc/apt/apt.conf.d/20auto-upgrades ]; then
    sudo sed -i 's/APT::Periodic::Update-Package-Lists "1";/APT::Periodic::Update-Package-Lists "0";/g' /etc/apt/apt.conf.d/20auto-upgrades
    sudo sed -i 's/APT::Periodic::Unattended-Upgrade "1";/APT::Periodic::Unattended-Upgrade "0";/g' /etc/apt/apt.conf.d/20auto-upgrades
    echo "  ✓ 자동 업데이트 비활성화 완료"
else
    echo "  ⚠ /etc/apt/apt.conf.d/20auto-upgrades 파일 없음 (스킵)"
fi

echo ""
echo "=================================================="
echo "모든 팝업 비활성화 완료!"
echo "재부팅 후 적용됩니다: sudo reboot"
echo "=================================================="
