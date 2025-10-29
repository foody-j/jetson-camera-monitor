"""
Fixed camera module with better Jetson and USB camera support
Tries multiple OpenCV backends to ensure camera works
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any


class CameraBaseFixed:
    """Improved camera class with multiple backend support"""

    def __init__(self, camera_index: int = 0, resolution: Tuple[int, int] = (640, 360)):
        """
        Initialize camera with backend auto-detection

        Args:
            camera_index (int): Camera index or device path
            resolution (tuple): Resolution (width, height)
        """
        self.camera_index = camera_index
        self.resolution = resolution
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_initialized = False
        self.backend_used = None

    def initialize(self) -> bool:
        """
        Initialize camera with multiple backend attempts

        Returns:
            bool: Success status
        """
        # Try different backends in order of preference for Jetson/USB cameras
        backends = [
            (cv2.CAP_V4L2, "V4L2 (Linux)"),
            (cv2.CAP_ANY, "AUTO"),
            (cv2.CAP_GSTREAMER, "GStreamer"),
        ]

        for backend, name in backends:
            print(f"Trying {name} backend...")

            try:
                # For V4L2, specify device path directly
                if backend == cv2.CAP_V4L2:
                    device = f"/dev/video{self.camera_index}" if isinstance(self.camera_index, int) else self.camera_index
                    self.cap = cv2.VideoCapture(device, backend)
                else:
                    self.cap = cv2.VideoCapture(self.camera_index, backend)

                if not self.cap.isOpened():
                    print(f"  ✗ {name} - Failed to open")
                    continue

                # Try to read a test frame
                ret, test_frame = self.cap.read()
                if not ret or test_frame is None:
                    print(f"  ✗ {name} - Opened but can't read frames")
                    self.cap.release()
                    continue

                # Success! Set resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

                # Get actual resolution (might differ from requested)
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                self.is_initialized = True
                self.backend_used = name

                print(f"  ✓ {name} - SUCCESS!")
                print(f"  Resolution: {actual_width}x{actual_height}")
                return True

            except Exception as e:
                print(f"  ✗ {name} - Exception: {e}")
                if self.cap:
                    self.cap.release()
                continue

        print("\n❌ Failed to initialize camera with any backend")
        print("\nTroubleshooting:")
        print("  1. Check camera is connected: ls -l /dev/video*")
        print("  2. Check permissions: groups (should include 'video')")
        print("  3. Check if camera is in use: sudo lsof /dev/video0")
        print("  4. Try closing other camera applications")

        return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from camera

        Returns:
            tuple: (success, frame)
        """
        if not self.is_initialized or not self.cap:
            return False, None

        ret, frame = self.cap.read()
        return ret, frame if ret else None

    def release(self) -> None:
        """Release camera resources"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_initialized = False
        print("Camera released")

    def get_info(self) -> Dict[str, Any]:
        """Get camera information"""
        if not self.is_initialized or not self.cap:
            return {}

        return {
            'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': int(self.cap.get(cv2.CAP_PROP_FPS)) or 30,
            'backend': self.backend_used
        }

    @property
    def fps(self) -> int:
        """Get FPS"""
        if not self.is_initialized or not self.cap:
            return 30
        return int(self.cap.get(cv2.CAP_PROP_FPS)) or 30

    def __enter__(self):
        """Context manager entry"""
        if not self.initialize():
            raise RuntimeError("Camera initialization failed")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()

    def __del__(self):
        """Destructor"""
        self.release()


def get_available_cameras(max_index: int = 5) -> list:
    """
    Get list of available cameras with detailed info

    Args:
        max_index: Maximum index to check

    Returns:
        list: Available camera info
    """
    available_cameras = []

    for i in range(max_index):
        # Try V4L2 backend specifically
        device_path = f"/dev/video{i}"
        cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)

        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                available_cameras.append({
                    'index': i,
                    'device': device_path,
                    'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    'fps': int(cap.get(cv2.CAP_PROP_FPS)) or 30
                })

        cap.release()

    return available_cameras


if __name__ == "__main__":
    """Test the fixed camera class"""
    print("=" * 50)
    print("Testing CameraBaseFixed")
    print("=" * 50)

    print("\nAvailable cameras:")
    cameras = get_available_cameras()
    for cam in cameras:
        print(f"  Camera {cam['index']}: {cam['device']} - {cam['width']}x{cam['height']}")

    if not cameras:
        print("  No cameras found")
    else:
        print(f"\nTesting camera 0...")
        with CameraBaseFixed(0, (640, 480)) as camera:
            print(f"\nCamera info: {camera.get_info()}")
            print("\nCapturing 10 frames...")

            for i in range(10):
                ret, frame = camera.read_frame()
                if ret:
                    print(f"  Frame {i+1}: {frame.shape}")
                else:
                    print(f"  Frame {i+1}: Failed")

            print("\nTest complete!")
