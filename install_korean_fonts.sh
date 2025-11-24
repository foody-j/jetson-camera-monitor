#!/bin/bash
# Install Korean fonts for Jetson

echo "=== 한글 폰트 설치 ==="

if [ "$EUID" -ne 0 ]; then
    echo "오류: root 권한 필요"
    echo "사용법: sudo bash $0"
    exit 1
fi

echo "[1/3] 한글 폰트 패키지 설치..."
apt-get update -qq
apt-get install -y fonts-nanum fonts-nanum-coding fonts-nanum-extra >/dev/null 2>&1

echo "[2/3] matplotlib 폰트 캐시 삭제..."
rm -rf ~/.cache/matplotlib

echo "[3/3] 폰트 캐시 업데이트..."
fc-cache -fv >/dev/null 2>&1

echo ""
echo "=== 설치 완료 ==="
echo "설치된 나눔 폰트:"
fc-list | grep -i nanum

echo ""
echo "Python에서 확인:"
python3 << 'EOF'
import matplotlib.font_manager as fm
nanum_fonts = [f.name for f in fm.fontManager.ttflist if 'Nanum' in f.name]
if nanum_fonts:
    print(f"✓ 사용 가능한 나눔 폰트: {', '.join(set(nanum_fonts))}")
else:
    print("✗ 나눔 폰트를 찾을 수 없습니다")
EOF
