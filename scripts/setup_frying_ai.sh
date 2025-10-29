#!/bin/bash

# 튀김 AI 프로젝트 자동 설정 스크립트
# 실행: bash setup_frying_ai.sh

echo "================================================"
echo "🍗 튀김 조리 자동화 프로젝트 설정"
echo "================================================"

# 1. 디렉토리 생성
echo ""
echo "1️⃣ 디렉토리 생성 중..."
mkdir -p frying_ai
mkdir -p frying_ai/frying_dataset
mkdir -p frying_ai/models
mkdir -p frying_ai/logs

echo "   ✅ frying_ai/ 디렉토리 생성 완료"

# 2. Python 파일 생성 여부 확인
echo ""
echo "2️⃣ Python 파일 확인..."

if [ ! -f "frying_ai/frying_data_collector.py" ]; then
    echo "   ⚠️  frying_data_collector.py 파일을 frying_ai/ 폴더에 저장해주세요"
    MISSING_FILES=1
fi

if [ ! -f "frying_ai/sensor_simulator.py" ]; then
    echo "   ⚠️  sensor_simulator.py 파일을 frying_ai/ 폴더에 저장해주세요"
    MISSING_FILES=1
fi

if [ -z "$MISSING_FILES" ]; then
    echo "   ✅ 모든 Python 파일 확인됨"
fi

# 3. 테스트 스크립트 생성
echo ""
echo "3️⃣ 테스트 스크립트 생성 중..."

cat > frying_ai/test_setup.py << 'EOF'
#!/usr/bin/env python3
"""
설정 테스트 스크립트
"""
import sys
import os

# 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 50)
print("🧪 튀김 AI 설정 테스트")
print("=" * 50)

# 1. camera_monitor 임포트 테스트
try:
    from camera_monitor.camera_base import CameraBase
    print("✅ camera_monitor 임포트 성공")
except ImportError as e:
    print(f"❌ camera_monitor 임포트 실패: {e}")
    print("   프로젝트 루트에서 실행 중인지 확인하세요")

# 2. utils 임포트 테스트
try:
    from utils import get_timestamp
    print("✅ utils 임포트 성공")
    print(f"   현재 시간: {get_timestamp()}")
except ImportError as e:
    print(f"❌ utils 임포트 실패: {e}")

# 3. 센서 시뮬레이터 테스트
try:
    from sensor_simulator import SensorManager
    manager = SensorManager(mode="simulate")
    oil_temp, fryer_temp = manager.read_temperatures()
    print("✅ 센서 시뮬레이터 작동")
    print(f"   유온도: {oil_temp:.1f}°C, 튀김기: {fryer_temp:.1f}°C")
except Exception as e:
    print(f"❌ 센서 시뮬레이터 오류: {e}")

# 4. 디렉토리 확인
import os
dirs_to_check = ['frying_dataset', 'models', 'logs']
for dir_name in dirs_to_check:
    if os.path.exists(dir_name):
        print(f"✅ {dir_name}/ 디렉토리 존재")
    else:
        print(f"⚠️  {dir_name}/ 디렉토리 없음")

print("=" * 50)
print("테스트 완료!")
EOF

chmod +x frying_ai/test_setup.py
echo "   ✅ test_setup.py 생성 완료"

# 4. 실행 스크립트 생성
echo ""
echo "4️⃣ 실행 스크립트 생성 중..."

cat > frying_ai/run_collector.sh << 'EOF'
#!/bin/bash
# 데이터 수집기 실행 스크립트

cd "$(dirname "$0")"
echo "🍗 튀김 데이터 수집기 시작..."
python3 frying_data_collector.py
EOF

cat > frying_ai/run_simulator_test.sh << 'EOF'
#!/bin/bash
# 센서 시뮬레이터 테스트

cd "$(dirname "$0")"
echo "🌡️ 센서 시뮬레이터 테스트..."
python3 sensor_simulator.py test
EOF

chmod +x frying_ai/run_collector.sh
chmod +x frying_ai/run_simulator_test.sh

echo "   ✅ 실행 스크립트 생성 완료"

# 5. README 생성
echo ""
echo "5️⃣ README 파일 생성 중..."

cat > frying_ai/README.md << 'EOF'
# 🍗 튀김 조리 자동화 AI

## 📁 프로젝트 구조
```
frying_ai/
├── frying_data_collector.py  # 메인 데이터 수집기
├── sensor_simulator.py        # 센서 시뮬레이터
├── frying_dataset/           # 수집된 데이터
├── models/                   # AI 모델 저장
├── logs/                     # 로그 파일
├── test_setup.py            # 설정 테스트
├── run_collector.sh         # 수집기 실행
└── run_simulator_test.sh    # 시뮬레이터 테스트
```

## 🚀 빠른 시작

### 1. 설정 테스트
```bash
cd frying_ai
python3 test_setup.py
```

### 2. 센서 시뮬레이터 테스트
```bash
./run_simulator_test.sh
```

### 3. 데이터 수집 시작
```bash
./run_collector.sh
```

## 📊 수집 프로세스

1. **세션 시작** (s 키)
   - 음식 종류 입력 (chicken/shrimp/potato)
   - 메모 입력 (온도 설정 등)

2. **조리 진행**
   - 자동으로 이미지와 센서 데이터 수집
   - 5초마다 상태 출력

3. **완료 마킹** (c 키)
   - 탐침온도계로 측정한 온도 입력
   - 완료 상태 메모

4. **세션 종료** (e 키)
   - 데이터 자동 저장
   - 통계 출력

## 📈 목표

- **일일 목표**: 20개 세션
- **주간 목표**: 100개 세션
- **최종 목표**: 400개 세션 (학습용)

## 🔧 센서 연결 (옵션)

현재는 시뮬레이션 모드로 작동합니다.
실제 센서 연결 시 `sensor_simulator.py`의 mode를 변경하세요:

```python
# 시뮬레이션 (기본)
manager = SensorManager(mode="simulate")

# 실제 센서
manager = SensorManager(mode="serial")  # 또는 "modbus", "gpio"
```

## ⚠️ 주의사항

1. 카메라가 /dev/video0에 연결되어 있어야 함
2. 탐침온도계 측정 위치 일정하게 유지
3. 조명 조건 일정하게 유지

## 📞 문제 해결

### 카메라 오류
```bash
ls -l /dev/video*
sudo chmod 666 /dev/video0
```

### Import 오류
상위 디렉토리(프로젝트 루트)에 camera_monitor/와 utils.py가 있는지 확인

### 권한 오류
```bash
chmod +x *.sh
```
EOF

echo "   ✅ README.md 생성 완료"

# 6. 완료 메시지
echo ""
echo "================================================"
echo "✅ 설정 완료!"
echo "================================================"
echo ""
echo "📂 생성된 구조:"
echo "   frying_ai/"
echo "   ├── frying_dataset/     (데이터 저장)"
echo "   ├── models/             (모델 저장)"
echo "   ├── logs/               (로그)"
echo "   └── *.py, *.sh          (스크립트)"
echo ""
echo "🚀 다음 단계:"
echo ""
echo "   1. Python 파일 저장:"
if [ ! -z "$MISSING_FILES" ]; then
    echo "      - frying_data_collector.py를 frying_ai/에 저장"
    echo "      - sensor_simulator.py를 frying_ai/에 저장"
    echo ""
fi
echo "   2. 테스트 실행:"
echo "      cd frying_ai"
echo "      python3 test_setup.py"
echo ""
echo "   3. 데이터 수집 시작:"
echo "      ./run_collector.sh"
echo ""
echo "================================================"