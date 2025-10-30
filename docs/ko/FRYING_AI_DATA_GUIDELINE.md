# 튀김 AI 데이터 수집 및 적용 가이드라인

## 📋 개요

이 가이드는 튀김 AI 시스템을 위한 데이터 수집, 라벨링 및 적용에 대한 포괄적인 지침을 제공합니다. 목표는 시각적(색상) 및 센서(온도) 데이터를 기반으로 음식이 완벽하게 조리되는 시점을 예측할 수 있는 머신러닝 모델을 구축하는 것입니다.

---

## 🎯 프로젝트 목표

**튀김 완료 시간 예측**

입력:
- 음식이 튀겨지는 실시간 이미지
- 온도 센서 데이터 (기름 온도, 튀김기 온도)
- 경과 시간

출력:
- 예측 완성도 수준 (0-100%)
- 예상 남은 시간
- 음식이 준비되었을 때 경고

---

## 📊 데이터 수집 개요

### 수집되는 데이터

**1. 시각 데이터 (이미지)**
- **형식**: JPEG 이미지
- **빈도**: 1-2 FPS (초당 프레임)
- **해상도**: 640x360 이상
- **내용**: 튀김기 속 음식의 상단 뷰
- **명명**: `t0000.jpg`, `t0001.jpg`, ... (순차적)

**2. 센서 데이터 (온도)**
- **기름 온도**: 튀김 기름의 온도 (°C)
- **튀김기 온도**: 히터/주변 온도 (°C)
- **내부 온도**: 음식 프로브 온도 (°C) - 정답 레이블용
- **빈도**: 이미지 캡처와 동일 (동기화)
- **형식**: CSV 시계열

**3. 세션 메타데이터**
- 음식 종류 (치킨, 새우, 감자 등)
- 시작 시간 및 종료 시간
- 완료 시점 (정답 레이블 타임스탬프)
- 완료 시 프로브 온도
- 세션 메모
- 날씨 조건 (선택사항)

### 데이터 구조

```
data/frying_dataset/
├── chicken_20251028_143012/          # 세션 ID
│   ├── images/                        # 이미지 시퀀스
│   │   ├── t0000.jpg
│   │   ├── t0001.jpg
│   │   └── ...
│   ├── session_data.json              # 메타데이터
│   └── sensor_log.csv                 # 시계열 센서 데이터
│
├── shrimp_20251028_150045/
│   ├── images/
│   ├── session_data.json
│   └── sensor_log.csv
│
└── analysis_results/                  # 특징 추출 결과
    ├── chicken_20251028_143012_features.json
    └── ...
```

---

## 🛠️ 장비 설정

### 필요한 장비

1. **카메라**
   - USB 웹캠 또는 CSI 카메라
   - 튀김기 위에 장착
   - 명확한 상단 뷰
   - 좋은 조명
   - 내열 마운트

2. **온도 센서**
   - **기름 온도계**: K-타입 열전대 또는 PT100
   - **음식 프로브**: 디지털 고기 온도계 (정답 레이블에 필수)
   - **튀김기 센서**: 주변/히터 온도
   - Jetson에 RS485 또는 시리얼 연결

3. **Jetson Orin Nano**
   - Ubuntu 실행
   - 카메라 연결
   - USB/GPIO를 통한 센서 연결
   - 충분한 저장 공간 (100GB+ 권장)

4. **튀김 장비**
   - 딥 프라이어 또는 웍
   - 일관된 열원
   - 안전 장비 (소화기, 앞치마, 장갑)

### 카메라 위치

```
        [카메라]
            |
         [마운트]
            |
    ==================
    |                |
    |     [음식]     |  ← 튀김기
    |    [  기름 ]   |
    |                |
    ==================
```

**모범 사례**:
- 기름 표면에서 30-50 cm 위에 장착
- 튀김기 중앙 바로 위
- 김/연기 방해 방지
- 필요시 보호 케이스 사용
- 안정적인 장착 보장 (진동 없음)

---

## 📝 데이터 수집 절차

### 준비

**1. 시스템 설정**
```bash
# 프로젝트로 이동
cd /home/dkutest/my_ai_project

# 환경 활성화 (가상 환경 사용 시)
source venv/bin/activate

# 카메라 테스트
python tests/test_camera.py

# 센서 테스트
python tests/test_sensors.py
```

