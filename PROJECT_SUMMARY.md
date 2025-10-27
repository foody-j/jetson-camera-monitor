# 튀김 AI 프로젝트 개발 요약

## 📋 프로젝트 개요

**목적**: 로봇 팔 기반 튀김 조리 자동화 시스템
- 카메라로 튀김 상태 실시간 모니터링
- 색상 변화 분석으로 조리 완료 시점 예측
- 안전한 조리를 위한 시간 기반 알림 시스템

**환경**:
- 하드웨어: NVIDIA Jetson Orin Nano
- 개발 환경: Windows 11 → VSCode SSH → Docker Container
- 카메라: /dev/video0
- 제어 PC: MQTT 통신 예정 (온도 센서 데이터)

## 🏗️ 시스템 아키텍처

```
┌──────────────────┐
│  Robotic Arm     │
│  + Bucket/Basket │
│  (튀김 음식 담김)  │
└────────┬─────────┘
         │
         v
┌──────────────────┐       ┌──────────────────┐
│   Jetson Orin    │◄──────┤  Control PC      │
│   - Camera       │  MQTT │  - Temp Sensors  │
│   - ML Model     │       │  - Commands      │
└────────┬─────────┘       └──────────────────┘
         │
         v
┌──────────────────┐
│ Windows Browser  │
│ (웹 뷰어)         │
└──────────────────┘
```

## 🎯 핵심 요구사항

1. **음식/기름 분리**: 로봇 팔이 바구니를 들고 있으므로, 튀김 음식과 기름을 구분해야 함
2. **평균 색상 계산**: 음식 영역에서만 평균 색상 특징 추출
3. **시간 기반 안전장치**: 일정 시간 후 알림 (과조리 방지)
4. **실시간 모니터링**: SSH + Docker 환경에서 브라우저로 접근
5. **MQTT 통합**: 제어 PC로부터 온도 데이터 수신 (향후)

## 📂 개발된 시스템 구조

### 1. 데이터 수집 (`frying_data_collector.py`)

**기능**:
- 실시간 카메라 캡처 (초당 1-2 프레임)
- 센서 데이터 시뮬레이션 (유온도, 튀김기 온도, 경과 시간)
- 세션 관리 (시작 → 수집 → 완료 마킹 → 종료)
- JSON/CSV 자동 저장

**데이터 구조**:
```python
@dataclass
class SensorData:
    timestamp: float
    oil_temp: float      # 튀김유 온도
    fryer_temp: float    # 튀김기 온도
    elapsed_time: float  # 경과 시간

@dataclass
class SessionData:
    session_id: str
    food_type: str       # chicken, shrimp, potato
    frames: List[FrameData]
    completion_time: float
    probe_temp: float    # 탐침온도계 Ground Truth
```

**출력**:
```
frying_dataset/
└── chicken_20251027_141132/
    ├── images/
    │   ├── t0000.jpg
    │   ├── t0001.jpg
    │   └── ...
    ├── session_data.json  # 전체 세션 메타데이터
    └── sensor_log.csv     # 시계열 센서 로그
```

**향후 계획**:
- 현재: `simulate=True` (시뮬레이션)
- 향후: MQTT 모드로 제어 PC에서 온도 수신

---

### 2. 음식 세그멘테이션 (`food_segmentation.py`)

**목적**: 튀김 음식과 기름/배경 분리

**알고리즘**:
- **HSV 색상 기반 분할**
  - 황금색 범위: Hue 15-35° (완벽한 튀김)
  - 갈색 범위: Hue 5-25° (익은 튀김)
  - 밝은 색 범위: Hue 20-40° (덜 익은 음식)
- **Morphology 노이즈 제거**: 작은 영역 필터링
- **Connected Components**: 최소 면적 500px 이상만 유지

**추출 특징**:
```python
@dataclass
class ColorFeatures:
    mean_hsv: Tuple[float, float, float]  # 평균 HSV
    mean_lab: Tuple[float, float, float]  # 평균 LAB (색 분석 적합)
    dominant_hue: float                    # 주요 색상
    saturation_mean: float                 # 채도 평균
    value_mean: float                      # 명도 평균
    brown_ratio: float                     # 갈색 비율 (익음 정도)
    golden_ratio: float                    # 황금색 비율 (완벽한 튀김)
```

