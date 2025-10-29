#!/usr/bin/env python3
"""
Direct camera test with explicit V4L2 backend and format
"""

import cv2
import sys

print("=" * 60)
print("Direct Camera Access Test")
print("=" * 60)

# Try to open with explicit V4L2 backend and device index
backends_to_try = [
    (cv2.CAP_V4L2, "V4L2"),
    (cv2.CAP_V4L, "V4L (legacy)"),
]

for backend_id, backend_name in backends_to_try:
    print(f"\nTrying backend: {backend_name}")
    print("-" * 60)

    cap = cv2.VideoCapture(0, backend_id)

    if not cap.isOpened():
        print(f"  ✗ Failed to open with {backend_name}")
        continue

    print(f"  ✓ Camera opened with {backend_name}")

    # Try to set MJPEG format (as shown by v4l2-ctl)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    # Try to read a frame
    ret, frame = cap.read()

    if ret and frame is not None:
        print(f"  ✓ SUCCESS! Frame captured: {frame.shape}")

        # Save the frame
        filename = f"test_frame_{backend_name.lower().replace(' ', '_')}.jpg"
        cv2.imwrite(filename, frame)
        print(f"  ✓ Saved: {filename}")

        # Display for 2 seconds
        try:
            cv2.imshow(f"Camera Test - {backend_name}", frame)
            print(f"  Displaying frame for 2 seconds...")
            cv2.waitKey(2000)
            cv2.destroyAllWindows()
        except:
            print(f"  (Could not display - no GUI available)")

        cap.release()

        print("\n" + "=" * 60)
        print("✓ CAMERA IS WORKING!")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"  ✗ Failed to read frame")

    cap.release()

print("\n" + "=" * 60)
print("✗ All backends failed")
print("=" * 60)
print("\nTroubleshooting:")
print("  1. Try unplugging and replugging the USB camera")
print("  2. Try: sudo rmmod uvcvideo && sudo modprobe uvcvideo")
print("  3. Reboot the system")
sys.exit(1)
