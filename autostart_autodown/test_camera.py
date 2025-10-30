#!/usr/bin/env python3
"""Quick camera test to find working camera device"""
import cv2

print("Testing camera devices...")

for i in [0, 1, 2]:
    print(f"\nTrying /dev/video{i}...")
    cap = cv2.VideoCapture(i)

    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"  ✅ SUCCESS: Camera {i} works! Resolution: {w}x{h}")
            print(f"     FPS: {cap.get(cv2.CAP_PROP_FPS)}")
            cap.release()
        else:
            print(f"  ❌ Camera {i} opened but can't read frames")
            cap.release()
    else:
        print(f"  ❌ Camera {i} failed to open")

print("\n✅ Test complete!")