**2. 환경 준비**
- 튀김기와 기름 청소
- 카메라 위치 설정
- 모든 센서 연결
- 온도 판독값 확인
- 음식 준비
- 주변 조건 문서화

**3. 데이터 수집기 실행**
```bash
# 방법 1: 웹 인터페이스
cd frying_ai
python web_viewer.py

# 방법 2: 직접 CLI
python frying_data_collector.py
```

### 데이터 수집 워크플로우

**1단계: 세션 시작**

웹 인터페이스를 통해 (http://localhost:5000):
1. **음식 종류** 입력 (예: "chicken_wings")
2. **세션 메모** 추가 (예: "신선한 기름, 180°C, 500g 배치")
3. **"세션 시작"** 클릭
4. 시스템이 새 세션 폴더 생성
5. 이미지 및 센서 로깅 시작

CLI를 통해:
```python
from frying_data_collector import FryingDataCollector

collector = FryingDataCollector()
collector.initialize()
collector.start_session(food_type="chicken_wings", notes="신선한 기름, 180°C")
```

**2단계: 튀김 과정 모니터링**

- 시스템이 자동으로 캡처:
  - 0.5-1.0초마다 이미지 (1-2 FPS)
  - 이미지와 동기화된 온도 판독값
  - 세션 시작 이후 경과 시간

- 관찰자가 모니터링:
  - 음식 색상 변화 (연함 → 황금색 → 갈색)
  - 기름 거품 강도
  - 음식 부유 행동
  - 증기 생성

- 웹 뷰어 표시:
  - 라이브 비디오 피드
  - 현재 경과 시간
  - 실시간 온도 판독값
  - 음식 분할 오버레이 (녹색 마스크)

**3단계: 완료 마킹 (정답 레이블)**

**중요**: 이것이 가장 중요한 단계입니다!

음식이 **완벽하게 조리되었을 때** (음식 프로브 온도계로 결정):

웹 인터페이스를 통해:
1. 음식 프로브 온도계 삽입
2. 온도가 안정될 때까지 대기
3. **프로브 온도** 판독 (예: 치킨의 경우 165°F / 74°C)
4. **"완료 마킹"** 클릭
5. 프로브 온도 입력
6. 메모 추가 (예: "황금색 갈색, 바삭한 외부")
7. 확인

CLI를 통해:
```python
# 음식이 완료된 정확한 순간 마킹
collector.mark_completion(
    probe_temp=74.0,  # °C
    notes="황금색 갈색, 내부 온도 74°C"
)
```

**음식 종류별 정답 레이블 가이드라인**:

| 음식 종류 | 내부 온도 (°C) | 내부 온도 (°F) | 시각적 단서 |
|-----------|----------------|----------------|-------------|
| 치킨 | 74°C | 165°F | 황금색 갈색, 육즙 맑음 |
| 새우 | 63°C | 145°F | 분홍색/흰색, 불투명, 말림 |
| 감자 (튀김) | N/A | N/A | 황금색 노랑, 바삭한 가장자리 |
| 생선 | 63°C | 145°F | 불투명, 쉽게 벗겨짐 |
| 돼지고기 | 63°C | 145°F | 연한 분홍색 중심, 단단함 |

**4단계: 계속 녹화 (선택사항)**

완료 마킹 후 다음을 수행할 수 있습니다:
- 몇 초 더 녹화 (과조리 상태 캡처)
- 또는 즉시 세션 중지

**권장사항**: 완료 **후** 10-30초 동안 녹화하여 "과조리" 상태로의 전환을 캡처하세요. 이는 모델이 경계를 학습하는 데 도움이 됩니다.

**5단계: 세션 중지**

웹 인터페이스를 통해:
1. **"세션 중지"** 클릭
2. 시스템이 데이터 마무리:
   - CSV 파일 닫기
   - session_data.json 저장
   - 요약 생성

CLI를 통해:
```python
collector.stop_session()
```

**6단계: 데이터 확인**

```bash
# 세션 폴더 확인
ls -lh frying_dataset/chicken_20251028_143012/

# 이미지 수 확인
ls frying_dataset/chicken_20251028_143012/images/ | wc -l

# CSV 확인
head -n 5 frying_dataset/chicken_20251028_143012/sensor_log.csv

# 메타데이터 검토
cat frying_dataset/chicken_20251028_143012/session_data.json | python -m json.tool
```

---

## 🎓 모범 사례

### 세션 계획

**조건 변화** (강건한 모델을 위해):
- 다양한 음식 종류 (치킨, 새우, 감자, 생선)
- 다양한 배치 크기 (소, 중, 대)
- 다양한 기름 온도 (160°C, 170°C, 180°C, 190°C)
- 다양한 기름 상태 (신선, 1회 사용, 3회 사용, 5회 사용)
- 다양한 주변 온도 (아침 vs. 오후)
- 다양한 음식 상태 (냉동 vs. 해동)

**목표 데이터셋 크기**:
- **최소**: 50 세션 (음식 종류당 10개)
- **권장**: 200+ 세션 (음식 종류당 40+개)
- **이상적**: 500+ 세션 (포괄적 커버리지)

### 정답 레이블 정확도

**중요 성공 요인**: 정확한 정답 레이블링!

**음식 프로브 온도계 사용**:
- 음식의 가장 두꺼운 부분에 삽입
- 안정화를 위해 5-10초 대기
- 정확하게 온도 판독
- 시스템에 즉시 기록

**시각적 검사**:
- 음식 샘플을 잘라 완성도 확인
- 색상 일관성 확인
- 질감 확인 (바삭함 vs. 눅눅함)
- 맛 테스트 (안전한 경우)

**일관성**:
- 모든 세션에서 동일한 기준 사용
- 모든 작업자에게 정답 레이블 절차 교육
- 예외 또는 불확실성 문서화

### 안전

- **튀김기를 방치하지 마세요**
- 소화기를 가까이 두세요
- 보호 장비 착용 (앞치마, 장갑)
- 적절한 환기 보장
- 카메라 장비를 뜨거운 기름에서 멀리 두세요
- 내열 마운트 사용
- 비상 정지 절차 마련

---

## 📈 특징 추출

원시 데이터 수집 후 ML 학습을 위한 특징을 추출합니다.

### 음식 분할 실행

```bash
cd frying_ai

# 단일 세션 분석
python food_segmentation.py --session frying_dataset/chicken_20251028_143012

# 모든 세션 일괄 분석
python food_segmentation.py --batch

# 출력: frying_dataset/analysis_results/
```

### 추출된 특징

각 프레임에 대해 시스템이 추출:

**색상 특징 (HSV)**:
- `brown_ratio`: 갈색 픽셀 비율 (0.0 - 1.0)
- `golden_ratio`: 황금색 픽셀 비율 (0.0 - 1.0)
- `mean_hue`: 평균 색조 값 (0 - 180)
- `mean_saturation`: 평균 채도 (0 - 255)
- `mean_value`: 평균 밝기 (0 - 255)

**색상 특징 (LAB)**:
- `mean_l`: 명도 (0 - 100)
- `mean_a`: 녹색-빨간색 축 (-128 ~ 127)
- `mean_b`: 파란색-노란색 축 (-128 ~ 127)

**공간 특징**:
- `food_area_ratio`: 음식 픽셀 / 전체 픽셀 (0.0 - 1.0)

**시간 특징** (파생):
- `elapsed_time`: 세션 시작 이후 초
- `time_to_completion`: 완료 마킹까지의 초 (목표)

### 특징 엔지니어링

계산할 추가 특징:

**변화율**:
```python
brown_ratio_delta = (brown_ratio[t] - brown_ratio[t-10]) / 10.0
golden_ratio_delta = (golden_ratio[t] - golden_ratio[t-10]) / 10.0
```

**이동 평균**:
```python
brown_ratio_ma5 = np.mean(brown_ratio[t-5:t])
brown_ratio_ma10 = np.mean(brown_ratio[t-10:t])
```

**센서 특징**:
```python
oil_temp_stable = np.std(oil_temp[t-10:t]) < 5.0  # Boolean
temp_drop = oil_temp[0] - oil_temp[t]  # 온도 하락
```

### 출력 형식

**프레임당 특징** (`session_id_features.json`):
```json
{
  "session_id": "chicken_20251028_143012",
  "food_type": "chicken",
  "completion_time": 180.5,
  "frames": [
    {
      "timestamp": 0.0,
      "frame_id": "t0000",
      "brown_ratio": 0.02,
      "golden_ratio": 0.15,
      "mean_hue": 25.3,
      "mean_saturation": 120.5,
      "mean_value": 180.2,
      "food_area_ratio": 0.35,
      "oil_temp": 175.2,
      "elapsed_time": 0.0,
      "time_to_completion": 180.5
    },
    ...
  ]
}
```

---

## 🤖 머신러닝 파이프라인

### 데이터 준비

**1. 데이터 로드 및 병합**

```python
import pandas as pd
import json
import glob

def load_all_sessions():
    """모든 세션 특징 데이터를 단일 DataFrame으로 로드"""
    all_data = []

    for feature_file in glob.glob("frying_dataset/analysis_results/*_features.json"):
        with open(feature_file, 'r') as f:
            session = json.load(f)

        for frame in session['frames']:
            frame['food_type'] = session['food_type']
            frame['session_id'] = session['session_id']
            all_data.append(frame)

    df = pd.DataFrame(all_data)
    return df

df = load_all_sessions()
print(f"총 프레임: {len(df)}")
print(f"총 세션: {df['session_id'].nunique()}")
```

**2. 특징 선택**

```python
# 특징 열 정의
feature_cols = [
    'brown_ratio',
    'golden_ratio',
    'mean_hue',
    'mean_saturation',
    'mean_value',
    'mean_l',
    'mean_a',
    'mean_b',
    'food_area_ratio',
    'oil_temp',
    'elapsed_time'
]

# 목표 변수
target_col = 'time_to_completion'

X = df[feature_cols]
y = df[target_col]
```

**3. 학습/테스트 분할**

```python
from sklearn.model_selection import train_test_split

# 데이터 누출을 피하기 위해 세션별로 분할 (프레임별이 아님)
sessions = df['session_id'].unique()
train_sessions, test_sessions = train_test_split(
    sessions, test_size=0.2, random_state=42
)

train_df = df[df['session_id'].isin(train_sessions)]
test_df = df[df['session_id'].isin(test_sessions)]

X_train = train_df[feature_cols]
y_train = train_df[target_col]
X_test = test_df[feature_cols]
y_test = test_df[target_col]
```

### 모델 학습

**1단계: 기준선 (선형 회귀)**

```python
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

# 모델 학습
model = LinearRegression()
model.fit(X_train, y_train)

# 평가
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.2f}초")
print(f"R²: {r2:.3f}")
```

**2단계: 랜덤 포레스트**

```python
from sklearn.ensemble import RandomForestRegressor

model = RandomForestRegressor(
    n_estimators=100,
    max_depth=15,
    min_samples_split=10,
    random_state=42
)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.2f}초")
print(f"R²: {r2:.3f}")
```

**3단계: XGBoost (고급)**

```python
import xgboost as xgb

model = xgb.XGBRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=10,
    random_state=42
)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.2f}초")
print(f"R²: {r2:.3f}")
```

### 모델 평가

**지표**:
- **MAE** (평균 절대 오차): 초 단위 평균 예측 오차
  - 목표: < 10초
- **R²** (결정 계수): 모델 적합도 품질
  - 목표: > 0.85
- **RMSE** (평균 제곱근 오차): 큰 오류에 페널티
  - 목표: < 15초

**음식 종류별 평가**:
```python
for food_type in df['food_type'].unique():
    test_food = test_df[test_df['food_type'] == food_type]
    X_food = test_food[feature_cols]
    y_food = test_food[target_col]

    y_pred_food = model.predict(X_food)
    mae_food = mean_absolute_error(y_food, y_pred_food)

    print(f"{food_type}: MAE = {mae_food:.2f}초")
```

**특징 중요도**:
```python
import matplotlib.pyplot as plt

# 랜덤 포레스트 또는 XGBoost의 경우
importance = model.feature_importances_
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': importance
}).sort_values('importance', ascending=False)

print(feature_importance)

# 플롯
plt.figure(figsize=(10, 6))
plt.barh(feature_importance['feature'], feature_importance['importance'])
plt.xlabel('중요도')
plt.title('특징 중요도')
plt.tight_layout()
plt.savefig('feature_importance.png')
```

### 모델 배포

**모델 저장**:
```python
import joblib

# 모델 저장
joblib.dump(model, 'models/frying_predictor_v1.pkl')

# 특징 스케일러 저장 (사용하는 경우)
joblib.dump(scaler, 'models/feature_scaler_v1.pkl')
```

**로드 및 사용**:
```python
# 모델 로드
model = joblib.load('models/frying_predictor_v1.pkl')

# 실시간 예측
current_features = {
    'brown_ratio': 0.25,
    'golden_ratio': 0.40,
    'mean_hue': 22.5,
    'mean_saturation': 145.2,
    'mean_value': 180.8,
    'mean_l': 75.3,
    'mean_a': 12.5,
    'mean_b': 35.2,
    'food_area_ratio': 0.38,
    'oil_temp': 178.5,
    'elapsed_time': 120.0
}

X_current = pd.DataFrame([current_features])
time_remaining = model.predict(X_current)[0]

print(f"예상 남은 시간: {time_remaining:.1f}초")

if time_remaining < 10:
    print("⚠️ 경고: 음식이 거의 준비되었습니다!")
```

---

## 📊 데이터 품질 확인

### 세션 검증

각 세션 후 확인:

```python
def validate_session(session_path):
    """세션 데이터 품질 검증"""
    issues = []

    # 이미지 수 확인
    images = glob.glob(f"{session_path}/images/*.jpg")
    if len(images) < 50:
        issues.append(f"이미지 너무 적음: {len(images)}")

    # CSV 확인
    csv_path = f"{session_path}/sensor_log.csv"
    if not os.path.exists(csv_path):
        issues.append("sensor_log.csv 누락")
    else:
        df = pd.read_csv(csv_path)
        if len(df) != len(images):
            issues.append(f"이미지/CSV 불일치: {len(images)}개 이미지, {len(df)}개 CSV 행")

    # 메타데이터 확인
    json_path = f"{session_path}/session_data.json"
    if not os.path.exists(json_path):
        issues.append("session_data.json 누락")
    else:
        with open(json_path, 'r') as f:
            metadata = json.load(f)

        if 'completion_frame' not in metadata:
            issues.append("완료 시간 마킹되지 않음!")

        if not metadata.get('food_type'):
            issues.append("음식 종류 지정되지 않음")

    if issues:
        print(f"❌ 검증 실패: {session_path}:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print(f"✅ 세션 검증됨: {session_path}")
        return True
```

### 데이터셋 통계

```python
def dataset_statistics():
    """데이터셋 통계 출력"""
    sessions = glob.glob("frying_dataset/*/session_data.json")

    stats = {
        'total_sessions': len(sessions),
        'food_types': {},
        'total_frames': 0,
        'avg_duration': []
    }

    for session_file in sessions:
        with open(session_file, 'r') as f:
            session = json.load(f)

        food_type = session.get('food_type', 'unknown')
        stats['food_types'][food_type] = stats['food_types'].get(food_type, 0) + 1

        duration = session.get('duration', 0)
        stats['avg_duration'].append(duration)

        images = glob.glob(f"{os.path.dirname(session_file)}/images/*.jpg")
        stats['total_frames'] += len(images)

    print("=" * 50)
    print("데이터셋 통계")
    print("=" * 50)
    print(f"총 세션: {stats['total_sessions']}")
    print(f"총 프레임: {stats['total_frames']}")
    print(f"평균 지속 시간: {np.mean(stats['avg_duration']):.1f}초")
    print(f"\n음식 종류별 세션:")
    for food_type, count in stats['food_types'].items():
        print(f"  - {food_type}: {count}개 세션")
    print("=" * 50)
```

---

## 🎯 목표 지표

### 데이터 수집 목표

- **총 세션**: 200+ (음식 종류당 40+개)
- **세션 지속 시간**: 일반적으로 2-5분
- **이미지 품질**: 명확하고 밝으며 안정적
- **정답 레이블 정확도**: ±2°C 온도, ±5초 타이밍
- **데이터 완전성**: 100% (모든 세션에 이미지 + CSV + 메타데이터)

### 모델 성능 목표

- **MAE**: < 10초 (예측 오차)
- **R²**: > 0.85 (모델 적합도)
- **음식 종류별 MAE**: < 15초
- **실시간 지연 시간**: < 100ms (예측 시간)
- **거짓 양성 비율**: < 5% (조기 경고)
- **거짓 음성 비율**: < 2% (완벽한 완성도 놓침)

---

## 🔄 지속적 개선

### 데이터 수집 팁

1. **경계 사례 라벨링**: 덜 익힘, 과조리, 탐
2. **이상 현상 문서화**: 예상치 못한 행동
3. **조건 변화**: 하루에 모든 데이터를 수집하지 마세요
4. **정기적으로 검토**: 매주 데이터 품질 확인
5. **주기적으로 재학습**: 매월 새 세션 추가

### 모델 반복

1. **간단하게 시작**: 선형 회귀 기준선
2. **복잡도 추가**: 랜덤 포레스트 → XGBoost
3. **특징 엔지니어링**: 파생 특징 추가
4. **하이퍼파라미터 튜닝**: GridSearchCV
5. **교차 검증**: K-폴드 검증
6. **A/B 테스트**: 프로덕션에서 모델 버전 비교

---

## 📚 참조

### 세션 메타데이터 스키마

```json
{
  "session_id": "chicken_20251028_143012",
  "food_type": "chicken",
  "start_time": 1698500000.123,
  "end_time": 1698500180.456,
  "duration": 180.333,
  "completion_frame": 181,
  "completion_time": 180.5,
  "probe_temp": 74.0,
  "notes": "신선한 기름, 180°C 목표",
  "camera_config": {
    "resolution": [640, 360],
    "fps": 2
  },
  "sensor_config": {
    "mode": "simulate"
  }
}
```

### 센서 로그 스키마 (CSV)

```
timestamp,elapsed_time,oil_temp,fryer_temp,internal_temp
1698500000.123,0.000,180.0,185.0,20.0
1698500000.623,0.500,179.5,184.8,22.5
1698500001.123,1.000,179.0,184.5,25.0
...
```

---

## 🆘 문제 해결

### 일반적인 문제

**이미지가 흐림**:
- 카메라 렌즈 청소
- 초점 조정
- 김/연기 감소
- 조명 개선

**온도 판독값 불일치**:
- 센서 연결 확인
- 센서 보정
- 느슨한 배선 확인
- 고품질 센서 사용

**완료 타이밍 불확실**:
- 음식 프로브 온도계 사용
- 시각적 단서 문서화
- 샘플을 잘라 확인
- 기준에 일관성 유지

**데이터셋 불균형**:
- 표현이 부족한 음식에 대한 세션 더 수집
- 데이터 증강 사용 (주의해서)
- 모델 학습에 클래스 가중치 적용

---

## ✅ 체크리스트

### 세션 전
- [ ] 카메라 장착 및 초점 맞춤
- [ ] 센서 연결 및 판독
- [ ] 데이터 수집기 실행
- [ ] 음식 프로브 온도계 준비
- [ ] 안전 장비 마련

### 세션 중
- [ ] 올바른 음식 종류로 세션 시작
- [ ] 문제 확인을 위한 비디오 피드 모니터링
- [ ] 완벽한 완성도 관찰
- [ ] 프로브 온도계 준비

### 완료 마킹
- [ ] 가장 두꺼운 부분에 프로브 삽입
- [ ] 온도 안정화 대기
- [ ] 정확한 온도 기록
- [ ] "완료 마킹" 클릭
- [ ] 설명적인 메모 추가

### 세션 후
- [ ] 세션 올바르게 중지
- [ ] 이미지 수 확인
- [ ] CSV 완전성 확인
- [ ] session_data.json 검토
- [ ] 검증 스크립트 실행

### 데이터셋 관리
- [ ] 날짜별로 세션 정리
- [ ] 정기적으로 데이터 백업
- [ ] 특징 추출 실행
- [ ] 데이터셋 통계 확인
- [ ] 이상 현상 문서화

---

## 📞 지원

질문이 있는 경우:
1. 이 가이드 검토
2. 문제 해결 섹션 확인
3. 제공된 스크립트로 데이터 검증
4. 개선을 위한 문제 문서화

---

**버전**: 1.0.0
**마지막 업데이트**: 2025-10-28
**상태**: 프로덕션 데이터 수집 준비 완료
