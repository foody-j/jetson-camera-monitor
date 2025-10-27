# 🍗 튀김 조리 자동화 AI

로봇 팔 기반 튀김 조리 자동화를 위한 실시간 모니터링 및 데이터 수집 시스템

## 📁 프로젝트 구조
```
frying_ai/
├── frying_data_collector.py  # 메인 데이터 수집기
├── food_segmentation.py       # 음식/기름 분리 & 특징 추출 ⭐
├── web_viewer.py              # 실시간 웹 뷰어 ⭐ NEW
├── sensor_simulator.py        # 센서 시뮬레이터
├── frying_dataset/            # 수집된 데이터
├── templates/                 # 웹 UI 템플릿
├── models/                    # AI 모델 저장
├── logs/                      # 로그 파일
├── requirements.txt           # Python 의존성
└── README.md                  # 이 파일
```

## 🚀 빠른 시작

### 방법 1: 웹 뷰어 (추천 ⭐)

```bash
# 1. Flask 설치
pip3 install flask

# 2. 웹 뷰어 실행
python3 frying_ai/web_viewer.py

# 3. Windows에서 SSH 포트 포워딩 후 접속
# http://localhost:5000
```

📖 **상세 가이드**: [../RUN_WEB_VIEWER.md](../RUN_WEB_VIEWER.md)

### 방법 2: 커맨드라인

```bash
# 대화형 데이터 수집
python3 frying_ai/frying_data_collector.py

# 자동 테스트 (30초)
python3 frying_ai/frying_data_collector.py test
```

### 방법 3: 데이터 분석

```bash
# 기존 데이터 세그멘테이션 분석
python3 frying_ai/food_segmentation.py frying_dataset

# 특정 이미지 테스트
python3 frying_ai/food_segmentation.py test path/to/image.jpg
```

## 📊 수집 프로세스

### 웹 UI에서:
1. **세션 시작**: 음식 종류 선택 → 메모 입력 → "세션 시작" 버튼
2. **실시간 모니터링**: 카메라 영상 + 세그멘테이션 오버레이 + 특징 표시
3. **완료 마킹**: 탐침온도 입력 → "완료 마킹" 버튼
4. **세션 종료**: "세션 종료" 버튼 → 자동 저장

### 커맨드라인에서:
1. **세션 시작** (s 키) - 음식 종류, 메모 입력
2. **조리 진행** - 자동 이미지/센서 수집, 5초마다 상태 출력
3. **완료 마킹** (c 키) - 탐침온도 입력
4. **세션 종료** (e 키) - 데이터 저장, 통계 출력

## 🎯 주요 기능

### 1. 실시간 웹 뷰어 ⭐
- **MJPEG 스트리밍**: 브라우저에서 실시간 영상 확인
- **자동 세그멘테이션**: 음식 영역 초록색 오버레이
- **실시간 특징**: 음식 면적, 갈색 비율, 황금색 비율 등
- **세션 제어**: 웹 UI로 시작/완료/종료
- **SSH + Docker 최적화**: Windows 브라우저에서 접근

### 2. 음식/기름 분리 세그멘테이션
- HSV 기반 색상 분할 (갈색, 황금색 범위)
- 음식 영역만 특징 추출
- 배경(기름) 노이즈 제거

### 3. 색상 특징 추출
- **brown_ratio**: 갈색 비율 (익음 정도)
- **golden_ratio**: 황금색 비율 (완벽한 튀김)
- **HSV/LAB 평균**: 색상, 채도, 명도
- **food_area_ratio**: 전체 대비 음식 영역

### 4. 자동 데이터 저장
- 타임스탬프 이미지 (초당 1-2프레임)
- 센서 로그 CSV (시계열 데이터)
- 세션 메타데이터 JSON
- Ground Truth 라벨 (탐침온도)

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
