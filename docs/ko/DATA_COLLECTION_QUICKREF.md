# 데이터 수집 빠른 참조

## 🚀 빠른 시작

### 데이터 수집기 실행
```bash
cd frying_ai
python web_viewer.py
# 접속: http://localhost:5000
```

### 세션 한 번 수집

1. **준비**: 기름 가열, 카메라 위치 조정, 센서 연결
2. **시작**: 음식 종류 입력 → "세션 시작" 클릭
3. **모니터링**: 튀김 과정 관찰 (2-5분)
4. **마킹**: 프로브 삽입 → 온도 읽기 → "완료 마킹" 클릭
5. **중지**: "세션 중지" 클릭
6. **확인**: `frying_dataset/`에서 데이터 확인

---

## 🎯 정답 레이블 가이드

| 음식 | 내부 온도 | 시각적 단서 |
|------|----------|------------|
| 치킨 | 74°C (165°F) | 황금색 갈색 |
| 새우 | 63°C (145°F) | 분홍색/불투명 |
| 감자 | N/A | 황금색 노랑 |
| 생선 | 63°C (145°F) | 불투명, 벗겨짐 |

**중요**: 정확한 정답 레이블을 위해 항상 음식 프로브 온도계를 사용하세요!

---

## 📊 데이터 구조

```
frying_dataset/
└── foodtype_YYYYMMDD_HHMMSS/
    ├── images/                  # 순차적 프레임
    │   ├── t0000.jpg
    │   └── ...
    ├── session_data.json        # 메타데이터 + 완료 시간
    └── sensor_log.csv           # 온도 시계열
```

---

## ✅ 세션 체크리스트

### 이전
- [ ] 카메라 초점 맞춤 및 장착
- [ ] 센서 연결
- [ ] 웹 뷰어 실행
- [ ] 프로브 온도계 준비

### 중간
- [ ] 음식 종류로 세션 시작
- [ ] 비디오 피드 모니터링
- [ ] 완성도 단서 관찰

### 완료
- [ ] 프로브 온도계 삽입
- [ ] 안정적인 판독값 대기
- [ ] "완료 마킹" 클릭
- [ ] 프로브 온도 + 메모 입력

### 이후
- [ ] 세션 중지
- [ ] 확인: `ls frying_dataset/SESSION_ID/images/ | wc -l`
- [ ] 확인: `cat frying_dataset/SESSION_ID/session_data.json`

---

## 🤖 ML 파이프라인

### 1. 특징 추출
```bash
cd frying_ai
python food_segmentation.py --batch
```

### 2. 모델 학습
```python
from sklearn.ensemble import RandomForestRegressor
import pandas as pd

# 데이터 로드
df = load_all_sessions()  # 사용자 함수

# 특징 및 목표
X = df[['brown_ratio', 'golden_ratio', 'mean_hue', 'oil_temp', 'elapsed_time']]
y = df['time_to_completion']

# 학습
model = RandomForestRegressor(n_estimators=100)
model.fit(X, y)

# 평가
print(f"MAE: {mean_absolute_error(y_test, y_pred):.2f}초")
```

### 3. 배포
```python
import joblib

# 저장
joblib.dump(model, 'models/predictor.pkl')

# 로드 및 예측
model = joblib.load('models/predictor.pkl')
time_left = model.predict(current_features)
```

---

## 🎯 목표 지표

| 지표 | 목표 | 설명 |
|--------|--------|-------------|
| 세션 | 200+ | 총 수집 |
| 음식당 | 40+ | 각 종류 |
| MAE | <10초 | 예측 오차 |
| R² | >0.85 | 모델 적합도 |

---

## 🔧 검증

```bash
# 세션 확인
ls -lh frying_dataset/SESSION_ID/

# 이미지 수 세기
ls frying_dataset/SESSION_ID/images/ | wc -l

# CSV 확인
head frying_dataset/SESSION_ID/sensor_log.csv

# 메타데이터 확인
cat frying_dataset/SESSION_ID/session_data.json | python -m json.tool
```

---

## ⚠️ 일반적인 실수

1. **완료 마킹 잊어버림** → 정답 레이블 없음!
2. **부정확한 프로브 판독** → 잘못된 레이블
3. **세션 중 카메라 움직임** → 일관성 없는 이미지
4. **센서 먼저 테스트 안 함** → 데이터 누락
5. **너무 일찍 중지** → 불완전한 세션

---

## 🔄 워크플로우

```
설정 → 세션 시작 → 모니터링 → 완료 마킹 → 중지 → 확인 → 반복
   ↓                                                              ↑
   └──────────────────────────────────────────────────────────────┘
                    (200+ 세션 수집)
                             ↓
                    특징 추출
                             ↓
                       모델 학습
                             ↓
                    평가 및 배포
```

---

## 📞 도움이 필요하신가요?

- **전체 가이드**: `docs/FRYING_AI_DATA_GUIDELINE.md`
- **시스템 가이드**: `docs/MONITORING_SYSTEM_GUIDE.md`
- **빠른 시작**: `QUICKSTART.md`
