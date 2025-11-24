#!/bin/bash
# Jetson Orin Nano - MAXN_SUPER 모드 설정 스크립트
# 최대 성능 모드로 전환

echo "=================================================="
echo "Jetson Orin Nano - MAXN_SUPER 성능 모드 설정"
echo "=================================================="

# 현재 모드 확인
echo ""
echo "[1단계] 현재 전원 모드 확인..."
sudo nvpmodel -q

# MAXN_SUPER 모드로 전환 (모드 2)
echo ""
echo "[2단계] MAXN_SUPER 모드로 전환 중 (모드 2)..."
sudo nvpmodel -m 2

# Jetson Clocks 활성화 (최대 클럭)
echo ""
echo "[3단계] Jetson Clocks 활성화 (최대 클럭)..."
sudo jetson_clocks

# 결과 확인
echo ""
echo "[4단계] 변경 결과 확인..."
sudo nvpmodel -q

echo ""
echo "=================================================="
echo "✅ MAXN_SUPER 모드 설정 완료!"
echo "=================================================="
echo ""
echo "💡 모드 번호:"
echo "  - 모드 0: 15W"
echo "  - 모드 1: 25W (기본)"
echo "  - 모드 2: MAXN_SUPER (최대 성능) ⭐"
echo ""
echo "💡 기타 명령:"
echo "  - 25W 모드로 되돌리기: sudo nvpmodel -m 1"
echo "  - Jetson Clocks 해제: sudo jetson_clocks --restore"
echo ""
