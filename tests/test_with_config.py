#!/usr/bin/env python3
"""
Config 파일을 사용한 카메라 테스트
"""
import sys
sys.path.append('.')
import time

from config import Config
from camera_monitor.camera_base import CameraBase
from camera_monitor.recorder import MediaRecorder
from camera_monitor.motion_detector import MotionDetector

print("=" * 50)
print("📋 Config 기반 카메라 테스트")
print("=" * 50)

# 1. Config 로드
print("\n1️⃣ Config 로드 중...")
config = Config("camera_config.json")

print(f"   카메라 이름: {config.get('camera.name')}")
print(f"   해상도: {config.get('camera.resolution.width')}x{config.get('camera.resolution.height')}")
print(f"   FPS: {config.get('camera.fps')}")
print(f"   코덱: {config.get('recording.codec')}")

# 2. 카메라 초기화
print("\n2️⃣ 카메라 초기화 중...")
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

print("✅ 카메라 초기화 성공!")
print(f"   실제 정보: {camera.get_info()}")

# 3. Recorder 초기화
print("\n3️⃣ Recorder 초기화 중...")
recorder = MediaRecorder(
    camera,
    recording_dir=config.get('recording.output_dir'),
    screenshot_dir=config.get('screenshot.output_dir')
)
print("✅ Recorder 준비 완료!")

# 4. 스크린샷 테스트
print("\n4️⃣ 스크린샷 테스트...")
ret, frame = camera.read_frame()
if ret:
    screenshot = recorder.take_screenshot(
        frame, 
        f"config_test.{config.get('screenshot.format')}"
    )
    print(f"✅ 스크린샷 저장: {screenshot}")

# 5. 비디오 녹화 테스트
print("\n5️⃣ 3초 비디오 녹화 테스트...")
if recorder.start_recording("config_test.avi", codec=config.get('recording.codec')):
    for i in range(90):  # 3초
        ret, frame = camera.read_frame()
        if ret:
            recorder.write_frame(frame)
            if i % 30 == 0:
                print(f"   {i//30 + 1}초...")
        time.sleep(0.033)
    
    video_file = recorder.stop_recording()
    
    # 파일 크기 확인
    import os
    size = os.path.getsize(video_file)
    print(f"✅ 녹화 완료: {video_file}")
    print(f"   파일 크기: {size/1024:.1f} KB")
    
    if size > 100000:
        print("   ✅ 파일 크기 정상!")
    else:
        print("   ⚠️ 파일이 작을 수 있습니다")

# 6. 움직임 감지 테스트
print("\n6️⃣ 움직임 감지기 초기화...")
detector = MotionDetector(
    threshold=config.get('motion_detection.threshold'),
    min_area=config.get('motion_detection.min_area')
)

if config.get('motion_detection.enabled'):
    detector.enable()
    print("✅ 움직임 감지 활성화됨")
else:
    print("⏸️ 움직임 감지 비활성화됨 (config 설정)")

# 7. 정리
print("\n7️⃣ 정리 중...")
camera.release()

print("\n" + "=" * 50)
print("🎉 모든 테스트 완료!")
print("=" * 50)
print("\n📊 설정 요약:")
print(f"   - 카메라: {config.get('camera.name')}")
print(f"   - 해상도: {config.get('camera.resolution.width')}x{config.get('camera.resolution.height')}")
print(f"   - FPS: {config.get('camera.fps')}")
print(f"   - 녹화 디렉토리: {config.get('recording.output_dir')}")
print(f"   - 스크린샷 디렉토리: {config.get('screenshot.output_dir')}")
print(f"   - 코덱: {config.get('recording.codec')}")