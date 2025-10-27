#!/usr/bin/env python3
"""
실시간 튀김 모니터링 웹 뷰어
- Flask 기반 MJPEG 스트리밍
- 세그멘테이션 오버레이
- 실시간 특징 표시
- 세션 제어 (시작/완료/종료)
"""

import os
import sys
import cv2
import numpy as np
import json
import time
from flask import Flask, render_template, Response, jsonify, request
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading

# 상위 디렉토리 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frying_ai.frying_data_collector import FryingDataCollector
from frying_ai.food_segmentation import FoodSegmenter

# Flask 앱
app = Flask(__name__)

# 전역 상태
class MonitorState:
    def __init__(self):
        self.collector: Optional[FryingDataCollector] = None
        self.segmenter: Optional[FoodSegmenter] = None
        self.is_running = False
        self.current_frame = None
        self.current_features = {}
        self.session_active = False
        self.session_id = ""
        self.start_time = 0
        self.frame_lock = threading.Lock()

state = MonitorState()


def initialize_system():
    """시스템 초기화"""
    state.collector = FryingDataCollector(base_dir="frying_dataset", fps=1)
    state.segmenter = FoodSegmenter(mode="auto")

    if not state.collector.initialize():
        print("❌ 카메라 초기화 실패")
        return False

    print("✅ 시스템 초기화 완료")
    return True


