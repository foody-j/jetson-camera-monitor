# Jetson1 카메라 프리징 문제 분석 (2026-01-20)

## 문제 증상

- **발생 시점**: 2026-01-20 오후
- **현상**:
  - GUI에서 카메라 프레임이 멈춰있음
  - 1970년 타임스탬프 발생
  - `gst-launch` 직접 실행 시에는 정상 작동
  - systemctl 서비스로 실행 시 프리징

## 원인 분석

### 범인 커밋: `31ccf45` (2026-01-16)

**커밋 메시지**: "Replace temperature labels with color_diff in GUI"

**변경 내용**:
- `gst_camera.py`에 `output_width`, `output_height`, `output_fps` 파라미터 추가
- **문제**: 기본값을 원본의 절반/1/3로 설정
  ```python
  self.output_width = output_width if output_width else width // 2      # 960
  self.output_height = output_height if output_height else height // 2  # 768
  self.output_fps = output_fps if output_fps else max(10, fps // 3)    # 10fps
  ```

### 커밋 타임라인

```
abf7d18 (2025-12-XX) - gst_camera.py 최초 생성
    → 원본 해상도 사용, output 파라미터 없음

83b2599 (2026-01-XX) - Remove camera auto-restart
    → 여전히 원본 해상도 1920x1536@30fps

31ccf45 (2026-01-16) ⚠️ 문제 시작!
    → output 파라미터 추가하면서 기본값 960x768@10fps
    → videorate, videoscale 추가

794960d~현재 (2026-01-20)
    → 계속 다운스케일 상태 유지
```

### 왜 갑자기 안 됐을까?

1. **31ccf45 이전**: 1920x1536@30fps 원본 그대로 → 정상 작동
2. **31ccf45 이후**:
   - GStreamer 파이프라인에 `videorate + videoscale` 추가
   - 960x768@10fps로 다운스케일
   - 3개 카메라 동시 처리 시 타이밍 문제 발생
   - 프레임 동기화 실패 → 프리징

## 확인된 사실

### 카메라 하드웨어: 정상 ✅
```bash
ls -l /dev/video*
# video0, video1, video2 존재

lsmod | grep sgx
# sgx_yuv_gmsl2, max96712 로드됨

gst-launch-1.0 v4l2src device=/dev/video2 ! ...
# 단일 카메라 직접 실행 → 정상 작동
```

### JETSON1_INTEGRATED.py: 문제 없음 ✅
```python
# 라인 1473, 1494, 1515
GstCamera(
    device_index=X,
    width=1920,
    height=1536,
    fps=30
)
# output_width, output_height, output_fps 안 넘김
# → gst_camera.py 기본값 사용 (960x768@10fps)
```

## 시도한 해결 방법

### ❌ 실패: 기본값을 원본 해상도로 변경

**커밋**: `12606bb` (2026-01-20 17:15)
```python
self.output_width = output_width if output_width else width      # 1920
self.output_height = output_height if output_height else height  # 1536
self.output_fps = output_fps if output_fps else fps              # 30
```

**결과**:
- 로그: `Input: 1920x1536@30fps → Output: 1920x1536@30fps (8.44MB)`
- 여전히 프리징 발생
- 추정 원인: 3개 카메라 × 8.44MB × 30fps = 메모리/대역폭 폭발

**Revert**: `2b024d5` (2026-01-20 17:20) → 원래대로 960x768@10fps

## 해결책

### 옵션 1: 83b2599로 롤백 (권장) ✅

**장점**:
- 이전에 정상 작동하던 버전
- output 파라미터 없음 (단순함)
- videorate/videoscale 없음

**단점**:
- 31ccf45 이후 추가된 최적화(더블버퍼 등) 날아감

**적용 방법**:
```bash
cd ~/jetson-food-ai
git checkout 83b2599 -- jetson1_monitoring/gst_camera.py
# 테스트 후 커밋
```

### 옵션 2: JETSON1_INTEGRATED.py에서 명시적 전달

```python
self.auto_cap = GstCamera(
    device_index=CAMERA_INDEX,
    width=1920,
    height=1536,
    fps=30,
    output_width=1920,   # 명시적 전달
    output_height=1536,
    output_fps=30
)
```

**문제**: 12606bb에서 실패했듯이 여전히 프리징 가능성

### 옵션 3: Jetson2 방식으로 교체

- subprocess + fdsink 방식
- Jetson2는 정상 작동 중
- 대규모 리팩토링 필요

## 다음 단계

1. **83b2599 버전으로 테스트** (가장 안전)
2. 정상 작동 확인 후 커밋
3. 향후 최적화는 점진적으로 적용

## 교훈

- **급한 커밋은 독**: 31ccf45에서 GUI 라벨 바꾸면서 카메라 코드까지 건드림
- **기본값 주의**: output 파라미터 기본값이 downscale인데 호출 측에서 몰랐음
- **점진적 테스트**: 3개 카메라 동시 실행 환경에서 충분한 테스트 없이 배포

---

**작성**: 2026-01-20
**작성자**: Claude Code
**상태**: 분석 완료, 해결 대기
