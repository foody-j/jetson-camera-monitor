#!/usr/bin/env python3
"""
Simple test without YOLO - just camera and motion detection
"""
import cv2
import time
from datetime import datetime
import os

print("Testing basic camera and motion detection...")

# Config
CAMERA_INDEX = 1
MOTION_MIN_AREA = 1500
SNAPSHOT_DIR = "Detection_Test"

# Initialize camera
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"ERROR: Cannot open camera {CAMERA_INDEX}")
    exit(1)

ret, frame = cap.read()
if ret:
    h, w = frame.shape[:2]
    print(f"Camera OK - Resolution: {w}x{h}")
else:
    print("ERROR: Cannot read from camera")
    exit(1)

# Background subtractor for motion detection
bg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

print("\nRunning motion detection test...")
print("Press 'q' to quit")
print("-" * 50)

frame_count = 0
motion_count = 0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Skip warmup frames
        if frame_count < 30:
            cv2.putText(frame, f"Warming up... {30-frame_count}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow("Test", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        # Motion detection
        fg = bg.apply(frame)
        _, thr = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
        clean = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion = False
        vis = frame.copy()

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= MOTION_MIN_AREA:
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(vis, f"Area: {int(area)}", (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                motion = True

        if motion:
            motion_count += 1
            now = datetime.now()
            print(f"[{now.strftime('%H:%M:%S')}] Motion detected! (count: {motion_count})")

            # Save snapshot
            day_dir = now.strftime("%Y%m%d")
            ts_name = now.strftime("%H%M%S_%f")
            out_dir = os.path.join(SNAPSHOT_DIR, day_dir)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{ts_name}.jpg")
            cv2.imwrite(out_path, frame)

            cv2.putText(vis, "MOTION DETECTED!", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        status = f"Frames: {frame_count} | Motion: {motion_count}"
        cv2.putText(vis, status, (10, vis.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow("Test", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    print(f"\nTest complete: {motion_count} motion events detected in {frame_count} frames")
