#!/usr/bin/env python3
"""
OpenCV + GStreamer Camera with Multiprocessing
OpenCV의 GStreamer 백엔드 사용 (안정성 향상)
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Value
import numpy as np
import time
import ctypes
import signal
import os
import cv2


def camera_process(device_index, width, height, fps, frame_queue, running_flag, ready_flag, error_flag):
    """
    별도 프로세스 - OpenCV GStreamer 백엔드
    """
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    device_path = f"/dev/video{device_index}"
    print(f"[CameraProcess {device_index}] Starting for {device_path}", flush=True)

    cap = None
    try:
        # OpenCV + GStreamer pipeline
        gst_str = (
            f"v4l2src device={device_path} io-mode=2 ! "
            f"video/x-raw, format=UYVY, width={width}, height={height}, framerate={fps}/1 ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! "
            f"appsink drop=1 max-buffers=1"
        )

        cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)

        if not cap.isOpened():
            print(f"[CameraProcess {device_index}] ERROR: Failed to open", flush=True)
            error_flag.value = 1
            return

        print(f"[CameraProcess {device_index}] Opened with GStreamer", flush=True)

        # 첫 프레임 대기
        for _ in range(30):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                print(f"[CameraProcess {device_index}] First frame: {frame.shape}, mean={frame.mean():.1f}", flush=True)
                ready_flag.value = 1
                break
            time.sleep(0.1)

        if not ready_flag.value:
            print(f"[CameraProcess {device_index}] No frames!", flush=True)
            error_flag.value = 1
            return

        no_frame_count = 0

        while running_flag.value:
            ret, frame = cap.read()

            if ret and frame is not None and frame.size > 0:
                no_frame_count = 0
                try:
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()
                        except:
                            pass
                    frame_queue.put_nowait(frame)
                except:
                    pass
            else:
                no_frame_count += 1
                if no_frame_count > 150:
                    print(f"[CameraProcess {device_index}] No frames 5s", flush=True)
                    no_frame_count = 0
                time.sleep(0.01)

    except Exception as e:
        print(f"[CameraProcess {device_index}] ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        error_flag.value = 1
    finally:
        if cap:
            try:
                cap.release()
            except:
                pass
        print(f"[CameraProcess {device_index}] Exit", flush=True)


class GstCameraMP:
    """OpenCV+GStreamer 멀티프로세스 카메라"""

    def __init__(self, device_index, width=1920, height=1536, fps=30):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps

        self.process = None
        self.frame_queue = None
        self.running_flag = None
        self.ready_flag = None
        self.error_flag = None
        self.latest_frame = None
        self._pid = None

        print(f"[GstCameraMP] Creating camera {device_index}")

    def start(self):
        if self.process and self.process.is_alive():
            return True

        self.frame_queue = Queue(maxsize=2)
        self.running_flag = Value(ctypes.c_int, 1)
        self.ready_flag = Value(ctypes.c_int, 0)
        self.error_flag = Value(ctypes.c_int, 0)

        self.process = Process(
            target=camera_process,
            args=(
                self.device_index,
                self.width,
                self.height,
                self.fps,
                self.frame_queue,
                self.running_flag,
                self.ready_flag,
                self.error_flag
            ),
            daemon=False
        )
        self.process.start()
        self._pid = self.process.pid
        print(f"[GstCameraMP] Camera {self.device_index} PID: {self._pid}")

        for _ in range(50):
            if self.ready_flag.value:
                print(f"[GstCameraMP] Camera {self.device_index} ready!")
                return True
            if self.error_flag.value:
                print(f"[GstCameraMP] Camera {self.device_index} failed")
                self._force_kill()
                return False
            time.sleep(0.1)

        print(f"[GstCameraMP] Camera {self.device_index} timeout")
        return False

    def read(self):
        if not self.process or not self.process.is_alive():
            return False, None

        try:
            while not self.frame_queue.empty():
                self.latest_frame = self.frame_queue.get_nowait()
        except:
            pass

        if self.latest_frame is not None:
            return True, self.latest_frame.copy()
        return False, None

    def isOpened(self):
        return self.process is not None and self.process.is_alive()

    def _force_kill(self):
        if self._pid:
            try:
                os.kill(self._pid, signal.SIGKILL)
            except:
                pass

    def stop(self):
        if not self.process:
            return

        print(f"[GstCameraMP] Stopping {self.device_index}...")

        if self.running_flag:
            self.running_flag.value = 0

        if self.process.is_alive():
            self.process.join(timeout=0.5)

        if self.process.is_alive():
            self._force_kill()
            time.sleep(0.1)

        if self.frame_queue:
            try:
                self.frame_queue.close()
            except:
                pass

        self.process = None
        self._pid = None
        self.latest_frame = None

    def release(self):
        self.stop()


if __name__ == "__main__":
    print("Testing OpenCV+GStreamer Camera...")

    cameras = []
    for i in range(4):
        cam = GstCameraMP(device_index=i, width=1920, height=1536, fps=30)
        if cam.start():
            cameras.append(cam)
            print(f"Camera {i} started")
        else:
            print(f"Camera {i} FAILED")
        time.sleep(1.0)

    print(f"\n{len(cameras)} cameras running...")

    for iteration in range(5):
        time.sleep(0.5)
        print(f"\n--- Iteration {iteration + 1} ---")
        for i, cam in enumerate(cameras):
            ret, frame = cam.read()
            if ret:
                print(f"  Camera {i}: {frame.shape}, mean={frame.mean():.1f}")
            else:
                print(f"  Camera {i}: No frame")

    print("\nStopping...")
    for cam in cameras:
        cam.stop()
    print("Done!")