**테스트 결과** (감자 + 갈색 종이 목업):
- 갈색 종이 검출: Brown ratio 94-98%
- 음식 영역: 2-11% of frame
- **결론**: 세그멘테이션 로직 정상 작동 확인

**시각화**:
- 헤드리스 환경 대응: `matplotlib.use('Agg')`
- 4-패널 시각화:
  1. 원본 이미지
  2. 음식 마스크 (흑백)
  3. 세그멘테이션 결과
  4. 특징 요약

**출력**:
```
frying_dataset/analysis_results/
├── potato_20251027_141132_analysis.json
├── potato_20251027_141132_features.csv
└── visualizations/
    └── potato_20251027_141132/
        ├── vis_t0000.jpg
        └── ...
```

---

### 3. 실시간 웹 뷰어 (`web_viewer.py`) ⭐

**목적**: SSH + Docker 환경에서 실시간 모니터링

**기술 스택**:
- **Backend**: Flask (Python)
- **Streaming**: MJPEG (multipart/x-mixed-replace)
- **Frontend**: HTML + JavaScript (Vanilla)

**주요 기능**:

#### A. 실시간 비디오 스트리밍
```python
def generate_stream():
    while state.is_running:
        frame = generate_annotated_frame()  # 세그멘테이션 + 오버레이
        jpeg = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
```

#### B. 세그멘테이션 오버레이
- 음식 영역: **초록색 반투명** 오버레이
- 정보 패널: 세션 ID, 경과 시간, 특징 값

#### C. REST API 엔드포인트
- `GET /api/status` - 현재 상태 (1초마다 폴링)
- `POST /api/start_session` - 세션 시작
- `POST /api/mark_completion` - 완료 마킹
- `POST /api/stop_session` - 세션 종료

#### D. 웹 UI
- **실시간 특징 표시**:
  - 음식 영역 비율
  - 갈색 비율
  - 황금색 비율
  - 색상(Hue)
- **세션 제어**:
  - 음식 종류 선택 (chicken, shrimp, potato, fish, vegetable)
  - 메모 입력
  - 탐침 온도 입력
  - 버튼: 시작/완료/종료

#### E. 접속 방법
```bash
# Windows에서 SSH 포트 포워딩
ssh -L 5000:localhost:5000 dkutest@<jetson-ip>

# 또는 VSCode SSH config:
# ~/.ssh/config에 추가:
Host jetson-nano
    LocalForward 5000 localhost:5000

# 브라우저에서:
http://localhost:5000
```

---

## 🔬 ML 모델 계획 (향후)

### 접근법: **전통 ML (CNN 사용 안 함)**

**이유**:
- ✅ 색상이 주요 시그널 (색 변화: 생 → 황금색 → 갈색)
- ✅ 특징이 이미 추출됨 (HSV, LAB, 비율)
- ✅ 적은 데이터로 가능 (50-100 샘플 vs CNN 500+)
- ✅ 빠른 추론 (Jetson 실시간 처리)
- ✅ 해석 가능 (어떤 특징이 중요한지 명확)

### 파이프라인 설계

```
입력 특징:
├── food_area_ratio      # 음식 영역 비율
├── brown_ratio          # 갈색 비율 (익음 정도)
├── golden_ratio         # 황금색 비율
├── hue_mean             # 평균 색상
├── saturation_mean      # 평균 채도
├── value_mean           # 평균 명도
├── lab_l, lab_a, lab_b  # LAB 색 공간
└── elapsed_time         # 경과 시간 ⭐ 중요

출력 (선택):
├── 회귀: 예측 내부 온도 (°C)
└── 분류: [Undercooked | Perfect | Overcooked]
```

### 모델 후보

**Phase 1: Baseline**
- Linear Regression
- 목적: 특징 중요도 파악, 빠른 검증

**Phase 2: Production**
- **Random Forest** (추천)
  - 비선형 관계 학습
  - Feature importance 제공
  - Overfitting 적음
- **XGBoost**
  - 더 높은 정확도
  - 시계열 특징에 강함

**Phase 3: Advanced**
- 시계열 모델 (색상 변화율 활용)
- LSTM/RNN (색상 변화 패턴 학습)

### 안전 알림 시스템

