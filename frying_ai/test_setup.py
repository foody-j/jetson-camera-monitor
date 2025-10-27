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
