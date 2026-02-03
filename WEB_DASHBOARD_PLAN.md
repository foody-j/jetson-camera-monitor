# 🌐 Jetson2 Web Dashboard 구현 플랜

## 📋 목표

Jetson Orin Nano에서 headless 웹 대시보드 추가 (Tailscale only, 기존 파이프라인 유지)

---

## 🏗️ 아키텍처 결정

### ✅ 추천: Sidecar 방식 (별도 프로세스)

```
┌─────────────────────────────────────────────┐
│  JETSON2_INTEGRATED.py (기존, 메인 프로세스)  │
│  ├─ GstCamera x4 (GMSL)                    │
│  ├─ AI 추론 (YOLO)                         │
│  ├─ MQTT 전송                              │
│  └─ tkinter GUI (optional)                │
└─────────────────────────────────────────────┘
              ↓ (카메라 프레임 공유)
┌─────────────────────────────────────────────┐
│  dashboard/ (새 모듈, 별도 프로세스)          │
│  ├─ FastAPI 웹서버                         │
│  ├─ MJPEG 스트리밍                         │
│  └─ 상태 API                               │
└─────────────────────────────────────────────┘
```

**방식 A: 공유 메모리 (추천 ⭐)**
- JETSON2_INTEGRATED.py가 `/dev/shm/jetson2_cam{0-3}.jpg` 저장
- dashboard가 주기적으로 읽어서 스트리밍
- 장점: 완전 독립, 한 쪽 죽어도 영향 없음
- 단점: 디스크 I/O (근데 shm이라 괜찮음)

**방식 B: ZeroMQ/Redis**
- JETSON2_INTEGRATED.py가 프레임 publish
- dashboard가 subscribe
- 장점: 실시간성 좋음
- 단점: 의존성 추가, 메모리 오버헤드

---

## 📁 디렉토리 구조 (추천)

```
jetson2_frying_ai/
├── JETSON2_INTEGRATED.py       # 기존 (수정 최소화)
├── JETSON2_web.py               # 새 진입점 (선택사항)
├── config_jetson2.json
├── gst_camera.py
│
├── dashboard/                   # 새 모듈
│   ├── __init__.py
│   ├── __main__.py             # python -m dashboard로 실행
│   ├── server.py               # FastAPI app
│   ├── mjpeg.py                # MJPEG 스트리밍 로직
│   ├── status.py               # 상태 수집/API
│   └── templates/
│       └── index.html          # 2x2 대시보드 페이지
│
├── systemd/
│   ├── jetson2-dashboard.service
│   └── jetson2-integrated.service (기존 업데이트)
│
└── docs/
    └── WEB_DASHBOARD.md        # 사용법
```

---

## 🔧 구현 세부사항

### 1. 프레임 공유 메커니즘

#### Option A: 공유 메모리 JPEG (추천)

**JETSON2_INTEGRATED.py 수정 (최소):**
```python
# config에 추가
"web_dashboard_enabled": true,
"web_preview_fps": 5,
"web_preview_quality": 70,
"web_preview_width": 640,

# init에 추가
if config.get('web_dashboard_enabled'):
    self.web_frame_queue = {
        'cam0': {'path': '/dev/shm/jetson2_cam0.jpg', 'last_write': 0},
        'cam1': {'path': '/dev/shm/jetson2_cam1.jpg', 'last_write': 0},
        'cam2': {'path': '/dev/shm/jetson2_cam2.jpg', 'last_write': 0},
        'cam3': {'path': '/dev/shm/jetson2_cam3.jpg', 'last_write': 0},
    }
    self.web_fps_interval = 1.0 / config.get('web_preview_fps', 5)

# capture worker에 추가 (각 카메라별)
def _write_web_preview(self, cam_id, frame):
    now = time.time()
    meta = self.web_frame_queue[f'cam{cam_id}']
    if now - meta['last_write'] < self.web_fps_interval:
        return  # FPS 제한

    # 640폭으로 리사이즈
    h, w = frame.shape[:2]
    target_w = self.config.get('web_preview_width', 640)
    target_h = int(h * target_w / w)
    small = cv2.resize(frame, (target_w, target_h))

    # JPEG 인코딩
    ret, jpg = cv2.imencode('.jpg', small,
        [cv2.IMWRITE_JPEG_QUALITY, self.config.get('web_preview_quality', 70)])

    # atomic write (임시 파일 → rename)
    tmp_path = meta['path'] + '.tmp'
    with open(tmp_path, 'wb') as f:
        f.write(jpg.tobytes())
    os.rename(tmp_path, meta['path'])

    meta['last_write'] = now
```

