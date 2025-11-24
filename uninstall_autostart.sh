#!/bin/bash
# Jetson 모니터링 자동 시작 제거 스크립트

echo "===== Jetson 모니터링 자동 시작 제거 ====="

# 서비스 확인
echo ""
echo "설치된 서비스 확인 중..."

SERVICES=()
if systemctl list-unit-files | grep -q "jetson1-monitor.service"; then
    SERVICES+=("jetson1-monitor")
fi
if systemctl list-unit-files | grep -q "jetson2-monitor.service"; then
    SERVICES+=("jetson2-monitor")
fi

if [ ${#SERVICES[@]} -eq 0 ]; then
    echo "설치된 Jetson 모니터링 서비스가 없습니다."
    exit 0
fi

echo "발견된 서비스:"
for service in "${SERVICES[@]}"; do
    echo "  - $service"
done

echo ""
read -p "위 서비스들을 모두 제거하시겠습니까? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "취소되었습니다."
    exit 0
fi

# 각 서비스 제거
for service in "${SERVICES[@]}"; do
    echo ""
    echo "[$service] 중지 중..."
    sudo systemctl stop $service.service

    echo "[$service] 비활성화 중..."
    sudo systemctl disable $service.service

    echo "[$service] 서비스 파일 삭제 중..."
    sudo rm -f /etc/systemd/system/$service.service
done

# systemd 리로드
echo ""
echo "systemd 데몬 리로드..."
sudo systemctl daemon-reload

echo ""
echo "===== 제거 완료 ====="
echo "자동 시작이 비활성화되었습니다."
echo ""
echo "수동 실행 방법:"
echo "  Jetson1: cd ~/jetson-food-ai/jetson1_monitoring && python3 JETSON1_INTEGRATED.py"
echo "  Jetson2: cd ~/jetson-food-ai/jetson2_frying_ai && python3 JETSON2_INTEGRATED.py"
