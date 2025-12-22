# GMSL 카메라 아키텍처

## 개요

NVIDIA Jetson Orin Nano에서 GMSL2 카메라 4대를 운용하는 시스템 구조.

---

## 하드웨어 구조

```
카메라 모듈 (GMSL2) → SerDes 변환 → Jetson Orin Nano
                     (Serializer)    (Deserializer)
```

- **GMSL2**: Gigabit Multimedia Serial Link - 차량용 고속 영상 전송 규격
- **SerDes**: Serializer(카메라) + Deserializer(Jetson) 쌍으로 동작
- 한 케이블로 영상 + 전원 + 제어신호 전송

### SerDes 구성

| 구성요소 | 위치 | 역할 |
|----------|------|------|
| Serializer | 카메라 모듈 내장 | 영상 데이터를 직렬 신호로 변환 |
| Deserializer | SG4A 보드 | 직렬 신호를 다시 병렬(CSI)로 변환 |

**SG4A-ORIN-NANO-G2Y-A1** = Deserializer 보드
- 카메라 4대 → SG4A → Jetson CSI 연결
- GMSL2 신호를 MIPI CSI로 변환

---

## 소프트웨어 스택

```
┌─────────────────────────────────────────┐
│      Python 앱 (JETSON2_INTEGRATED.py)  │
│  - Tkinter GUI                          │
│  - YOLO 추론                            │
│  - MQTT 통신                            │
│  - 이미지 저장                          │
└────────────────┬────────────────────────┘
                 │ read() 호출
                 ▼
┌─────────────────────────────────────────┐
│         GstCamera (gst_camera.py)       │
│  - subprocess로 gst-launch 실행         │
│  - stdout에서 BGR 프레임 읽기           │
│  - threading으로 비동기 처리            │
└────────────────┬────────────────────────┘
                 │ subprocess 통신
                 ▼
┌─────────────────────────────────────────┐
│        GStreamer (gst-launch-1.0)       │
│  - 파이프라인 실행                      │
│  - 플러그인 체인 (src→convert→sink)     │
└────────────────┬────────────────────────┘
                 │ ioctl 호출
                 ▼
┌─────────────────────────────────────────┐
│           V4L2 (Video4Linux2)           │
│  - 리눅스 비디오 캡처 API               │
│  - /dev/video0~3 디바이스               │
└────────────────┬────────────────────────┘
                 │ 드라이버 호출
                 ▼
┌─────────────────────────────────────────┐
│            NVIDIA 드라이버              │
│  - nvcsi: CSI 수신                      │
│  - vi: Video Input 처리                 │
│  - isp: 이미지 시그널 프로세싱          │
└────────────────┬────────────────────────┘
                 │ MIPI CSI 신호
                 ▼
┌─────────────────────────────────────────┐
│       SG4A 보드 (Deserializer)          │
│  - MAX96712 칩                          │
│  - GMSL2 → MIPI CSI 변환                │
└────────────────┬────────────────────────┘
                 │ GMSL2 동축케이블
                 ▼
┌─────────────────────────────────────────┐
│        카메라 모듈 (Serializer)         │
│  - 이미지 센서                          │
│  - GMSL2 Serializer 내장                │
└─────────────────────────────────────────┘
```

---

## GStreamer 파이프라인

### 파이프라인이란?
데이터가 흐르는 "파이프" 연결. 각 단계(element)를 `!`로 연결.

### 현재 사용 중인 파이프라인

```bash
v4l2src device=/dev/video0 io-mode=2 !
video/x-raw,format=UYVY,width=1920,height=1536,framerate=30/1 !
videoconvert !
video/x-raw,format=BGR !
fdsink fd=1 sync=false
```

### 각 Element 설명

| Element | 역할 |
|---------|------|
| `v4l2src` | 카메라에서 영상 캡처 (Video4Linux2) |
| `device=/dev/video0` | 어떤 카메라 쓸지 |
| `io-mode=2` | MMAP 방식 (메모리 효율적) |
| `video/x-raw,format=UYVY` | 카메라 출력 포맷 (YUV 계열) |
| `videoconvert` | 색상 포맷 변환 |
| `video/x-raw,format=BGR` | OpenCV가 쓰는 BGR로 변환 |
| `fdsink fd=1` | stdout으로 출력 (Python이 읽음) |
| `sync=false` | 실시간 처리 (버퍼 안 쌓음) |

### 데이터 흐름

```
v4l2src: 커널에서 프레임 가져옴
    ↓ UYVY (YUV422)
videoconvert: CPU에서 색상 변환
    ↓ BGR
fdsink: stdout으로 출력
```

---

## 각 계층 상세

### 1. Python 앱 계층