**dashboard/mjpeg.py:**
```python
import asyncio
import os
from fastapi import Response
from fastapi.responses import StreamingResponse

class MJPEGStreamer:
    def __init__(self, cam_paths):
        self.cam_paths = cam_paths  # {0: '/dev/shm/jetson2_cam0.jpg', ...}

    async def stream_mjpeg(self, cam_id: int, fps: int = 5):
        """MJPEG 스트림 생성기"""
        interval = 1.0 / fps
        jpeg_path = self.cam_paths.get(cam_id)

        if not jpeg_path or not os.path.exists(jpeg_path):
            yield self._error_frame(f"Camera {cam_id} not available")
            return

        async def generate():
            last_mtime = 0
            cached_frame = None

            while True:
                try:
                    # mtime 체크로 변경 감지
                    stat = os.stat(jpeg_path)
                    if stat.st_mtime > last_mtime:
                        with open(jpeg_path, 'rb') as f:
                            cached_frame = f.read()
                        last_mtime = stat.st_mtime

                    if cached_frame:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' +
                               cached_frame + b'\r\n')

                    await asyncio.sleep(interval)

                except Exception as e:
                    yield self._error_frame(str(e))
                    await asyncio.sleep(1)

        return StreamingResponse(
            generate(),
            media_type='multipart/x-mixed-replace; boundary=frame'
        )

    def _error_frame(self, msg):
        # 에러 이미지 생성 (PIL 또는 cv2)
        ...
```

---

### 2. FastAPI 서버 구조

**dashboard/server.py:**
```python
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from .mjpeg import MJPEGStreamer
from .status import StatusCollector
import os

app = FastAPI(title="Jetson2 Dashboard", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory="dashboard/templates")

# 카메라 경로
CAM_PATHS = {
    0: '/dev/shm/jetson2_cam0.jpg',  # frying_left
    1: '/dev/shm/jetson2_cam1.jpg',  # frying_right
    2: '/dev/shm/jetson2_cam2.jpg',  # observe_left
    3: '/dev/shm/jetson2_cam3.jpg',  # observe_right
}

streamer = MJPEGStreamer(CAM_PATHS)
status = StatusCollector(CAM_PATHS)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """2x2 대시보드 페이지"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "cameras": [
            {"id": 0, "name": "Frying Left"},
            {"id": 1, "name": "Frying Right"},
            {"id": 2, "name": "Observe Left"},
            {"id": 3, "name": "Observe Right"},
        ]
    })

@app.get("/mjpeg/cam{cam_id}")
async def mjpeg_stream(
    cam_id: int,
    fps: int = Query(default=5, ge=1, le=30),
    quality: int = Query(default=70, ge=10, le=100)
):
    """MJPEG 스트림 (query로 fps 조절 가능)"""
    return await streamer.stream_mjpeg(cam_id, fps)

@app.get("/api/status")
async def get_status():
    """시스템 상태 JSON"""
    return status.collect()

@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "ok"}
```

**dashboard/status.py:**
```python
import os
import time
import json

class StatusCollector:
    def __init__(self, cam_paths):
        self.cam_paths = cam_paths
        self.status_file = '/dev/shm/jetson2_status.json'  # JETSON2가 주기적 업데이트

    def collect(self):
        """상태 수집"""
        cameras = {}
        for cam_id, path in self.cam_paths.items():
            if os.path.exists(path):
                stat = os.stat(path)
                age = time.time() - stat.st_mtime
                cameras[f'cam{cam_id}'] = {
                    'available': True,
                    'last_frame_age_sec': round(age, 2),
                    'file_size_kb': round(stat.st_size / 1024, 1),
                }
            else:
                cameras[f'cam{cam_id}'] = {'available': False}

        # JETSON2가 쓴 상태 파일 읽기 (옵션)
        jetson_status = {}
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file) as f:
                    jetson_status = json.load(f)
            except:
                pass

        return {
            'timestamp': time.time(),
            'cameras': cameras,
            'jetson2': jetson_status,  # inference fps, mqtt status 등
        }
```

---

### 3. HTML 템플릿 (2x2 그리드)

