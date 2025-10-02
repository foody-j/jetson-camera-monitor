#!/usr/bin/env python3
import sys
sys.path.append('.')
import time
from camera_monitor.camera_base import CameraBase
from camera_monitor.recorder import MediaRecorder

camera = CameraBase()
if camera.initialize():
    recorder = MediaRecorder(camera)
    
    print("30초간 live.jpg 실시간 업데이트...")
    print("다른 터미널에서 'ls -la live.jpg'로 확인 가능")
    
    for i in range(300):
        ret, frame = camera.read_frame()
        if ret:
            recorder.take_screenshot(frame, 'live.jpg')
            if i % 50 == 0:
                print(f"{i//10}초 경과...")
        time.sleep(0.1)
    
    print("✅ 완료!")
    camera.release()