**2단계 체크**:
```python
# 조건 1: ML 예측
if predicted_doneness > threshold:
    alert()

# 조건 2: 시간 안전장치
if elapsed_time > max_cooking_time[food_type]:
    alert()  # 과조리 방지

# 알림 방법:
# - MQTT 메시지 → 제어 PC
# - 웹 UI 알림
# - 로컬 로그
```

---

## 📊 데이터 수집 전략

### 목표 데이터셋
- **음식별**: 치킨, 새우, 감자, 생선 등
- **샘플 수**: 각 50-100 세션
- **변수 다양화**:
  - 다른 온도 설정 (160°C, 170°C, 180°C)
  - 다른 조리 시간
  - 다른 배치 크기
  - 다른 시간대 (조명 변화)

### Ground Truth
- **탐침온도계** 측정 온도
- **완료 시점** 타임스탬프
- **육안 평가** (메모 필드)

### 품질 관리
- 카메라 각도 고정
- 조명 일정하게 유지
- 탐침 측정 위치 일관성

---

## 🛠️ 기술 스택

### Hardware
- NVIDIA Jetson Orin Nano
- Camera (/dev/video0)
- 탐침온도계 (수동)
- 제어 PC (MQTT, 향후)

### Software
- **OS**: Linux (Docker)
- **Language**: Python 3.8+
- **Computer Vision**: OpenCV
- **Web**: Flask
- **ML** (예정): scikit-learn, XGBoost
- **Data**: NumPy, Pandas, JSON, CSV
- **Communication** (예정): MQTT (paho-mqtt)

### Development
- Windows 11 (Host)
- VSCode Remote SSH
- Docker Container
- Git

---

## 📁 파일 구조

```
my_ai_project/
├── camera_monitor/              # 기존 카메라 시스템
│   ├── camera_base.py
│   ├── monitor.py
│   └── ...
├── frying_ai/                   # 튀김 AI 시스템 ⭐
│   ├── frying_data_collector.py # 데이터 수집
│   ├── food_segmentation.py     # 세그멘테이션
│   ├── web_viewer.py            # 웹 뷰어
│   ├── sensor_simulator.py      # 센서 시뮬레이터
│   ├── templates/
│   │   └── viewer.html          # 웹 UI (자동 생성)
│   ├── frying_dataset/          # 수집 데이터
│   │   └── [session_id]/
│   │       ├── images/
│   │       ├── session_data.json
│   │       └── sensor_log.csv
│   ├── requirements.txt
│   └── README.md
├── RUN_WEB_VIEWER.md            # 웹 뷰어 가이드
├── PROJECT_SUMMARY.md           # 이 파일
├── utils.py                     # 유틸리티
├── config.py                    # 설정 관리
└── docker-compose.yml           # Docker 설정
```

---

## ✅ 완료된 작업

### Phase 1: 데이터 수집 시스템 ✅
- [x] 카메라 캡처 (`frying_data_collector.py`)
- [x] 센서 시뮬레이션 (유온도, 튀김기 온도, 시간)
- [x] 세션 관리 (시작/완료/종료)
- [x] JSON/CSV 자동 저장

### Phase 2: 세그멘테이션 ✅
- [x] HSV 기반 음식/기름 분리
- [x] 색상 특징 추출 (9가지 특징)
- [x] 헤드리스 시각화 (matplotlib Agg backend)
- [x] 배치 분석 도구
- [x] 감자 목업 테스트 완료

### Phase 3: 웹 뷰어 ✅
- [x] Flask 서버
- [x] MJPEG 스트리밍
- [x] 실시간 세그멘테이션 오버레이
- [x] REST API (status, start, complete, stop)
- [x] 반응형 웹 UI
- [x] SSH 포트 포워딩 가이드

### Documentation ✅
- [x] `RUN_WEB_VIEWER.md` - 웹 뷰어 사용법
- [x] `frying_ai/README.md` - 시스템 개요
- [x] `PROJECT_SUMMARY.md` - 전체 요약 (이 파일)

---

## 🔜 다음 단계

### Immediate (즉시)
1. **웹 뷰어 테스트**
   - Flask 설치: `pip3 install flask`
   - 실행: `python3 frying_ai/web_viewer.py`
   - Windows 브라우저에서 접속 확인

2. **스쿱 & 볼 테스트**
   - 간단한 환경에서 로직 검증
   - 카메라 위치/각도 조정
   - 세그멘테이션 품질 확인

