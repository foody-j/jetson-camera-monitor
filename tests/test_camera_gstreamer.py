#!/usr/bin/env python3
"""Test camera using GStreamer pipeline for Jetson"""

import cv2

print("Testing camera with GStreamer pipeline...")
print("=" * 60)

# GStreamer pipeline for USB camera (bypasses nvargus-daemon)
# This pipeline reads from /dev/video0 directly using v4l2src
gst_pipeline = (
    "v4l2src device=/dev/video0 ! "
    "image/jpeg,width=640,height=360,framerate=30/1 ! "
    "jpegdec ! "
    "videoconvert ! "
    "appsink"
)

print("\nGStreamer pipeline:")
print(gst_pipeline)
print("\nOpening camera...")

cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("\n✗ Failed to open camera with GStreamer")
    print("\nTrying alternative pipeline (raw video)...")

    # Alternative pipeline for raw video (not MJPEG)
    gst_pipeline_alt = (
        "v4l2src device=/dev/video0 ! "
        "video/x-raw,width=640,height=360,framerate=30/1 ! "
        "videoconvert ! "
        "appsink"
    )

    print(gst_pipeline_alt)
    cap = cv2.VideoCapture(gst_pipeline_alt, cv2.CAP_GSTREAMER)

if cap.isOpened():
    print("\n✓ Camera opened successfully!")

    print("\nReading frames...")
    for i in range(5):
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"  Frame {i+1}: {frame.shape} - ✓")

            if i == 0:
                # Save and display first frame
                filename = "test_gstreamer_frame.jpg"
                cv2.imwrite(filename, frame)
                print(f"\n  Saved: {filename}")

                # Display frame
                cv2.imshow("Camera Test - GStreamer", frame)
                print("  Displaying for 3 seconds...")
                cv2.waitKey(3000)
                cv2.destroyAllWindows()
        else:
            print(f"  Frame {i+1}: Failed - ✗")

    cap.release()
    print("\n✓ Test successful!")
    print("\n" + "=" * 60)
    print("Your camera is working! Use GStreamer pipeline in your code.")
    print("=" * 60)

else:
    print("\n✗ Failed to open camera")
    print("\nTroubleshooting:")
    print("  1. Check GStreamer plugins: gst-inspect-1.0 v4l2src")
    print("  2. Test with gst-launch:")
    print("     gst-launch-1.0 v4l2src device=/dev/video0 ! jpegdec ! videoconvert ! xvimagesink")
