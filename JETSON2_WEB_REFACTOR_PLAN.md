# 🔄 JETSON2_web.py 리팩토링 플랜

## 🎯 목표

**tkinter GUI 제거하고 headless + 웹 대시보드 전용으로 새로 만들기**

### 왜 리팩토링?
- 기존: tkinter GUI가 CPU 너무 먹음 (추론 시 GUI 뻑남)
- 목표: Headless + FastAPI 웹으로 CPU 효율화
- 방식: 기존 JETSON2_INTEGRATED.py 건드리지 말고 **새 파일** 작성

---

## 📊 CPU 사용량 분석 (기존)

### 기존 JETSON2_INTEGRATED.py 병목:

```
총 CPU 사용량: ~80-100%
├── AI 추론 (YOLO x2): ~40%
├── 카메라 캡처 (x4): ~15%
├── tkinter GUI 업데이트: ~25% ⚠️ 여기가 문제!
│   ├── PhotoImage 변환
│   ├── Label.config(image=...)
│   ├── root.update()
│   └── Canvas redraw
├── MQTT: ~3%
└── 기타: ~10%
```

**GUI 제거 시 예상:**
```
총 CPU: ~55-70% (25-30% 절감!)
```

---

## 🏗️ 새 아키텍처 (JETSON2_web.py)

```
┌─────────────────────────────────────────────────────┐
│  JETSON2_web.py (Headless + Web)                   │
├─────────────────────────────────────────────────────┤
│  1. 카메라 캡처 스레드 x4 (간소화)                   │
│     - GstCamera (그대로 사용)                       │
│     - GUI 변환 로직 제거                            │
│     - 최신 프레임만 유지 (deque maxlen=1)          │
│                                                     │
│  2. AI 추론 스레드 x2                               │
│     - Frying AI (POT 0, 1)                         │
│     - Observe AI (Bucket)                          │
│     - 프레임 큐에서 꺼내서 추론                      │
│                                                     │
│  3. MQTT 클라이언트                                 │
│     - 상태 발행                                     │
│     - 로봇 상태 구독                                │
│                                                     │
│  4. FastAPI 웹서버 (별도 스레드)                    │
│     ├── / : 2x2 대시보드                           │
│     ├── /mjpeg/cam{0-3} : MJPEG 스트림             │
│     ├── /api/status : 상태 JSON                    │
│     └── /api/config : 설정 조회/변경               │
│                                                     │
│  5. 메인 루프 (간소화)                              │
│     - signal handler                               │
│     - 헬스체크                                      │
│     - 로깅                                          │
└─────────────────────────────────────────────────────┘
```

---

## 📁 파일 구조

```
jetson2_frying_ai/
├── JETSON2_INTEGRATED.py       # 기존 (건드리지 않음!)
├── JETSON2_web.py               # 새 파일 (리팩토링 버전)
├── config_jetson2.json
├── config_jetson2_web.json      # 웹 전용 설정 (새로 추가)
│
├── gst_camera.py                # 그대로 사용
├── frying_segmenter.py          # 그대로 사용
├── lift_event_tracker.py        # 그대로 사용
├── gpu_postprocess.py           # 그대로 사용
│
├── web/                         # 웹 모듈 (새로 생성)
│   ├── __init__.py
│   ├── app.py                  # FastAPI app
│   ├── mjpeg.py                # MJPEG 스트리머
│   ├── templates/
│   │   └── dashboard.html      # 2x2 그리드
│   └── static/
│       └── style.css           # 스타일
│
└── systemd/
    └── jetson2-web.service     # 새 서비스
```

---

## 🔧 JETSON2_web.py 구조 (상세)

