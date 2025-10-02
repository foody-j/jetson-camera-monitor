#!/usr/bin/env python3
import sys
sys.path.append('.')
import time
from camera_monitor.camera_base import CameraBase
from camera_monitor.recorder import MediaRecorder

camera = CameraBase()
if camera.initialize():
    recorder = MediaRecorder(camera)
    
    # 5초 녹화
    print("5초간 녹화 시작...")
    if recorder.start_recording("test_video.avi"):
        for i in range(150):  # 5초 x 30fps
            ret, frame = camera.read_frame()
            if ret:
                recorder.write_frame(frame)
                if i % 30 == 0:
                    print(f"{i//30 + 1}초...")
            time.sleep(0.033)
        
        video_file = recorder.stop_recording()
        print(f"✅ 녹화 완료: {video_file}")
    
    camera.release()