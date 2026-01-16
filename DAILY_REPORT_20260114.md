# 일간 작업 보고서

**작업 일자**: 2026년 1월 14일
**작업자**: Youngjin
**시스템**: Jetson #2 (튀김 AI)
**작업 분류**: 기능 추가 및 최적화

---

## 📋 작업 요약

JETSON2 시스템에 **SimpleColorChecker** 기능을 통합하여 튀김 색상 변화를 실시간으로 측정하고 데이터를 수집할 수 있도록 개선하였습니다. 또한 카메라 모듈을 원래 안정 버전으로 복구하여 프리징 문제를 해결하였습니다.

---

## ✅ 완료된 작업

### 1. SimpleColorChecker 통합 (튀김 색상 변화 측정)

**목적**: 튀김 과정에서 색상 변화를 정량적으로 측정하여 익힘 정도를 추적

**구현 내용**:
- `simple_checker.color_checker` 모듈을 JETSON2_INTEGRATED.py에 통합
- POT1 (좌측 튀김), POT2 (우측 튀김) 각각 독립적인 ColorChecker 인스턴스 생성
- 실시간 색상 변화량 측정 및 화면 표시

**작동 방식**:
```
1. 튀김 투입 감지 (MQTT 메시지 or 로봇 상태)
   ↓
2. Baseline 자동 설정 (탈탈 직후 첫 프레임 색상 저장)
   ↓
3. 매 프레임(50ms)마다 색상 변화 측정 및 화면 표시
   ↓
4. 매 1초마다 이미지 + 메타데이터 저장
```

**화면 표시**:
- 위치: 튀김 화면 좌측 상단
- 내용:
  - `Color: X.X` (색상 변화량, 0~25.0)
  - `Progress: X%` (진행도, 0~100%)
- 색상: 노란색 (Cyan)

---

### 2. 메타데이터 저장 기능 추가

**저장 경로**:
```
~/AI_Data/POT1Data/session_YYYYMMDD_HHMMSS/meta/meta_HHMMSS_mmm.json
~/AI_Data/POT2Data/session_YYYYMMDD_HHMMSS/meta/meta_HHMMSS_mmm.json
```

**메타데이터 구조 예시**:
```json
{
  "timestamp": "2026-01-14 13:02:45.123",
  "frame_id": "130245_123",
  "pot": "pot1",
  "OilTempL": 165.3,
  "ProbeTempL": 72.1,
  "color_diff": 12.45,
  "progress_pct": 49.8
}
```

**추가된 필드**:
- `color_diff`: 기준 색상 대비 변화량 (0~25.0)
- `progress_pct`: 익힘 진행도 (0~100%)

---

### 3. 카메라 모듈 복구 (gst_camera.py)

**문제**: 다운샘플링 버전 사용으로 인한 예상치 못한 동작

**해결**:
- 원래 안정 버전(ORIGINAL_BACKUP)으로 복구
- subprocess 방식 (gst-launch-1.0 외부 프로세스)
- 풀 해상도 유지: 1920×1536 @ 30fps

**복구 내용**:
| 항목 | 이전 (다운샘플링) | 현재 (복구) |
|------|------------------|------------|
| 방식 | GStreamer Python Binding | subprocess (gst-launch) |
| 해상도 | 960×768 (자동 축소) | 1920×1536 (풀 해상도) |
| FPS | 10fps (자동 축소) | 30fps (원본) |
| 상태 | 불안정 가능성 | **안정 확인됨** |

---

### 4. 백업 파일 관리

**생성된 백업**:
- `JETSON2_INTEGRATED_MODIFIED_BACKUP.py`: SimpleColorChecker 통합 버전
- `gst_camera_ORIGINAL_BACKUP.py`: 원본 카메라 모듈
- `gst_camera_DOWNSAMPLING_BACKUP_20260114_133214.py`: 다운샘플링 버전 (참고용)
- `JETSON2_INTEGRATED_BACKUP_20260114_132045.py`: 작업 전 운영 버전

---

## 📊 작동 프로세스

### POT1 (좌측 튀김) 예시

| 시간 | 동작 | color_diff | 저장 |
|------|------|-----------|------|
| 0초 | 튀김 투입 → Baseline 설정 | 0.0 | - |
| 1초 | 색상 측정 | 2.3 |  이미지 + JSON |
| 2초 | 색상 측정 | 5.1 |  이미지 + JSON |
| ... | ... | ... | ... |
| 60초 | 색상 측정 | 18.7 |  이미지 + JSON |

**매 프레임 (50ms)**: 화면에 실시간 표시
**매 1초**: 이미지 + 메타데이터 저장

---

## 🎯 적용 범위

### POT1 (좌측 튀김)
- ✅ SimpleColorChecker 적용
- ✅ 실시간 화면 표시
- ✅ 메타데이터 저장
- ✅ 독립 동작

