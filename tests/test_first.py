import cv2
import time
import os

cap = cv2.VideoCapture(0)
frame_count = 0

while True:
    ret, frame = cap.read()
    if ret:
        # 타임스탬프 추가
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imwrite('/project/live.jpg', frame)
        print(f'\r프레임 {frame_count}: {timestamp}', end='', flush=True)
        frame_count += 1
    
    time.sleep(0.1)