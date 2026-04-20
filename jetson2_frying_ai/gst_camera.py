#!/usr/bin/env python3
"""
GStreamer Camera using subprocess + shared memory
Avoids Python GStreamer binding issues by using gst-launch-1.0 externally
"""

import subprocess
import numpy as np
import threading
import time
import os
import signal
import fcntl
import select


class GstCamera:
    """Camera using gst-launch subprocess with fdsink to pipe frames"""

    def __init__(self, device_index, width=1920, height=1536, fps=30):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.device_path = f"/dev/video{device_index}"
        self.preview_sink = os.getenv("GMSL_PREVIEW_SINK", "none")  # GUI에만 표시, GST 윈도우 안 띄움
        self.use_nvvidconv = os.getenv("GMSL_USE_NVVIDCONV", "1").lower() not in ("0", "false", "no")
        self.io_mode = os.getenv("GMSL_IO_MODE", "2")  # 4=dmabuf, 2=mmap (changed to mmap for stability)

        self.process = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.is_running = False
        self.thread = None
        self.last_frame_ts = 0.0
        self.last_unique_frame_ts = 0.0
        self.same_frame_count = 0
        self._last_frame_signature = None

        # BGR frame size
        self.frame_size = width * height * 3

        print(f"[GstCamera] Creating camera for {self.device_path} @ {width}x{height}")

    def start(self):
        """Start gst-launch subprocess"""
        if self.is_running:
            print(f"[GstCamera] Camera {self.device_index} already running")
            return True

        # GStreamer pipeline - tee preview sink to keep stream alive
        gst_cmd = [
            "gst-launch-1.0", "-q",
            "v4l2src", f"device={self.device_path}", f"io-mode={self.io_mode}", "!",
            f"video/x-raw,format=UYVY,width={self.width},height={self.height},framerate={self.fps}/1", "!",
            "tee", "name=t",
        ]

        if self.preview_sink.lower() != "none":
            if self.use_nvvidconv:
                gst_cmd += [
                    "t.", "!", "queue", "max-size-buffers=1", "leaky=downstream", "!",
                    "nvvidconv", "!", "video/x-raw,format=BGRx", "!", "videoconvert", "!",
                    self.preview_sink, "sync=false"
                ]
            else:
                gst_cmd += [
                    "t.", "!", "queue", "max-size-buffers=1", "leaky=downstream", "!", "videoconvert", "!",
                    self.preview_sink, "sync=false"
                ]

        if self.use_nvvidconv:
            gst_cmd += [
                "t.", "!", "queue", "max-size-buffers=1", "leaky=downstream", "!",
                "nvvidconv", "!", "video/x-raw,format=BGRx", "!", "videoconvert", "!",
                "video/x-raw,format=BGR", "!",
                "fdsink", "fd=1", "sync=false", "async=false"
            ]
        else:
            gst_cmd += [
                "t.", "!", "queue", "max-size-buffers=1", "leaky=downstream", "!",
                "videoconvert", "!",
                "video/x-raw,format=BGR", "!",
                "fdsink", "fd=1", "sync=false", "async=false"
            ]

        print(f"[GstCamera] Starting: {' '.join(gst_cmd)}")

        try:
            # Start subprocess with stdout pipe
            self.process = subprocess.Popen(
                gst_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=self.frame_size * 2,
                preexec_fn=os.setsid  # 새 프로세스 그룹으로 생성
            )

            self.is_running = True
            self.thread = threading.Thread(target=self._read_frames, daemon=True)
            self.thread.start()

            # Wait for first frame (최대 5초)
            for _ in range(50):
                time.sleep(0.1)
                with self.frame_lock:
                    if self.latest_frame is not None:
                        print(f"[GstCamera] Camera {self.device_index} started successfully")
                        return True

            # 프레임 못 받음
            print(f"[GstCamera] Camera {self.device_index} - no frames received")
            self.stop()
            return False

        except Exception as e:
            print(f"[ERROR] Failed to start camera {self.device_index}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _read_frames(self):
        """Read frames from subprocess stdout (non-blocking)"""
        try:
            # Set stdout to non-blocking
            fd = self.process.stdout.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            buffer = b''

            while self.is_running and self.process and self.process.poll() is None:
                # Wait for data with timeout
                readable, _, _ = select.select([self.process.stdout], [], [], 0.1)

                if not readable:
                    continue

                try:
                    chunk = self.process.stdout.read(self.frame_size)
                    if chunk:
                        buffer += chunk
                except BlockingIOError:
                    continue

                # Extract complete frames from buffer
                while len(buffer) >= self.frame_size:
                    frame_data = buffer[:self.frame_size]
                    buffer = buffer[self.frame_size:]

                    # Fast signature for repeated-frame detection
                    mid = self.frame_size // 2
                    signature = (
                        frame_data[:64],
                        frame_data[mid:mid + 64],
                        frame_data[-64:],
                    )

                    # Convert to numpy array
                    frame = np.frombuffer(frame_data, dtype=np.uint8).reshape(
                        (self.height, self.width, 3)
                    )

                    with self.frame_lock:
                        self.latest_frame = frame.copy()
                        now_ts = time.time()
                        self.last_frame_ts = now_ts
                        if signature == self._last_frame_signature:
                            self.same_frame_count += 1
                        else:
                            self._last_frame_signature = signature
                            self.same_frame_count = 0
                            self.last_unique_frame_ts = now_ts

        except Exception as e:
            if self.is_running:
                print(f"[ERROR] Frame read error camera {self.device_index}: {e}")
        finally:
            self.is_running = False

    def read(self):
        """Read the latest frame"""
        if not self.is_running:
            return False, None

        with self.frame_lock:
            if self.latest_frame is None:
                return False, None
            return True, self.latest_frame.copy()

    def isOpened(self):
        """Check if camera is running"""
        return self.is_running and self.process is not None

    def stop(self):
        """Stop the camera"""
        if not self.is_running and self.process is None:
            return

        print(f"[GstCamera] Stopping camera {self.device_index}...")
        self.is_running = False

        # Close stdout first to unblock read thread
        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except:
                pass

        # Wait for thread to exit
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.3)

        # Kill subprocess group - 먼저 SIGTERM으로 시도 (깔끔한 종료)
        if self.process:
            try:
                pgid = os.getpgid(self.process.pid)
                # 먼저 SIGTERM으로 종료 시도 (v4l2 장치 해제를 위해)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    # SIGTERM 실패시 SIGKILL
                    os.killpg(pgid, signal.SIGKILL)
                    self.process.wait(timeout=0.3)
            except:
                pass
            self.process = None
            self.thread = None
            self.latest_frame = None

        # 장치 해제 대기 (v4l2 장치가 완전히 해제되도록)
        time.sleep(0.3)

        print(f"[GstCamera] Camera {self.device_index} stopped")

    def release(self):
        """Release camera resources"""
        self.stop()


# Test code
if __name__ == "__main__":
    print("Testing GstCamera with subprocess...")

    cam = GstCamera(device_index=0, width=1920, height=1536, fps=30)

    if not cam.start():
        print("Failed to start camera!")
        exit(1)

    print("Camera started, reading frames...")

    for i in range(10):
        time.sleep(0.5)
        ret, frame = cam.read()
        if ret:
            print(f"Frame {i+1}: Shape={frame.shape}, Mean={frame.mean():.1f}")
        else:
            print(f"Frame {i+1}: No frame available")

    cam.stop()
    print("Test complete!")
