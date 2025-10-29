#!/usr/bin/env python3
"""Simple direct camera test"""

import cv2
import sys

print("Testing camera with different methods...")
print("=" * 50)

# Method 1: Direct index with V4L2
print("\n1. Testing index 0 with CAP_V4L2...")
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
if cap.isOpened():
    print("  ✓ Camera opened!")
    ret, frame = cap.read()
    if ret:
        print(f"  ✓ Frame captured: {frame.shape}")
        cv2.imwrite("test_frame_method1.jpg", frame)
        print("  ✓ Saved: test_frame_method1.jpg")

        # Show frame for 3 seconds
        cv2.imshow("Camera Test - Method 1", frame)
        print("\n  Displaying frame for 3 seconds...")
        cv2.waitKey(3000)
        cv2.destroyAllWindows()
    else:
        print("  ✗ Could not read frame")
    cap.release()
else:
    print("  ✗ Failed to open")

# Method 2: Direct index with CAP_ANY
print("\n2. Testing index 0 with CAP_ANY...")
cap = cv2.VideoCapture(0, cv2.CAP_ANY)
if cap.isOpened():
    print("  ✓ Camera opened!")
    ret, frame = cap.read()
    if ret:
        print(f"  ✓ Frame captured: {frame.shape}")
        cv2.imwrite("test_frame_method2.jpg", frame)
        print("  ✓ Saved: test_frame_method2.jpg")
    else:
        print("  ✗ Could not read frame")
    cap.release()
else:
    print("  ✗ Failed to open")

# Method 3: Direct index, no backend specified
print("\n3. Testing index 0 with default backend...")
cap = cv2.VideoCapture(0)
if cap.isOpened():
    print("  ✓ Camera opened!")
    ret, frame = cap.read()
    if ret:
        print(f"  ✓ Frame captured: {frame.shape}")
        cv2.imwrite("test_frame_method3.jpg", frame)
        print("  ✓ Saved: test_frame_method3.jpg")
    else:
        print("  ✗ Could not read frame")
    cap.release()
else:
    print("  ✗ Failed to open")

print("\n" + "=" * 50)
print("Test complete!")