**dashboard/templates/index.html:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Jetson2 Dashboard</title>
    <style>
        body { margin: 0; background: #1a1a1a; color: white; font-family: sans-serif; }
        .header { background: #2c3e50; padding: 15px; text-align: center; }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 10px;
            height: calc(100vh - 80px);
        }
        .camera {
            border: 2px solid #34495e;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .camera-title {
            background: #34495e;
            padding: 10px;
            font-weight: bold;
        }
        .camera-view {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #000;
        }
        .camera-view img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        .status {
            background: #2c3e50;
            padding: 5px 10px;
            font-size: 12px;
            color: #7f8c8d;
        }
        .status.connected { color: #27ae60; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎥 Jetson2 Camera Dashboard</h1>
        <div id="system-status"></div>
    </div>

    <div class="grid">
        {% for cam in cameras %}
        <div class="camera">
            <div class="camera-title">{{ cam.name }} (CAM{{ cam.id }})</div>
            <div class="camera-view">
                <img src="/mjpeg/cam{{ cam.id }}?fps=5" alt="{{ cam.name }}">
            </div>
            <div class="status" id="status-cam{{ cam.id }}">Loading...</div>
        </div>
        {% endfor %}
    </div>

    <script>
        // 상태 업데이트 (2초마다)
        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                for (let i = 0; i < 4; i++) {
                    const cam = data.cameras[`cam${i}`];
                    const elem = document.getElementById(`status-cam${i}`);
                    if (cam.available) {
                        elem.className = 'status connected';
                        elem.textContent = `✓ Active (${cam.last_frame_age_sec}s ago, ${cam.file_size_kb}KB)`;
                    } else {
                        elem.className = 'status';
                        elem.textContent = '✗ Unavailable';
                    }
                }

                // 시스템 상태
                const sysStatus = document.getElementById('system-status');
                if (data.jetson2) {
                    sysStatus.textContent = `Inference FPS: ${data.jetson2.infer_fps || 'N/A'} | MQTT: ${data.jetson2.mqtt_connected ? 'Connected' : 'Disconnected'}`;
                }
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

### 4. 실행 진입점

**dashboard/__main__.py:**
```python
"""
python -m dashboard로 실행
"""
import uvicorn
import os
import sys

# Tailscale IP 가져오기
def get_tailscale_ip():
    """tailscale0 인터페이스 IP 반환"""
    import subprocess
    try:
        result = subprocess.run(
            ['ip', 'addr', 'show', 'tailscale0'],
            capture_output=True, text=True, timeout=2
        )
        for line in result.stdout.split('\n'):
            if 'inet ' in line:
                ip = line.strip().split()[1].split('/')[0]
                return ip
    except:
        pass
    return None

if __name__ == "__main__":
    # Tailscale IP 바인딩 (보안)
    tailscale_ip = get_tailscale_ip()

    if tailscale_ip:
        host = tailscale_ip
        print(f"✅ Binding to Tailscale IP: {tailscale_ip}")
    else:
        host = "0.0.0.0"
        print("⚠️  Tailscale IP not found, binding to 0.0.0.0")
        print("⚠️  WARNING: Accessible from all interfaces!")

    port = int(os.getenv('DASHBOARD_PORT', '8000'))

    print(f"🚀 Starting dashboard on http://{host}:{port}")
    print(f"📸 Access: http://{tailscale_ip or 'localhost'}:{port}/")

    uvicorn.run(
        "dashboard.server:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,  # CPU 절약
    )
```

---

### 5. systemd 서비스

**systemd/jetson2-dashboard.service:**
```ini
[Unit]
Description=Jetson2 Web Dashboard
After=network-online.target jetson2-integrated.service
Wants=network-online.target

[Service]
Type=simple
User=hr_dku_001
WorkingDirectory=/home/hr_dku_001/jetson-food-ai/jetson2_frying_ai
Environment="DASHBOARD_PORT=8000"
ExecStart=/usr/bin/python3 -m dashboard
Restart=always
RestartSec=10

# 로그
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**설치:**
```bash
sudo cp systemd/jetson2-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jetson2-dashboard
sudo systemctl start jetson2-dashboard
```

---

### 6. Tailscale 접근 제한 (보안)

**방법 A: uvicorn host 바인딩 (위에 구현됨)**
```python
# Tailscale IP로만 바인딩
host = get_tailscale_ip()  # 예: 100.x.x.x
```

**방법 B: ufw 방화벽 (추가 보안층)**
```bash
# 8000 포트는 tailscale0에서만 허용
sudo ufw allow in on tailscale0 to any port 8000
sudo ufw deny 8000

# 확인
sudo ufw status
```

**docs/WEB_DASHBOARD.md에 작성:**
```markdown
## 🔒 보안 설정

### Tailscale 전용 접근

대시보드는 Tailscale VPN을 통해서만 접근 가능합니다.

1. **Tailscale 설치 확인**
   ```bash
   tailscale status
   ```

2. **방화벽 설정 (선택)**
   ```bash
   sudo ufw allow in on tailscale0 to any port 8000
   sudo ufw deny 8000
   ```

3. **접속**
   ```
   http://100.x.x.x:8000/
   ```
   (Tailscale IP는 `tailscale ip -4`로 확인)

### ⚠️ 인터넷 노출 방지

- uvicorn이 Tailscale IP로만 바인딩되므로 외부 접근 불가
- 추가로 ufw 설정 시 이중 보호
```

---

## 📊 성능 최적화

### CPU 부담 최소화

1. **프레임 리사이즈**: 640폭 (원본 1920 → 1/3 크기)
2. **JPEG 품질**: 70 (기본), 50-80 조절 가능
3. **FPS 제한**: 5fps (기본), 1-10 조절 가능
4. **공유메모리 사용**: 디스크 I/O 최소화
5. **mtime 기반 읽기**: 변경 시에만 파일 읽기
6. **큐 없음**: 최신 1프레임만 유지 (메모리 절약)

**예상 CPU 사용량:**
- 프레임 리사이즈 + JPEG 인코딩: ~2% (4대 카메라)
- FastAPI 서버: ~1%
- 총: ~3% 추가 (접속 시)

---

## 🚀 실행 순서

### 개발 모드

```bash
# 터미널 1: 메인 시스템
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py

# 터미널 2: 대시보드
cd ~/jetson-food-ai/jetson2_frying_ai
python3 -m dashboard
```

### 프로덕션 (systemd)

```bash
sudo systemctl start jetson2-integrated
sudo systemctl start jetson2-dashboard

# 로그 확인
journalctl -u jetson2-dashboard -f
```

---

## 📝 기존 코드 수정 사항 (최소)

### JETSON2_INTEGRATED.py

**1. config 추가 (config_jetson2.json):**
```json
{
  "web_dashboard_enabled": true,
  "web_preview_fps": 5,
  "web_preview_quality": 70,
  "web_preview_width": 640
}
```

**2. __init__에 추가:**
```python
# Web dashboard 공유메모리 초기화
if config.get('web_dashboard_enabled'):
    self.init_web_preview()
```

**3. 각 카메라 capture worker에 추가:**
```python
# 프레임 캡처 후
if self.web_dashboard_enabled:
    self._write_web_preview(cam_id, frame)
```

**4. 상태 파일 쓰기 (선택, 주기적):**
```python
def write_status_file(self):
    """대시보드용 상태 JSON 쓰기"""
    status = {
        'timestamp': time.time(),
        'infer_fps': self.current_fps,
        'mqtt_connected': self.mqtt_client.is_connected if self.mqtt_client else False,
        # ... 추가 정보
    }
    with open('/dev/shm/jetson2_status.json', 'w') as f:
        json.dump(status, f)
```

**총 수정량: ~50줄 추가 (기존 로직 변경 없음)**

---

## 🎯 구현 우선순위

### Phase 1: 기본 MJPEG 스트리밍 (1일)
- [ ] dashboard/ 모듈 구조 생성
- [ ] JETSON2에 공유메모리 JPEG 쓰기 추가
- [ ] FastAPI 서버 + MJPEG endpoint
- [ ] 간단한 HTML (4개 img 태그)

### Phase 2: 상태 API + 디자인 (0.5일)
- [ ] /api/status 구현
- [ ] HTML 2x2 그리드 디자인
- [ ] JS로 상태 실시간 업데이트

### Phase 3: 보안 + 배포 (0.5일)
- [ ] Tailscale IP 바인딩
- [ ] systemd 서비스 파일
- [ ] ufw 규칙 문서화
- [ ] WEB_DASHBOARD.md 작성

---

## 🔄 대안: JETSON2_web.py (통합 버전)

별도 프로세스가 아닌, JETSON2_INTEGRATED.py에 FastAPI를 thread로 띄우는 방식도 가능:

**장점:**
- 프레임 공유 불필요 (직접 접근)
- 상태 정보 실시간

**단점:**
- tkinter + FastAPI 충돌 가능성
- 한 쪽 크래시 시 전체 다운
- 코드 복잡도 증가

**추천하지 않음.** Sidecar 방식이 더 안전합니다.

---

## 📦 의존성

**requirements-dashboard.txt:**
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
jinja2==3.1.3
```

**설치:**
```bash
pip3 install -r requirements-dashboard.txt
```

---

## ✅ 최종 체크리스트

- [x] 기존 파이프라인 무건드림 (sidecar)
- [x] FastAPI + MJPEG
- [x] 2x2 그리드 대시보드
- [x] 상태 API (/api/status)
- [x] FPS/Quality 조절 가능
- [x] 최신 1프레임 유지 (공유메모리)
- [x] Tailscale 전용 접근
- [x] systemd 서비스
- [x] 문서화

---

**작성일:** 2026-02-03
**목적:** Jetson2 웹 대시보드 아키텍처 플랜
**방식:** Sidecar (별도 프로세스) + 공유메모리