### POT2 (우측 튀김)
- ✅ SimpleColorChecker 적용
- ✅ 실시간 화면 표시
- ✅ 메타데이터 저장
- ✅ 독립 동작

### 바켓 카메라 (좌/우)
- ❌ SimpleColorChecker 미적용 (바켓 감지만 수행)

---

## 🔧 Git 이력

**커밋 해시**: `3fb16c5`

**커밋 메시지**:
```
Restore original gst_camera and add SimpleColorChecker with color_diff tracking

- Restore gst_camera.py to ORIGINAL version (subprocess, full resolution 1920x1536@30fps)
- Add SimpleColorChecker integration to JETSON2_INTEGRATED.py
- Add color_diff and progress_pct to POT1/POT2 metadata JSON
- Backup downsampling version for reference
```

**변경 통계**:
- 4 files changed
- 4,465 insertions(+)
- 4 deletions(-)

**푸시 완료**:
```
To https://github.com/foody-j/jetson-food-ai.git
   68dce68..3fb16c5  main -> main
```

---

## 🧪 테스트 현황

### 개발 환경 (WSL2)
- ✅ 코드 통합 완료
- ✅ Git 커밋/푸시 완료

### 현장 환경 (Jetson #2)
- ✅ Git pull 완료
- ✅ 프로그램 실행 확인
- ✅ 카메라 4대 정상 작동
- ⏳ 실제 튀김 데이터 수집 예정 (2026-01-15)

---

## 📝 예상 효과

1. **정량적 데이터 수집**: 색상 변화를 숫자로 추적하여 AI 학습 데이터 품질 향상
2. **익힘 정도 추적**: 진행도(%)로 튀김 상태를 객관적으로 판단 가능
3. **데이터 분석 용이**: 메타데이터에 color_diff 포함으로 시계열 분석 가능
4. **안정성 확보**: 검증된 카메라 모듈 사용으로 프리징 문제 해결

---

## 🔜 향후 계획

### 단기 (1주 이내)
- [ ] 실제 튀김 공정에서 color_diff 데이터 수집
- [ ] 수집된 데이터 검증 (온도, 시간, color_diff 상관관계 분석)
- [ ] color_threshold 값 조정 필요 여부 확인 (현재 25.0)

### 중기 (1개월 이내)
- [ ] color_diff 기반 자동 알림 기능 추가 (예: 80% 익었을 때 알림)
- [ ] 히스토리 그래프 시각화 (색상 변화 추이)
- [ ] 음식 종류별 color_diff 패턴 분석

---

## 📌 참고 사항

### SimpleColorChecker 파라미터
- `color_threshold`: 25.0 (최대 색상 변화량)
- 측정 방식: HSV 색공간에서 L2 거리 계산
- Baseline: 탈탈 직후 첫 프레임 자동 설정

### 데이터 수집 조건
- POT1/POT2 데이터 수집이 활성화된 상태에서만 color_diff 측정
- 수집 간격: 1초 (collection_interval)
- 저장 형식: JPEG 이미지 + JSON 메타데이터

### 주의 사항
- Baseline 설정 후에는 reset되기 전까지 동일한 기준 유지
- 새로운 조리 시작 시 자동으로 reset됨 (MQTT 메시지 or 로봇 상태)

---

## 📎 관련 파일

### 수정된 주요 파일
- `jetson2_frying_ai/JETSON2_INTEGRATED.py` (171KB → 174KB)
- `jetson2_frying_ai/gst_camera.py` (복구됨)

### 새로 추가된 파일
- `jetson2_frying_ai/simple_checker/color_checker.py`
- `jetson2_frying_ai/simple_checker/color_utils.py`
- `jetson2_frying_ai/simple_checker/demo.py`

### 백업 파일
- `JETSON2_INTEGRATED_MODIFIED_BACKUP.py`
- `gst_camera_ORIGINAL_BACKUP.py`
- `gst_camera_DOWNSAMPLING_BACKUP_20260114_133214.py`

---

## 💡 기술 상세

### SimpleColorChecker 알고리즘
1. **전처리**: BGR → HSV 변환
2. **영역 추출**: HSV 임계값으로 음식 영역 마스크 생성
3. **색상 통계**: 마스크 영역의 평균 HSV 값 계산
4. **거리 계산**: Baseline과 현재 색상 간 L2 거리
5. **진행도 산출**: `min(color_diff / threshold, 1.0) × 100`

### 카메라 파이프라인 (복구 버전)
```bash
gst-launch-1.0 -q \
  v4l2src device=/dev/video0 io-mode=2 ! \
  video/x-raw,format=UYVY,width=1920,height=1536,framerate=30/1 ! \
  videoconvert ! \
  video/x-raw,format=BGR ! \
  fdsink
```

---

**보고서 작성**: Claude Code (Sonnet 4.5)
**검토**: Youngjin
**승인**: -

---

*이 보고서는 jetson-food-ai 프로젝트의 개발 이력을 기록하기 위해 작성되었습니다.*
