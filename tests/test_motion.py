#!/usr/bin/env python3
"""
움직임 감지 테스트
"""
import sys
import os
# 상위 폴더를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from config import Config
from camera_monitor.camera_base import CameraBase
from camera_monitor.motion_detector import MotionDetector
from camera_monitor.recorder import MediaRecorder

print("=" * 50)
print("🚨 움직임 감지 테스트")
print("=" * 50)

# Config 로드
config = Config("camera_config.json")

# 카메라 초기화
camera = CameraBase(
    camera_index=config.get('camera.index'),
    resolution=(
        config.get('camera.resolution.width'),
        config.get('camera.resolution.height')
    )
)

if not camera.initialize():
    print("❌ 카메라 초기화 실패")
    sys.exit(1)

# Recorder 초기화 (움직임 감지 시 스크린샷 저장)
recorder = MediaRecorder(
    camera,
    screenshot_dir=config.get('screenshot.output_dir')
)

# 움직임 감지기 초기화
detector = MotionDetector(
    threshold=config.get('motion_detection.threshold'),
    min_area=config.get('motion_detection.min_area')
)

motion_count = 0

def on_motion_detected(frame):
    """움직임 감지 시 호출될 콜백"""
    global motion_count
    motion_count += 1
    timestamp = time.strftime('%H:%M:%S')
    
    # 스크린샷 저장
    filename = f"motion_{motion_count:03d}_{time.strftime('%H%M%S')}.jpg"
    saved = recorder.take_screenshot(frame, filename)
    
    print(f"🚨 [{timestamp}] 움직임 #{motion_count} 감지! → {saved}")

# 콜백 설정 및 활성화
detector.set_callback(on_motion_detected)
detector.enable()

print(f"\n설정:")
print(f"  - 감지 임계값: {config.get('motion_detection.threshold')}")
print(f"  - 최소 영역: {config.get('motion_detection.min_area')}")
print(f"  - 스크린샷 저장 위치: {config.get('screenshot.output_dir')}")

print("\n20초간 움직임 감지 테스트 시작...")
print("👉 카메라 앞에서 움직여보세요!")
print("Ctrl+C로 중단 가능\n")

start_time = time.time()
frame_count = 0

try:
    while time.time() - start_time < 20:  # 20초간 실행
        ret, frame = camera.read_frame()
        if ret:
            frame_count += 1
            
            # 움직임 감지
            motion_detected, mask = detector.detect(frame)
            
            # 5초마다 상태 출력
            elapsed = time.time() - start_time
            if frame_count % 150 == 0:  # 30fps 기준 5초
                print(f"⏱️ {elapsed:.1f}초 경과 | 총 움직임: {motion_count}회")
        
        time.sleep(0.033)  # 약 30fps

except KeyboardInterrupt:
    print("\n\n⏸️ 사용자에 의해 중단됨")

finally:
    camera.release()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과")
    print("=" * 50)
    print(f"  - 총 실행 시간: {time.time() - start_time:.1f}초")
    print(f"  - 총 프레임: {frame_count}")
    print(f"  - 감지된 움직임: {motion_count}회")
    print(f"  - 저장된 스크린샷: {motion_count}개")
    print("\n✅ 테스트 완료!")