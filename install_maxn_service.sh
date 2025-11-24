#!/bin/bash
# 부팅 시 자동으로 MAXN_SUPER 모드 설정 서비스 설치

echo "=================================================="
echo "MAXN_SUPER 자동 설정 서비스 설치"
echo "=================================================="

# 서비스 파일 복사
echo "[1/4] 서비스 파일 복사 중..."
sudo cp jetson-maxn.service /etc/systemd/system/

# systemd 리로드
echo "[2/4] systemd 리로드 중..."
sudo systemctl daemon-reload

# 서비스 활성화
echo "[3/4] 서비스 활성화 중..."
sudo systemctl enable jetson-maxn.service

# 즉시 적용 (재부팅 없이)
echo "[4/4] MAXN 모드 즉시 적용 중..."
sudo systemctl start jetson-maxn.service

echo ""
echo "=================================================="
echo "✅ 설치 완료!"
echo "=================================================="
echo ""
echo "📋 서비스 상태 확인:"
sudo systemctl status jetson-maxn.service --no-pager

echo ""
echo "💡 유용한 명령어:"
echo "  - 서비스 상태 확인: sudo systemctl status jetson-maxn"
echo "  - 서비스 비활성화: sudo systemctl disable jetson-maxn"
echo "  - 현재 모드 확인: sudo nvpmodel -q"
echo ""