```python
# 프레임 읽기
ret, frame = self.frying_left_cap.read()
if ret:
    # YOLO 추론
    results = self.model(frame)
    # GUI 업데이트
    self.update_preview(frame)
```

### 2. GstCamera 계층

```python
# subprocess로 gst-launch 실행
self.process = subprocess.Popen(gst_cmd, stdout=PIPE)

# 별도 스레드에서 프레임 읽기
def _read_frames(self):
    while self.is_running:
        chunk = self.process.stdout.read(frame_size)
        frame = np.frombuffer(chunk).reshape(H, W, 3)
        self.latest_frame = frame
```

### 3. V4L2 계층

```bash
# 카메라 확인
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all

# 지원 포맷 확인
v4l2-ctl -d /dev/video0 --list-formats-ext
```

### 4. NVIDIA 드라이버 계층

```
nvcsi ← CSI 수신 (MIPI 신호 받음)
   ↓
vi (Video Input) ← 프레임 버퍼링
   ↓
isp (Image Signal Processor) ← 디베이어링, 노이즈 제거 등
   ↓
V4L2 버퍼 ← 앱에서 읽을 수 있게 준비
```

> **ISP 과부하가 4대 동시 프리징의 원인!**

### 5. SG4A (Deserializer)

```
GMSL2 입력 (4채널) → MAX96712 칩 → MIPI CSI 출력 (4레인)
```

---

## 데이터 흐름 (1프레임)

```
1. 센서가 빛 → 전기신호 변환 (1920x1536 픽셀)
2. Serializer가 직렬화 → 동축케이블로 전송
3. Deserializer가 역직렬화 → MIPI CSI로 Jetson 전달
4. nvcsi가 CSI 수신
5. vi가 메모리에 프레임 저장
6. isp가 UYVY 포맷으로 변환
7. V4L2가 /dev/video0 버퍼에 노출
8. gst-launch가 v4l2src로 읽음
9. videoconvert가 UYVY→BGR 변환
10. fdsink가 stdout으로 출력
11. Python이 읽어서 numpy array로 변환
12. YOLO가 추론
13. Tkinter가 GUI에 표시
```

**총 지연시간**: 약 50~100ms (카메라→화면)

---

## 3-of-4 카메라 전략

### 문제
- Jetson Orin Nano의 ISP가 4개 스트림 동시 처리 시 병목
- GMSL2 4채널 + ISP 처리 = 프리징

### 해결
최대 3대까지만 동시 스트리밍

### 구현 (Jetson2)

```
시작 시:
  video2 (바켓L) → ON
  video3 (바켓R) → ON
  video0 (튀김L) → 대기
  video1 (튀김R) → 대기

투입 MQTT 수신 시:
  video0 또는 video1 → 동적 ON (GstCamera.start())

배출 50초 후:
  해당 카메라 → OFF (GstCamera.stop())
```

### 관련 메서드

```python
def start_frying_camera(self, pot_num):
    """튀김솥 카메라 동적 시작"""
    self.frying_left_cap = GstCamera(...)
    self.frying_left_cap.start()
    self.frying_left_streaming = True

def stop_frying_camera(self, pot_num):
    """튀김솥 카메라 동적 중지"""
    self.frying_left_cap.stop()
    self.frying_left_cap = None
    self.frying_left_streaming = False
```

---

## 카메라 구성

### Jetson1 (볶음 모니터링)
| 카메라 | 디바이스 | 용도 |
|--------|----------|------|
| video0 | 사람 감지 | YOLO로 사람 탐지 |
| video1 | 볶음 왼쪽 | 볶음솥 모니터링 |
| video2 | 볶음 오른쪽 | 볶음솥 모니터링 |

### Jetson2 (튀김 AI)
| 카메라 | 디바이스 | 용도 | 상태 |
|--------|----------|------|------|
| video0 | 튀김 왼쪽 (POT1) | 튀김 AI 분석 | 동적 ON/OFF |
| video1 | 튀김 오른쪽 (POT2) | 튀김 AI 분석 | 동적 ON/OFF |
| video2 | 바켓 왼쪽 | 바켓 감지 | 항상 ON |
| video3 | 바켓 오른쪽 | 바켓 감지 | 항상 ON |

---

## 디버깅 명령어

```bash
# 카메라 디바이스 확인
ls -la /dev/video*

# 카메라 상세 정보
v4l2-ctl -d /dev/video0 --all

# 지원 포맷
v4l2-ctl -d /dev/video0 --list-formats-ext

# GStreamer 테스트
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink

# 드라이버 로드 확인
lsmod | grep -E "nvcsi|vi|isp"

# dmesg에서 카메라 관련 로그
dmesg | grep -i -E "camera|gmsl|max96712|video"
```
