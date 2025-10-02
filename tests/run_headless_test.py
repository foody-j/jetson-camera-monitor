import sys
sys.path.append('.')
import time
from camera_monitor.camera_base import CameraBase
from camera_monitor.recorder import MediaRecorder

camera = CameraBase()
if camera.initialize():
    recorder = MediaRecorder(camera)
    
    print("10초간 live.jpg 업데이트 중...")
    for i in range(100):
        ret, frame = camera.read_frame()
        if ret:
            recorder.take_screenshot(frame, 'live.jpg')
            print(f"\r{i+1}/100 프레임", end='')
        time.sleep(0.1)
    
    print("\n✅ 완료!")
    camera.release()