### Short-term (단기)
3. **실제 튀김 데이터 수집**
   - 치킨 20-30 세션
   - 다양한 조리 시간
   - 탐침온도 측정

4. **ML 모델 개발**
   - Baseline: Linear Regression
   - Production: Random Forest
   - 평가: Cross-validation

### Mid-term (중기)
5. **MQTT 센서 통합**
   - 제어 PC와 프로토콜 정의
   - `SensorInterface` MQTT 모드 구현
   - 실제 온도 데이터 수집

6. **알림 시스템**
   - MQTT 퍼블리셔 (제어 PC로 알림)
   - 웹 UI 알림
   - 시간 기반 안전장치

### Long-term (장기)
7. **로봇 팔 연동**
   - 완료 신호 → 로봇 팔 제어
   - 자동화 파이프라인

8. **배포 최적화**
   - 모델 경량화 (Jetson 최적화)
   - TensorRT 변환 (필요시)
   - 전력 효율 개선

---

## 🎓 핵심 인사이트

### 1. CNN 불필요
- 색상 특징만으로 충분
- 전통 ML이 더 적합 (적은 데이터, 빠른 추론, 해석 가능)

### 2. 세그멘테이션 중요성
- 음식/기름 분리 필수 (로봇 팔 + 바구니 환경)
- 평균 색상은 음식 영역에서만 계산

### 3. 시간 특징 중요
- 조리 시간도 주요 특징
- 안전장치로 필수

### 4. SSH + Docker 환경
- 웹 기반 UI가 최적 (X11 forwarding 불필요)
- 포트 포워딩으로 Windows 브라우저 접근

### 5. Ground Truth
- 탐침온도계가 객관적 라벨 제공
- 육안 평가 메모도 중요

---

## 📞 문제 해결

### 카메라 오류
```bash
ls -l /dev/video*
sudo chmod 666 /dev/video0
```

### Flask 설치
```bash
pip3 install flask
# 또는
apt-get update && apt-get install -y python3-flask
```

### 포트 포워딩
```bash
# VSCode SSH config
Host jetson-nano
    LocalForward 5000 localhost:5000

# 또는 수동
ssh -L 5000:localhost:5000 user@jetson-ip
```

### Docker 컨테이너 포트
`docker-compose.yml`에 추가:
```yaml
ports:
  - "5000:5000"
```

---

## 📚 참고 자료

### Color Spaces
- **HSV**: Hue (색상), Saturation (채도), Value (명도)
- **LAB**: L (밝기), A (빨강-초록), B (노랑-파랑)
- LAB이 인간 색 인식에 더 가까움

### Frying Temperature Ranges
- 치킨: 160-180°C, 내부 온도 74°C+
- 새우: 175°C, 3-5분
- 감자: 175°C, 3-4분 (1차), 190°C, 2-3분 (2차)

### ML Metrics
- **회귀**: MAE, RMSE, R²
- **분류**: Accuracy, Precision, Recall, F1

---

## 🏆 프로젝트 목표

**최종 목표**: 완전 자동화 튀김 시스템
1. 로봇 팔이 바구니 투입
2. 카메라로 실시간 모니터링
3. ML 모델이 완료 시점 예측
4. MQTT로 제어 PC에 알림
5. 로봇 팔이 자동으로 회수

**현재 진행도**: 35%
- ✅ 데이터 수집 인프라
- ✅ 세그멘테이션 & 특징 추출
- ✅ 웹 모니터링 UI
- ⏳ ML 모델 (다음 단계)
- ⏳ MQTT 통합 (향후)
- ⏳ 로봇 팔 연동 (향후)

---

## 📝 메모

### 2025-10-27 개발 세션
- 웹 뷰어 완성
- 세그멘테이션 검증 완료 (감자 목업)
- SSH + Docker 환경 최적화
- 전통 ML 방향 결정 (CNN 불필요)
- MQTT 센서 통합 방안 논의

### 다음 미팅 전 준비사항
- [ ] 웹 뷰어 동작 확인
- [ ] 스쿱 & 볼 테스트
- [ ] 제어 PC MQTT 프로토콜 정의
- [ ] 실제 튀김 1회 테스트 수집

---

**작성일**: 2025-10-27
**작성자**: Claude Code
**프로젝트**: 튀김 AI 자동화 시스템
**버전**: v0.3 (Web Viewer Release)
