#!/usr/bin/env python3
import sys
sys.path.append('.')
import time
import cv2
from camera_monitor.camera_base import CameraBase

camera = CameraBase()
if camera.initialize():
    info = camera.get_info()
    print(f"카메라 정보: {info}")
    
    # 실제 카메라 해상도 사용!
    width = info['width']
    height = info['height']
    fps = 30  # FPS는 30으로 고정 (260은 너무 높음)
    
    print(f"녹화 설정: {width}x{height} @ {fps}fps")
    
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out = cv2.VideoWriter('test_correct.avi', fourcc, fps, (width, height))
    
    if out.isOpened():
        print("5초 녹화 시작...")
        
        for i in range(150):
            ret, frame = camera.read_frame()
            if ret:
                out.write(frame)
                if i % 30 == 0:
                    print(f"{i//30 + 1}초...")
            time.sleep(0.033)
        
        out.release()
        
        import os
        size = os.path.getsize('test_correct.avi')
        print(f"✅ 파일 크기: {size/1024:.1f} KB")
        
        if size > 100000:
            print("✅ 성공! 파일이 제대로 생성되었습니다!")
        else:
            print("⚠️ 여전히 파일이 작습니다.")
    
    camera.release()