#!/usr/bin/env python3
"""
Camera Detection and Test Script
Helps diagnose camera connection issues
"""

import cv2
import sys

def test_camera_detection():
    """Test and list all available cameras"""
    print("=" * 50)
    print("Camera Detection Test")
    print("=" * 50)

    available_cameras = []

    # Test camera indices 0-10
    print("\nScanning for cameras (indices 0-10)...\n")

    for i in range(11):
        print(f"Testing camera index {i}...", end=" ")
        cap = cv2.VideoCapture(i)

        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                # Get camera properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))

                available_cameras.append({
                    'index': i,
                    'width': width,
                    'height': height,
                    'fps': fps
                })

                print(f"✓ FOUND - {width}x{height} @ {fps}fps")
            else:
                print("✗ Opened but can't read frames")
        else:
            print("✗ Not available")

        cap.release()

    print("\n" + "=" * 50)
    print(f"Summary: Found {len(available_cameras)} working camera(s)")
    print("=" * 50)

    if available_cameras:
        print("\nAvailable cameras:")
        for cam in available_cameras:
            print(f"  - Camera {cam['index']}: {cam['width']}x{cam['height']} @ {cam['fps']}fps")

        # Test the first available camera
        print("\n" + "=" * 50)
        print("Testing first available camera...")
        print("=" * 50)

        test_index = available_cameras[0]['index']
        test_camera_display(test_index)

    else:
        print("\n❌ No working cameras found!")
        print("\nPossible reasons:")
        print("  1. Camera is not connected")
        print("  2. Camera drivers not installed")
        print("  3. Permission denied (try: sudo usermod -aG video $USER)")
        print("  4. Camera is being used by another application")
        print("  5. OpenCV not built with proper camera support")

        # Show video devices
        print("\nChecking /dev/video* devices:")
        import os
        video_devs = [f for f in os.listdir('/dev') if f.startswith('video')]
        if video_devs:
            for dev in sorted(video_devs):
                print(f"  - /dev/{dev}")
        else:
            print("  - No /dev/video* devices found")

    return available_cameras


def test_camera_display(camera_index=0):
    """Test camera with live display"""
    print(f"\nOpening camera {camera_index} for live test...")
    print("Press 'q' to quit, 's' to take a screenshot")

    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"❌ Failed to open camera {camera_index}")
        return False

    print("✓ Camera opened successfully!")
    print("\nDisplaying live feed...")

    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()

            if not ret or frame is None:
                print("❌ Failed to read frame")
                break

            frame_count += 1

            # Add overlay info
            cv2.putText(frame, f"Camera {camera_index} - Frame {frame_count}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "Press 'q' to quit",
                       (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, (255, 255, 255), 1)

            cv2.imshow(f'Camera {camera_index} Test', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\nTest stopped by user")
                break
            elif key == ord('s'):
                filename = f"camera_test_{camera_index}.jpg"
                cv2.imwrite(filename, frame)
                print(f"Screenshot saved: {filename}")

    except KeyboardInterrupt:
        print("\nTest interrupted by user")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"✓ Test completed - {frame_count} frames captured")

    return True


if __name__ == "__main__":
    print("\n🎥 Camera Diagnostic Tool\n")

    # Run detection test
    cameras = test_camera_detection()

    # If user wants to test a specific camera
    if len(sys.argv) > 1:
        try:
            camera_index = int(sys.argv[1])
            print(f"\n\nTesting camera index {camera_index} (from command line)...")
            test_camera_display(camera_index)
        except ValueError:
            print(f"Invalid camera index: {sys.argv[1]}")

    print("\n" + "=" * 50)
    print("Diagnostic complete!")
    print("=" * 50)
