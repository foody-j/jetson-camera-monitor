# GstCamera 최적화 완료 (2026-01-10)

## 문제 상황
- **증상**: 4카메라 장기 운용(3주) 시 프리징/프로세스 뻗음
- **원인**:
  - 초당 1GB 메모리 할당 (4카메라 × 30fps × 8.8MB/frame × 2회 copy)
  - stdout 파이프 백프레셔 (GStreamer 블로킹 가능)
  - bytes 재할당 및 메모리 단편화

---

## 적용된 개선 사항

### ✅ Phase 1: GStreamer 파이프라인 최적화

**변경 사항**:
```python
# 전: 1920x1536@30fps, 8.8MB/frame
# 후: 960x768@10fps, 2.2MB/frame (기본값)
```

**추가 요소**:
- `videorate`: FPS 감소 (30fps → 10fps)
- `videoscale`: 해상도 감소 (1920x1536 → 960x768)
- `queue leaky=downstream`: 백프레셔 방지 (최신 프레임만 유지)

**효과**:
- 대역폭: 264MB/s → 22MB/s (12배 감소)
- 파이프 I/O 부하 대폭 감소
- GStreamer 블로킹 위험 제거

---

### ✅ Phase 2: 더블버퍼 + 제로카피

**변경 사항**:

1. **더블버퍼** (고정 할당):
   ```python
   # 프로그램 시작 시 2개 버퍼만 할당
   self.buffer_pool = [
       np.empty((height, width, 3), dtype=np.uint8),  # 버퍼 A
       np.empty((height, width, 3), dtype=np.uint8)   # 버퍼 B
   ]
   ```

2. **bytearray + memoryview** (재할당 제거):
   ```python
   buffer = bytearray()            # mutable
   buffer.extend(chunk)            # in-place, 재할당 없음
   frame_view = memoryview(buffer) # 제로카피 슬라이싱
   ```

3. **np.copyto** (덮어쓰기):
   ```python
   np.copyto(self.buffer_pool[next_idx], frame)  # 할당 없음
   ```

4. **read() 제로카피**:
   ```python
   return True, self.buffer_pool[self.read_index]  # 참조만 반환
   ```

**효과**:
- 메모리 할당: 1GB/s → ~0MB/s (99% 감소)
- GC 부하 대폭 감소
- 메모리 단편화 제거

---

## 성능 비교 (예상)

| 항목 | 개선 전 | 개선 후 | 감소율 |
|------|---------|---------|--------|
| **프레임 크기** | 8.8MB | 2.2MB | 75% ↓ |
| **FPS** | 30 | 10 | 67% ↓ |
| **대역폭 (4카메라)** | 1,056MB/s | 88MB/s | 92% ↓ |
| **메모리 할당** | ~2GB/s | ~0MB/s | 99% ↓ |

---

## 백업 파일

```
jetson2_frying_ai/gst_camera_ORIGINAL_BACKUP.py   (fdsink 버전)
jetson1_monitoring/gst_camera_ORIGINAL_BACKUP.py  (appsink 버전)
```

롤백 방법:
```bash
# Jetson2
cp jetson2_frying_ai/gst_camera_ORIGINAL_BACKUP.py jetson2_frying_ai/gst_camera.py

# Jetson1
cp jetson1_monitoring/gst_camera_ORIGINAL_BACKUP.py jetson1_monitoring/gst_camera.py
```

---

## 테스트 방법

### 1. 단일 카메라 테스트 (30초)
```bash
cd /home/yjk/jetson-food-ai
python3 test_camera_optimized.py --device 0 --duration 30
```

### 2. 장기 안정성 테스트 (10분)
```bash
python3 test_camera_optimized.py --device 0 --duration 600
```

### 3. 통합 프로그램 테스트
```bash
# Jetson2
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py

# 실시간 메모리 모니터링 (별도 터미널)
watch -n 1 "ps aux | grep JETSON2 | grep -v grep"
```

---

## 주의 사항

### ⚠️ read() 반환값 처리

**변경 전**:
```python
ret, frame = cam.read()  # frame은 복사본
frame[0, 0] = [255, 0, 0]  # 수정 가능 (독립적)
```

**변경 후**:
```python
ret, frame = cam.read()  # frame은 참조 (읽기 전용!)
# frame[0, 0] = [255, 0, 0]  # ❌ 금지! 버퍼 오염 가능

# 수정이 필요하면 명시적으로 복사:
frame_copy = frame.copy()
frame_copy[0, 0] = [255, 0, 0]  # ✅ OK
```

**영향 받는 코드**:
- YOLO 추론: 문제없음 (읽기만 함)
- cv2.imwrite: 문제없음 (읽기만 함)
- cv2.putText: ⚠️ 주의! 프레임 직접 수정 → copy() 필요
- OpenCV 변환 (cvtColor 등): 보통 새 배열 반환하므로 OK

---

## 해상도/FPS 조정

기본값이 너무 낮다면 조정 가능:

```python
# JETSON2_INTEGRATED.py 또는 JETSON1_INTEGRATED.py에서

cam = GstCamera(
    device_index=0,
    width=1920,
    height=1536,
    fps=30,
    # 출력 설정 (None이면 자동: width//2, height//2, fps//3)
    output_width=1280,   # 1280x720 (HD)
    output_height=720,
    output_fps=15        # 15fps
)
```

**권장 설정**:
- **저부하** (모니터링용): 640x480@10fps
- **중간** (일반 AI): 960x540@10fps (기본값)
- **고품질** (세밀한 감지): 1280x720@15fps

---

## 다음 단계 (선택적)

### Phase 3: 순환 버퍼 (미적용)
`del buffer[:self.frame_size]`의 memmove 오버헤드 제거. Phase 2로 충분하면 생략 가능.

### appsink 전환 (Jetson2)
Jetson1처럼 appsink 사용하면 파이프 I/O 제거 가능. Python GStreamer binding 필요.

### NVMM 제로카피
GPU 메모리 직접 접근. 복잡도 높고, YOLO가 이미 GPU 쓰므로 효과 제한적.

### systemd watchdog
```ini
[Service]
WatchdogSec=30
Restart=on-failure
RestartSec=5
```

---

## 문제 발생 시

### 1. 카메라 안 보임
```bash
ls -l /dev/video*
cd ~/jetson-food-ai/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3
sudo ./quick_bring_up.sh
```

### 2. GStreamer 에러
```bash
# 파이프라인 직접 테스트
gst-launch-1.0 v4l2src device=/dev/video0 ! \
  video/x-raw,format=UYVY,width=1920,height=1536,framerate=30/1 ! \
  videorate ! video/x-raw,framerate=10/1 ! \
  videoscale ! video/x-raw,width=960,height=768 ! \
  videoconvert ! video/x-raw,format=BGR ! \
  queue max-size-buffers=1 leaky=downstream ! \
  fakesink
```

### 3. 메모리 계속 증가
- Phase 2가 제대로 적용되었는지 확인
- `frame.copy()` 호출이 남아있는지 검색
- 소비자 코드에서 프레임을 계속 쌓고 있는지 확인

---

## 변경 이력

- **2026-01-10**: Phase 1 + Phase 2 적용 (videorate/videoscale + 더블버퍼)
- **기존**: 원본 fdsink/appsink 구현