def generate_annotated_frame():
    """주석이 달린 프레임 생성"""
    if state.collector is None:
        return None

    # 프레임 캡처
    ret, frame = state.collector.camera.read_frame()
    if not ret or frame is None:
        return None

    # 세그멘테이션 수행
    try:
        seg_result = state.segmenter.segment(frame, visualize=False)

        # 마스크 오버레이 (반투명)
        overlay = frame.copy()
        overlay[seg_result.food_mask > 0] = [0, 255, 0]  # 초록색
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

        # 특징 추출
        features = seg_result.color_features
        state.current_features = {
            'food_area': seg_result.food_area_ratio,
            'brown_ratio': features.brown_ratio,
            'golden_ratio': features.golden_ratio,
            'hue_mean': features.mean_hsv[0],
            'saturation_mean': features.saturation_mean,
            'value_mean': features.value_mean,
            'elapsed_time': time.time() - state.start_time if state.session_active else 0
        }

    except Exception as e:
        print(f"세그멘테이션 오류: {e}")
        state.current_features = {}

    # 정보 오버레이
    if state.session_active:
        elapsed = time.time() - state.start_time

        # 배경 (반투명 검은색)
        cv2.rectangle(frame, (10, 10), (400, 200), (0, 0, 0), -1)
        overlay_bg = frame.copy()
        cv2.rectangle(overlay_bg, (10, 10), (400, 200), (0, 0, 0), -1)
        frame = cv2.addWeighted(frame, 0.7, overlay_bg, 0.3, 0)

        # 텍스트 정보
        y_offset = 35
        line_height = 25

        info_lines = [
            f"Session: {state.session_id}",
            f"Time: {elapsed:.1f}s ({elapsed/60:.1f}min)",
            f"Food Area: {state.current_features.get('food_area', 0):.2%}",
            f"Brown: {state.current_features.get('brown_ratio', 0):.2%}",
            f"Golden: {state.current_features.get('golden_ratio', 0):.2%}",
            f"Hue: {state.current_features.get('hue_mean', 0):.1f}deg"
        ]

        for i, line in enumerate(info_lines):
            cv2.putText(frame, line, (20, y_offset + i * line_height),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    else:
        # 대기 중
        cv2.putText(frame, "Waiting for session...", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    with state.frame_lock:
        state.current_frame = frame.copy()

    return frame


def generate_stream():
    """MJPEG 스트림 생성"""
    while state.is_running:
        frame = generate_annotated_frame()

        if frame is None:
            time.sleep(0.1)
            continue

        # JPEG 인코딩
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        # MJPEG 프레임 전송
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        time.sleep(0.1)  # 10 FPS


# ==================== 라우트 ====================

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('viewer.html')


@app.route('/video_feed')
def video_feed():
    """비디오 스트림"""
    return Response(generate_stream(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/status')
def get_status():
    """현재 상태 반환"""
    return jsonify({
        'session_active': state.session_active,
        'session_id': state.session_id,
        'elapsed_time': time.time() - state.start_time if state.session_active else 0,
        'features': state.current_features
    })


@app.route('/api/start_session', methods=['POST'])
def start_session():
    """세션 시작"""
    if state.session_active:
        return jsonify({'success': False, 'message': '이미 세션이 진행 중입니다'})

    data = request.json
    food_type = data.get('food_type', 'unknown')
    notes = data.get('notes', '')

    session_id = state.collector.start_session(food_type, notes)
    state.session_active = True
    state.session_id = session_id
    state.start_time = time.time()

    return jsonify({
        'success': True,
        'session_id': session_id,
        'message': f'세션 시작: {session_id}'
    })


@app.route('/api/mark_completion', methods=['POST'])
def mark_completion():
    """완료 마킹"""
    if not state.session_active:
        return jsonify({'success': False, 'message': '진행 중인 세션이 없습니다'})

    data = request.json
    probe_temp = float(data.get('probe_temp', 75.0))
    notes = data.get('notes', '')

    success = state.collector.mark_completion(probe_temp, notes)

    return jsonify({
        'success': success,
        'message': f'완료 마킹: {probe_temp}°C'
    })


@app.route('/api/stop_session', methods=['POST'])
def stop_session():
    """세션 종료"""
    if not state.session_active:
        return jsonify({'success': False, 'message': '진행 중인 세션이 없습니다'})

    save_path = state.collector.stop_session()
    state.session_active = False
    state.session_id = ""

    return jsonify({
        'success': True,
        'save_path': save_path,
        'message': '세션 종료'
    })


@app.route('/api/stats')
def get_stats():
    """통계 반환"""
    stats = state.collector.get_statistics()
    return jsonify(stats)


def run_server(host='0.0.0.0', port=5000):
    """서버 실행"""
    # 템플릿 디렉토리 생성
    template_dir = Path(__file__).parent / "templates"
    template_dir.mkdir(exist_ok=True)

    # HTML 템플릿 생성
    create_html_template(template_dir)

    # 시스템 초기화
    if not initialize_system():
        print("❌ 초기화 실패")
        return

    state.is_running = True

    print("\n" + "=" * 60)
    print("🌐 튀김 모니터링 웹 뷰어 시작")
    print("=" * 60)
    print(f"URL: http://localhost:{port}")
    print(f"또는: http://<Jetson-IP>:{port}")
    print("Windows에서 접속: SSH 포트 포워딩 필요")
    print("  예: ssh -L 5000:localhost:5000 user@jetson-ip")
    print("=" * 60)
    print("\nCtrl+C로 종료\n")

    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n종료 중...")
    finally:
        state.is_running = False
        if state.collector:
            state.collector.cleanup()


def create_html_template(template_dir: Path):
    """HTML 템플릿 생성"""
    html_content = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>튀김 모니터링 시스템</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }

        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .content {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            padding: 30px;
        }

        .video-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
        }

        .video-container {
            position: relative;
            width: 100%;
            background: #000;
            border-radius: 10px;
            overflow: hidden;
        }

        .video-container img {
            width: 100%;
            height: auto;
            display: block;
        }

        .control-section {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-inactive {
            background: #dc3545;
        }

        .status-active {
            background: #28a745;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .feature-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }

        .feature-item {
            background: white;
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }

        .feature-label {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 5px;
        }

        .feature-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }

        .form-group {
            margin-bottom: 15px;
        }

        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }

        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            transition: border 0.3s;
        }

        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }

        button {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }

        .btn-start {
            background: #28a745;
            color: white;
        }

        .btn-start:hover {
            background: #218838;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3);
        }

        .btn-complete {
            background: #ffc107;
            color: #333;
        }

        .btn-complete:hover {
            background: #e0a800;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 193, 7, 0.3);
        }

        .btn-stop {
            background: #dc3545;
            color: white;
        }

        .btn-stop:hover {
            background: #c82333;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(220, 53, 69, 0.3);
        }

        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }

        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            display: none;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        @media (max-width: 1024px) {
            .content {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🍗 튀김 모니터링 시스템</h1>
            <p>실시간 세그멘테이션 & 데이터 수집</p>
        </header>

        <div class="content">
            <!-- 비디오 섹션 -->
            <div class="video-section">
                <h2>실시간 카메라</h2>
                <div class="video-container">
                    <img src="{{ url_for('video_feed') }}" alt="Video Stream">
                </div>
            </div>

            <!-- 컨트롤 섹션 -->
            <div class="control-section">
                <!-- 상태 카드 -->
                <div class="card">
                    <h2>세션 상태</h2>
                    <p>
                        <span id="status-indicator" class="status-indicator status-inactive"></span>
                        <strong id="status-text">대기 중</strong>
                    </p>
                    <p id="session-id" style="margin-top: 10px; color: #666;"></p>
                    <p id="elapsed-time" style="margin-top: 5px; font-size: 1.5em; font-weight: bold; color: #667eea;"></p>
                </div>

                <!-- 특징 카드 -->
                <div class="card">
                    <h2>실시간 특징</h2>
                    <div class="feature-grid">
                        <div class="feature-item">
                            <div class="feature-label">음식 영역</div>
                            <div class="feature-value" id="feat-area">0.0%</div>
                        </div>
                        <div class="feature-item">
                            <div class="feature-label">갈색 비율</div>
                            <div class="feature-value" id="feat-brown">0.0%</div>
                        </div>
                        <div class="feature-item">
                            <div class="feature-label">황금색 비율</div>
                            <div class="feature-value" id="feat-golden">0.0%</div>
                        </div>
                        <div class="feature-item">
                            <div class="feature-label">색상(Hue)</div>
                            <div class="feature-value" id="feat-hue">0°</div>
                        </div>
                    </div>
                </div>

                <!-- 세션 시작 카드 -->
                <div class="card">
                    <h2>세션 제어</h2>
                    <div id="alert-box" class="alert"></div>

                    <div class="form-group">
                        <label for="food-type">음식 종류</label>
                        <select id="food-type">
                            <option value="chicken">치킨 (Chicken)</option>
                            <option value="shrimp">새우 (Shrimp)</option>
                            <option value="potato">감자 (Potato)</option>
                            <option value="fish">생선 (Fish)</option>
                            <option value="vegetable">야채 (Vegetable)</option>
                            <option value="other">기타 (Other)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="notes">메모</label>
                        <textarea id="notes" rows="2" placeholder="온도 설정, 특이사항 등..."></textarea>
                    </div>

                    <button id="btn-start" class="btn-start" onclick="startSession()">🔴 세션 시작</button>

                    <div class="form-group" id="completion-group" style="display: none;">
                        <label for="probe-temp">탐침 온도 (°C)</label>
                        <input type="number" id="probe-temp" value="75.0" step="0.1">
                    </div>

                    <button id="btn-complete" class="btn-complete" onclick="markCompletion()" disabled>✅ 완료 마킹</button>
                    <button id="btn-stop" class="btn-stop" onclick="stopSession()" disabled>⏹ 세션 종료</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let sessionActive = false;

        // 상태 업데이트 (1초마다)
        setInterval(updateStatus, 1000);

        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                sessionActive = data.session_active;

                // UI 업데이트
                const indicator = document.getElementById('status-indicator');
                const statusText = document.getElementById('status-text');
                const sessionId = document.getElementById('session-id');
                const elapsedTime = document.getElementById('elapsed-time');

                if (sessionActive) {
                    indicator.className = 'status-indicator status-active';
                    statusText.textContent = '진행 중';
                    sessionId.textContent = `Session: ${data.session_id}`;

                    const elapsed = data.elapsed_time;
                    const minutes = Math.floor(elapsed / 60);
                    const seconds = Math.floor(elapsed % 60);
                    elapsedTime.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    indicator.className = 'status-indicator status-inactive';
                    statusText.textContent = '대기 중';
                    sessionId.textContent = '';
                    elapsedTime.textContent = '';
                }

                // 특징 업데이트
                const features = data.features;
                document.getElementById('feat-area').textContent = (features.food_area * 100).toFixed(1) + '%';
                document.getElementById('feat-brown').textContent = (features.brown_ratio * 100).toFixed(1) + '%';
                document.getElementById('feat-golden').textContent = (features.golden_ratio * 100).toFixed(1) + '%';
                document.getElementById('feat-hue').textContent = features.hue_mean.toFixed(1) + '°';

                // 버튼 상태
                document.getElementById('btn-start').disabled = sessionActive;
                document.getElementById('btn-complete').disabled = !sessionActive;
                document.getElementById('btn-stop').disabled = !sessionActive;
                document.getElementById('completion-group').style.display = sessionActive ? 'block' : 'none';

            } catch (error) {
                console.error('Status update failed:', error);
            }
        }

        async function startSession() {
            const foodType = document.getElementById('food-type').value;
            const notes = document.getElementById('notes').value;

            try {
                const response = await fetch('/api/start_session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({food_type: foodType, notes: notes})
                });

                const data = await response.json();
                showAlert(data.message, data.success ? 'success' : 'error');

                if (data.success) {
                    updateStatus();
                }
            } catch (error) {
                showAlert('세션 시작 실패: ' + error, 'error');
            }
        }

        async function markCompletion() {
            const probeTemp = document.getElementById('probe-temp').value;
            const notes = document.getElementById('notes').value;

            try {
                const response = await fetch('/api/mark_completion', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({probe_temp: probeTemp, notes: notes})
                });

                const data = await response.json();
                showAlert(data.message, data.success ? 'success' : 'error');
            } catch (error) {
                showAlert('완료 마킹 실패: ' + error, 'error');
            }
        }

        async function stopSession() {
            if (!confirm('세션을 종료하시겠습니까?')) return;

            try {
                const response = await fetch('/api/stop_session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });

                const data = await response.json();
                showAlert(data.message, data.success ? 'success' : 'error');

                if (data.success) {
                    updateStatus();
                }
            } catch (error) {
                showAlert('세션 종료 실패: ' + error, 'error');
            }
        }

        function showAlert(message, type) {
            const alertBox = document.getElementById('alert-box');
            alertBox.textContent = message;
            alertBox.className = 'alert alert-' + type;
            alertBox.style.display = 'block';

            setTimeout(() => {
                alertBox.style.display = 'none';
            }, 5000);
        }

        // 초기 상태 업데이트
        updateStatus();
    </script>
</body>
</html>"""

    template_path = template_dir / "viewer.html"
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ HTML 템플릿 생성: {template_path}")


if __name__ == "__main__":
    import sys

    port = 5000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    run_server(port=port)