### 1. imports & config

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson2 Web Refactored - Headless + FastAPI Dashboard
CPU 최적화 버전 (tkinter 제거)
"""

import threading
import time
import queue
import signal
import sys
import json
from collections import deque
from datetime import datetime

# 기존 모듈 재사용
from gst_camera import GstCamera
from frying_segmenter import FoodSegmenter
from lift_event_tracker import LiftEventTracker
sys.path.insert(0, '..')
from src.communication.mqtt_client import MQTTClient

# 웹 서버
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn
import cv2
import numpy as np

# 설정 로드
def load_config(path='config_jetson2_web.json'):
    with open(path, 'r') as f:
        return json.load(f)

config = load_config()
```

---

### 2. CameraWorker (간소화)

```python
class CameraWorker(threading.Thread):
    """카메라 캡처 스레드 (GUI 로직 제거)"""

    def __init__(self, cam_id, cam_index, config):
        super().__init__(daemon=True)
        self.cam_id = cam_id
        self.cam_index = cam_index
        self.config = config

        # GstCamera (그대로)
        self.camera = GstCamera(
            cam_index,
            width=config['camera_width'],
            height=config['camera_height'],
            fps=config['camera_fps']
        )

        # 프레임 큐 (최신 1장만!)
        self.frame_queue = deque(maxlen=1)  # 자동 드롭

        # 웹 프리뷰용 (리사이즈 + JPEG)
        self.web_frame = None
        self.web_frame_lock = threading.Lock()

        # 통계
        self.stats = {
            'fps': 0,
            'frame_count': 0,
            'last_frame_ts': 0,
            'drop_count': 0,
        }

        self.running = False

    def run(self):
        """캡처 루프 (GUI 업데이트 제거!)"""
        self.running = True

        if not self.camera.start():
            print(f"[CAM{self.cam_id}] Failed to start")
            return

        fps_calc_time = time.time()
        fps_frame_count = 0

        while self.running:
            frame = self.camera.read()
            if frame is None:
                time.sleep(0.01)
                continue

            # 1. AI 추론용 큐에 넣기 (최신 1장만 유지)
            if len(self.frame_queue) == 1:  # 가득 참
                self.stats['drop_count'] += 1
            self.frame_queue.append(frame.copy())

            # 2. 웹 프리뷰용 생성 (비동기, 주기적)
            self._update_web_frame(frame)

            # 3. 통계 업데이트
            fps_frame_count += 1
            now = time.time()
            if now - fps_calc_time >= 1.0:
                self.stats['fps'] = fps_frame_count
                fps_frame_count = 0
                fps_calc_time = now

            self.stats['frame_count'] += 1
            self.stats['last_frame_ts'] = now

        self.camera.stop()

    def _update_web_frame(self, frame):
        """웹 프리뷰 프레임 생성 (리사이즈 + JPEG)"""
        # FPS 제한 (web_preview_fps)
        now = time.time()
        if hasattr(self, '_last_web_update'):
            interval = 1.0 / self.config.get('web_preview_fps', 5)
            if now - self._last_web_update < interval:
                return

        # 리사이즈
        h, w = frame.shape[:2]
        target_w = self.config.get('web_preview_width', 640)
        target_h = int(h * target_w / w)
        small = cv2.resize(frame, (target_w, target_h))

        # JPEG 인코딩
        ret, jpg = cv2.imencode('.jpg', small, [
            cv2.IMWRITE_JPEG_QUALITY,
            self.config.get('web_preview_quality', 70)
        ])

        if ret:
            with self.web_frame_lock:
                self.web_frame = jpg.tobytes()

        self._last_web_update = now

    def get_frame_for_ai(self):
        """AI 추론용 프레임 가져오기 (non-blocking)"""
        try:
            return self.frame_queue.popleft()
        except IndexError:
            return None

    def get_web_frame(self):
        """웹 스트리밍용 JPEG 가져오기"""
        with self.web_frame_lock:
            return self.web_frame

    def stop(self):
        self.running = False
```

**핵심 차이:**
- ✅ tkinter PhotoImage 변환 **제거**
- ✅ GUI 업데이트 로직 **제거**
- ✅ `deque(maxlen=1)`로 자동 드롭 (큐 쌓임 방지)
- ✅ 웹용 JPEG는 별도 관리 (FPS 제한)

---

### 3. AI Worker (간소화)

```python
class FryingAIWorker(threading.Thread):
    """튀김 AI 추론 스레드"""

    def __init__(self, pot_id, camera_worker, config):
        super().__init__(daemon=True)
        self.pot_id = pot_id
        self.camera = camera_worker
        self.config = config

        # AI 모델
        self.segmenter = FoodSegmenter(
            seg_model=config['frying_seg_model'],
            # ... 설정
        )
        self.tracker = LiftEventTracker(config)

        # 결과
        self.latest_result = {
            'pot_id': pot_id,
            'status': 'IDLE',
            'lift_count': 0,
            'last_update': 0,
        }
        self.result_lock = threading.Lock()

        self.running = False

    def run(self):
        """추론 루프 (GUI 없음!)"""
        self.running = True

        infer_interval = 1.0 / self.config.get('frying_infer_fps', 5)
        last_infer = 0

        while self.running:
            # FPS 제한
            now = time.time()
            if now - last_infer < infer_interval:
                time.sleep(0.01)
                continue

            # 프레임 가져오기
            frame = self.camera.get_frame_for_ai()
            if frame is None:
                time.sleep(0.01)
                continue

            # AI 추론
            result = self.segmenter.infer(frame)
            tracker_result = self.tracker.update(result)

            # 결과 저장
            with self.result_lock:
                self.latest_result = {
                    'pot_id': self.pot_id,
                    'status': tracker_result.get('status', 'UNKNOWN'),
                    'lift_count': tracker_result.get('lift_count', 0),
                    'area': result.get('area', 0),
                    'last_update': now,
                }

            last_infer = now

    def get_result(self):
        """최신 결과 가져오기"""
        with self.result_lock:
            return self.latest_result.copy()

    def stop(self):
        self.running = False
```

**핵심:**
- ✅ GUI 업데이트 제거
- ✅ 결과만 dict로 저장
- ✅ MQTT는 메인에서 처리

---

### 4. FastAPI 웹서버

```python
class WebDashboard:
    """FastAPI 웹 대시보드"""

    def __init__(self, cameras, ai_workers, mqtt_client, config):
        self.cameras = cameras  # dict: {0: CameraWorker, ...}
        self.ai_workers = ai_workers  # dict: {0: FryingAI, 1: FryingAI, ...}
        self.mqtt = mqtt_client
        self.config = config

        self.app = FastAPI(title="Jetson2 Dashboard")
        self._setup_routes()

    def _setup_routes(self):
        """라우트 설정"""

        @self.app.get("/")
        async def index():
            """2x2 대시보드 HTML"""
            return FileResponse("web/templates/dashboard.html")

        @self.app.get("/mjpeg/cam{cam_id}")
        async def mjpeg_stream(cam_id: int):
            """MJPEG 스트림"""
            return StreamingResponse(
                self._generate_mjpeg(cam_id),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )

        @self.app.get("/api/status")
        async def status():
            """시스템 상태 JSON"""
            return {
                'timestamp': time.time(),
                'cameras': {
                    f'cam{i}': cam.stats for i, cam in self.cameras.items()
                },
                'ai': {
                    f'pot{i}': ai.get_result() for i, ai in self.ai_workers.items()
                },
                'mqtt': {
                    'connected': self.mqtt.is_connected if self.mqtt else False,
                }
            }

        @self.app.get("/api/config")
        async def get_config():
            """설정 조회"""
            return self.config

    async def _generate_mjpeg(self, cam_id):
        """MJPEG 스트림 생성기"""
        camera = self.cameras.get(cam_id)
        if not camera:
            yield b"--frame\r\nContent-Type: text/plain\r\n\r\nCamera not found\r\n"
            return

        while True:
            jpg = camera.get_web_frame()
            if jpg:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
            await asyncio.sleep(1.0 / self.config.get('web_preview_fps', 5))

    def run(self, host='0.0.0.0', port=8000):
        """서버 시작 (별도 스레드)"""
        def _run():
            uvicorn.run(self.app, host=host, port=port, log_level='warning')

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread
```

---

### 5. 메인 클래스 (간소화)

```python
class Jetson2Web:
    """메인 컨트롤러 (GUI 없음!)"""

    def __init__(self, config):
        self.config = config
        self.running = False

        # 카메라 워커 x4
        self.cameras = {}
        for i in range(4):
            self.cameras[i] = CameraWorker(i, i, config)

        # AI 워커 x2 (POT 0, 1)
        self.ai_workers = {}
        if config.get('frying_enabled'):
            self.ai_workers[0] = FryingAIWorker(0, self.cameras[0], config)
            self.ai_workers[1] = FryingAIWorker(1, self.cameras[1], config)

        # MQTT
        self.mqtt = None
        if config.get('mqtt_enabled'):
            self.mqtt = MQTTClient(
                broker=config['mqtt_broker'],
                port=config['mqtt_port'],
                client_id=config['mqtt_client_id']
            )

        # 웹 대시보드
        self.web = WebDashboard(self.cameras, self.ai_workers, self.mqtt, config)

    def start(self):
        """시스템 시작"""
        print("=" * 60)
        print("🚀 Jetson2 Web (Headless) Starting...")
        print("=" * 60)

        # 1. 카메라 시작
        for cam_id, cam in self.cameras.items():
            cam.start()
            time.sleep(0.5)  # 순차 시작

        # 2. AI 시작
        for pot_id, ai in self.ai_workers.items():
            ai.start()

        # 3. MQTT 시작
        if self.mqtt:
            self.mqtt.connect()

        # 4. 웹서버 시작
        tailscale_ip = self._get_tailscale_ip()
        host = tailscale_ip if tailscale_ip else '0.0.0.0'
        port = self.config.get('web_port', 8000)

        print(f"🌐 Web Dashboard: http://{host}:{port}/")
        self.web.run(host, port)

        # 5. 메인 루프
        self.running = True
        self._main_loop()

    def _main_loop(self):
        """메인 루프 (간소화 - GUI 없음!)"""
        last_mqtt_publish = 0
        mqtt_interval = self.config.get('mqtt_publish_interval', 2)

        try:
            while self.running:
                now = time.time()

                # MQTT 상태 발행
                if self.mqtt and now - last_mqtt_publish >= mqtt_interval:
                    self._publish_mqtt_status()
                    last_mqtt_publish = now

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user")
        finally:
            self.stop()

    def _publish_mqtt_status(self):
        """MQTT 상태 발행"""
        # AI 결과 수집
        status = {}
        for pot_id, ai in self.ai_workers.items():
            result = ai.get_result()
            status[f'pot{pot_id}'] = result

        # 발행
        if self.mqtt:
            self.mqtt.publish('jetson2/status', json.dumps(status))

    def _get_tailscale_ip(self):
        """Tailscale IP 가져오기"""
        import subprocess
        try:
            result = subprocess.run(['tailscale', 'ip', '-4'],
                capture_output=True, text=True, timeout=2)
            return result.stdout.strip()
        except:
            return None

    def stop(self):
        """시스템 종료"""
        print("\n🛑 Shutting down...")
        self.running = False

        # 모든 워커 종료
        for cam in self.cameras.values():
            cam.stop()
        for ai in self.ai_workers.values():
            ai.stop()

        if self.mqtt:
            self.mqtt.disconnect()

        print("✅ Shutdown complete")


def main():
    """진입점"""
    config = load_config()

    # Signal handler
    app = Jetson2Web(config)

    def signal_handler(sig, frame):
        print("\n⚠️  Signal received")
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 시작
    app.start()


if __name__ == '__main__':
    main()
```

---

## 📝 config_jetson2_web.json (새 설정)

```json
{
  "// 기본": "",
  "device_id": "jetson2",
  "device_name": "Jetson2_Web",

  "// 카메라": "",
  "camera_width": 1920,
  "camera_height": 1536,
  "camera_fps": 30,

  "// AI": "",
  "frying_enabled": true,
  "frying_seg_model": "frying_seg_v3.pt",
  "frying_infer_fps": 5,
  "observe_enabled": true,
  "observe_seg_model": "observe_add/best_io.pt",

  "// 웹 대시보드": "",
  "web_enabled": true,
  "web_port": 8000,
  "web_preview_fps": 5,
  "web_preview_quality": 70,
  "web_preview_width": 640,

  "// MQTT": "",
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.0.100",
  "mqtt_port": 1883,
  "mqtt_client_id": "jetson2_web",
  "mqtt_publish_interval": 2,

  "// 최적화": "",
  "headless_mode": true,
  "debug_print_enabled": false
}
```

---

## 🌐 웹 대시보드 HTML

**web/templates/dashboard.html:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Jetson2 Dashboard</title>
    <meta charset="utf-8">
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="header">
        <h1>🎥 Jetson2 Headless Dashboard</h1>
        <div id="status-bar">Loading...</div>
    </div>

    <div class="grid">
        <!-- Camera 0: Frying Left -->
        <div class="camera-box">
            <div class="cam-header">Frying Left (POT0)</div>
            <img src="/mjpeg/cam0" alt="Frying Left">
            <div class="cam-status" id="status-0">-</div>
        </div>

        <!-- Camera 1: Frying Right -->
        <div class="camera-box">
            <div class="cam-header">Frying Right (POT1)</div>
            <img src="/mjpeg/cam1" alt="Frying Right">
            <div class="cam-status" id="status-1">-</div>
        </div>

        <!-- Camera 2: Observe Left -->
        <div class="camera-box">
            <div class="cam-header">Bucket Left</div>
            <img src="/mjpeg/cam2" alt="Bucket Left">
            <div class="cam-status" id="status-2">-</div>
        </div>

        <!-- Camera 3: Observe Right -->
        <div class="camera-box">
            <div class="cam-header">Bucket Right</div>
            <img src="/mjpeg/cam3" alt="Bucket Right">
            <div class="cam-status" id="status-3">-</div>
        </div>
    </div>

    <script>
        // 상태 업데이트 (2초마다)
        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                // 카메라 상태
                for (let i = 0; i < 4; i++) {
                    const cam = data.cameras[`cam${i}`];
                    const elem = document.getElementById(`status-${i}`);
                    elem.textContent = `FPS: ${cam.fps} | Frames: ${cam.frame_count} | Drops: ${cam.drop_count}`;
                }

                // AI 상태
                if (data.ai.pot0) {
                    document.getElementById('status-0').textContent +=
                        ` | Lift: ${data.ai.pot0.lift_count}`;
                }
                if (data.ai.pot1) {
                    document.getElementById('status-1').textContent +=
                        ` | Lift: ${data.ai.pot1.lift_count}`;
                }

                // 헤더 상태
                document.getElementById('status-bar').textContent =
                    `MQTT: ${data.mqtt.connected ? 'Connected' : 'Disconnected'} | ` +
                    `Timestamp: ${new Date(data.timestamp * 1000).toLocaleTimeString()}`;

            } catch (e) {
                console.error('Status update failed:', e);
            }
        }

        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
```

---

## 🎨 CSS

**web/static/style.css:**
```css
body {
    margin: 0;
    padding: 0;
    background: #1a1a1a;
    color: white;
    font-family: 'Segoe UI', sans-serif;
}

.header {
    background: #2c3e50;
    padding: 20px;
    text-align: center;
}

.header h1 {
    margin: 0 0 10px 0;
}

#status-bar {
    color: #7f8c8d;
    font-size: 14px;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    padding: 15px;
    height: calc(100vh - 120px);
}

.camera-box {
    border: 2px solid #34495e;
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: #2c3e50;
}

.cam-header {
    background: #34495e;
    padding: 12px;
    font-weight: bold;
    font-size: 16px;
}

.camera-box img {
    width: 100%;
    height: auto;
    flex: 1;
    object-fit: contain;
    background: #000;
}

.cam-status {
    background: #1a1a1a;
    padding: 10px;
    font-size: 12px;
    color: #27ae60;
    font-family: monospace;
}
```

---

## 🚀 실행 방법

### 개발 모드

```bash
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_web.py
```

### systemd 서비스

**systemd/jetson2-web.service:**
```ini
[Unit]
Description=Jetson2 Web Dashboard (Headless)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=hr_dku_001
WorkingDirectory=/home/hr_dku_001/jetson-food-ai/jetson2_frying_ai
ExecStart=/usr/bin/python3 JETSON2_web.py
Restart=always
RestartSec=10

# 환경변수
Environment="PYTHONUNBUFFERED=1"

# 로그
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**설치:**
```bash
sudo cp systemd/jetson2-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jetson2-web
sudo systemctl start jetson2-web

# 로그 확인
journalctl -u jetson2-web -f
```

---

## 📊 성능 비교

| 항목 | 기존 (GUI) | 새 (Headless) | 절감 |
|------|-----------|--------------|------|
| **총 CPU** | ~80-100% | ~55-70% | **25-30%** |
| **카메라** | 15% | 15% | 0% |
| **AI 추론** | 40% | 40% | 0% |
| **GUI** | 25% | **0%** | **-25%** |
| **웹서버** | 0% | 3% | +3% |
| **MQTT** | 3% | 3% | 0% |
| **기타** | 10% | 7% | -3% |

**결과:** CPU **25-30% 절감!**

---

## 🔄 마이그레이션 전략

### Phase 1: 개발 & 테스트 (병행)
```bash
# 기존 (계속 실행)
sudo systemctl start jetson2-monitor

# 새 버전 (테스트)
python3 JETSON2_web.py
```

### Phase 2: 비교 테스트
- CPU 사용량 모니터링
- AI 추론 FPS 비교
- MQTT 안정성 확인
- 웹 대시보드 동작 확인

### Phase 3: 전환 (준비되면)
```bash
# 기존 중지
sudo systemctl stop jetson2-monitor
sudo systemctl disable jetson2-monitor

# 새 버전 시작
sudo systemctl enable jetson2-web
sudo systemctl start jetson2-web
```

---

## ✅ 체크리스트

### 제거된 것 (CPU 절감)
- [x] tkinter GUI 전체
- [x] PhotoImage 변환
- [x] Canvas/Label 업데이트
- [x] root.update() 호출
- [x] GUI 관련 모든 import

### 추가된 것 (기능 유지)
- [x] FastAPI 웹서버
- [x] MJPEG 스트리밍
- [x] 2x2 대시보드 HTML
- [x] 상태 API
- [x] Tailscale 바인딩

### 유지된 것 (재사용)
- [x] GstCamera
- [x] FoodSegmenter
- [x] LiftEventTracker
- [x] MQTTClient
- [x] 전체 AI 파이프라인

---

## 🎯 구현 우선순위 (Codex용)

### Day 1: 핵심 구조
1. JETSON2_web.py 기본 구조
2. CameraWorker (GUI 제거 버전)
3. FryingAIWorker (간소화)
4. 메인 클래스

### Day 2: 웹 대시보드
1. FastAPI app
2. MJPEG 스트리밍
3. 상태 API
4. HTML/CSS

### Day 3: 테스트 & 최적화
1. 실제 Jetson에서 테스트
2. CPU 사용량 측정
3. 성능 튜닝
4. 문서 작성

---

## 📚 의존성

**requirements-web.txt:**
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
aiofiles==23.2.1
```

---

**작성일:** 2026-02-03
**목적:** JETSON2_web.py 리팩토링 플랜 (Headless + FastAPI)
**목표:** CPU 25-30% 절감 (tkinter 제거)
**방식:** 기존 건드리지 않고 새 파일로 작성
