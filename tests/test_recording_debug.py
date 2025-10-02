#!/usr/bin/env python3
import sys
sys.path.append('.')
import time
import cv2
from camera_monitor.camera_base import CameraBase

camera = CameraBase()
if camera.initialize():
    print(f"카메라 정보: {camera.get_info()}")
    
    # 직접 VideoWriter 테스트
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out = cv2.VideoWriter('test_direct.avi', fourcc, 30, (640, 480))
    
    print(f"VideoWriter 열림: {out.isOpened()}")
    
    if out.isOpened():
        print("5초 녹화 시작...")
        frame_count = 0
        
        for i in range(150):
            ret, frame = camera.read_frame()
            if ret and frame is not None:
                # 프레임 크기 확인
                if i == 0:
                    print(f"프레임 크기: {frame.shape}")
                
                out.write(frame)
                frame_count += 1
                
                if i % 30 == 0:
                    print(f"{i//30 + 1}초... (프레임 {frame_count}개)")
            else:
                print(f"프레임 읽기 실패: {i}")
            
            time.sleep(0.033)
        
        out.release()
        print(f"✅ 총 {frame_count}개 프레임 녹화")
        
        # 파일 크기 확인
        import os
        size = os.path.getsize('test_direct.avi')
        print(f"파일 크기: {size/1024:.1f} KB")
        
        if size < 100000:  # 100KB 미만이면
            print("⚠️ 파일이 너무 작습니다. 프레임이 제대로 안 들어갔을 수 있습니다.")
    else:
        print("❌ VideoWriter 열기 실패")
    
    camera.release()