# 튀김 AI 학습 가이드

## 📐 이미지 해상도 설정

### 카메라 사양
- **해상도**: 1920x1536 (GMSL UYVY)
- **비율**: 1.25 (5:4)
- **FPS**: 30

### 학습 해상도 (확정)
```yaml
imgsz: 800  # YOLO가 자동으로 800x640으로 처리
```

**중요**: `imgsz=800`으로 설정하면 YOLO가 비율을 유지하여 **800x640**으로 자동 리사이즈합니다.

### 왜 800x640인가?

| 항목 | 값 | 설명 |
|------|-----|------|
| **비율 일치** | 800÷640 = 1.25 | 카메라와 정확히 동일 ✅ |
| **패딩 불필요** | 0px | 검정색 영역 없음 ✅ |
| **충분한 디테일** | 512K 픽셀 | 작은 튀김도 식별 가능 ✅ |
| **실시간 추론** | ~3-4 FPS | Jetson Orin Nano 충분 ✅ |

### ❌ 다른 해상도를 사용하지 않는 이유

```python
# 432x432 (기존) - 정사각형
- 비율: 1.0 ≠ 1.25
- 위아래 검정 패딩 필요
- 정보 낭비

# 640x512 (대안) - 비율 일치하지만 작음
- 비율: 1.25 ✓
- 패딩 불필요 ✓
- 디테일 부족 (327K 픽셀)

# 800x640 (최종 선택) - 최적
- 비율: 1.25 ✓
- 패딩 불필요 ✓
- 충분한 디테일 (512K 픽셀) ✓
```

---

## 🚀 YOLO Segmentation 학습

### 1. 데이터셋 준비

```yaml
# frying.yaml
path: /path/to/dataset
train: images/train
val: images/val

names:
  0: food

# 이미지 해상도 설정
imgsz: 800  # YOLO가 800x640으로 자동 처리
```

### 2. 학습 명령어

```bash
# YOLOv8n-seg (나노 모델 - 추천)
yolo task=segment mode=train \
  model=yolov8n-seg.pt \
  data=frying.yaml \
  epochs=100 \
  imgsz=800 \
  batch=16 \
  rect=True \
  device=0

# rect=True: 비율 유지하면서 리사이즈 (800x640으로 자동 조정)
# batch=16: GPU 메모리에 따라 조정 (부족하면 8 또는 4)
```

### 3. 고급 옵션

```bash
# 더 나은 성능을 위한 설정
yolo task=segment mode=train \
  model=yolov8n-seg.pt \
  data=frying.yaml \
  epochs=150 \
  imgsz=800 \
  batch=16 \
  rect=True \
  device=0 \
  patience=50 \
  save=True \
  augment=True \
  hsv_h=0.015 \
  hsv_s=0.7 \
  hsv_v=0.4 \
  degrees=0 \
  translate=0.1 \
  scale=0.5 \
  flipud=0.5 \
  mosaic=1.0
```

### 4. 모델 선택

| 모델 | 크기 | 속도 | 정확도 | 추천 |
|------|------|------|--------|------|
| yolov8n-seg | 3.4M | 빠름 | 중간 | ✅ Jetson 추천 |
| yolov8s-seg | 11.8M | 보통 | 높음 | 정확도 우선 시 |
| yolov8m-seg | 27.3M | 느림 | 매우 높음 | GPU 충분 시 |

---

## ⚙️ Jetson 설정

### config_jetson2.json

```json
{
  "frying_seg_model": "frying_seg_v2.pt",
  "frying_seg_imgsz": 800,
  "frying_seg_conf": 0.05,
  "frying_seg_mask_thresh": 0.2,
  "frying_infer_fps": 5
}
```

### 추론 흐름

```
카메라 읽기 (1920x1536)
    ↓
원본 프레임 사용 (패딩 없음)
    ↓
YOLO 추론 (자동 리사이즈: 800x640)
    ↓
마스크 출력 (1920x1536로 복원)
    ↓
색상 분석 + 탈탈 감지
```

---

## 📊 성능 예상

### 학습
- **시간**: ~20-30시간 (100 epochs, RTX 3090 기준)
- **배치 크기**: 16 (GPU 메모리 24GB)
- **데이터셋**: ~5000장 권장

### 추론 (Jetson Orin Nano)
- **FPS**: 3-4 (800x640 입력)
- **지연시간**: ~250ms
- **충분성**: ✅ 5 FPS 설정으로 여유 있음

---

## 🔧 학습 후 배포

### 1. 모델 복사
```bash
# WSL2에서 학습 완료 후
scp runs/segment/train/weights/best.pt jetson:/home/yjk/jetson-food-ai/jetson2_frying_ai/frying_seg_v3.pt
```

### 2. Config 업데이트
```json
{
  "frying_seg_model": "frying_seg_v3.pt",
  "frying_seg_imgsz": 800
}
```

### 3. 테스트
```bash
cd ~/jetson-food-ai/jetson2_frying_ai

# 배치 시뮬레이션으로 먼저 테스트
python3 batch_simulation.py ~/AI_Data/FryingData/session_xxx

# 실제 시스템에 적용
python3 JETSON2_INTEGRATED.py
```

---

## 📝 체크리스트

학습 전:
- [ ] 데이터셋 레이블링 완료 (Roboflow/CVAT)
- [ ] frying.yaml에서 `imgsz: 800` 설정
- [ ] 학습/검증 데이터 분리 (80/20)

학습 중:
- [ ] TensorBoard로 loss 모니터링
- [ ] Validation mAP 확인 (>0.7 목표)
- [ ] 과적합 체크 (train loss << val loss)

배포 전:
- [ ] config_jetson2.json에서 `frying_seg_imgsz: 800` 확인
- [ ] 배치 시뮬레이션으로 정확도 테스트
- [ ] 실제 튀김 데이터로 검증

---

## 🎯 기대 효과

✅ **정확도 향상**: 비율 일치 + 고해상도
✅ **안정적 추론**: 패딩 없어서 일관성 증가
✅ **작은 객체 감지**: 512K 픽셀로 디테일 확보
✅ **실시간 가능**: Jetson에서 3-4 FPS 충분

---

**최종 확정: 800x640 (imgsz=800)**
