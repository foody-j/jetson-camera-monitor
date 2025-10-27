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
