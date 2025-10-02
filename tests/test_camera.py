#!/usr/bin/env python3
"""
카메라 모니터링 테스트
"""
import sys
sys.path.append('.')

from camera_monitor.camera_base import CameraBase
from camera_monitor.recorder import MediaRecorder
from camera_monitor.motion_detector import MotionDetector

print("🎯 카메라 모니터링 테스트 시작")

# 1. 카메라 테스트
print("\n1. 카메라 초기화...")
camera = CameraBase()
if camera.initialize():
    print("✅ 카메라 OK!")
    
    # 2. 녹화기 테스트
    print("\n2. 녹화기 테스트...")
    recorder = MediaRecorder(camera)
    print("✅ 녹화기 OK!")
    
    # 3. 스크린샷 테스트
    print("\n3. 스크린샷 촬영...")
    ret, frame = camera.read_frame()
    if ret:
        screenshot = recorder.take_screenshot(frame, 'test_screenshot.jpg')
        print(f"✅ 스크린샷 저장: {screenshot}")
    
    # 4. 움직임 감지 테스트
    print("\n4. 움직임 감지기 생성...")
    detector = MotionDetector()
    print("✅ 움직임 감지기 OK!")
    
    camera.release()
    print("\n🎉 모든 테스트 성공!")
else:
    print("❌ 카메라 초기화 실패")