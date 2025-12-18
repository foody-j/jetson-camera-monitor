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

        self.process = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.is_running = False
        self.thread = None

        # BGR frame size
        self.frame_size = width * height * 3

        # 프레임 타임스탬프 (stale 감지용)
        self.last_frame_time = 0
        self.frame_timeout = 5.0  # 5초 동안 프레임 없으면 stale

        # 자동 재시작 설정
        self.auto_restart = True
        self.restart_count = 0
        self.max_restart_attempts = 3
        self.restart_lock = threading.Lock()
        self.restart_in_progress = False

        print(f"[GstCamera] Creating camera for {self.device_path} @ {width}x{height}")

    def start(self):
        """Start gst-launch subprocess"""
        if self.is_running:
            print(f"[GstCamera] Camera {self.device_index} already running")
            return True

        # GStreamer pipeline - output raw BGR to stdout
        gst_cmd = [
            "gst-launch-1.0", "-q",
            "v4l2src", f"device={self.device_path}", "io-mode=2", "!",
            f"video/x-raw,format=UYVY,width={self.width},height={self.height},framerate={self.fps}/1", "!",
            "videoconvert", "!",
            "video/x-raw,format=BGR", "!",
            "fdsink", "fd=1", "sync=false"
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

                    # Convert to numpy array
                    frame = np.frombuffer(frame_data, dtype=np.uint8).reshape(
                        (self.height, self.width, 3)
                    )

                    with self.frame_lock:
                        self.latest_frame = frame.copy()
                        self.last_frame_time = time.time()

        except Exception as e:
            if self.is_running:
                print(f"[ERROR] Frame read error camera {self.device_index}: {e}")
        finally:
            self.is_running = False
            # 자동 재시작 트리거
            if self.auto_restart:
                self._trigger_restart()

    def read(self):
        """Read the latest frame"""
        if not self.is_running:
            # 자동 재시작 시도
            if self.auto_restart and not self.restart_in_progress:
                self._trigger_restart()
            return False, None

        with self.frame_lock:
            if self.latest_frame is None:
                return False, None

            # Stale 프레임 체크
            if self.last_frame_time > 0:
                elapsed = time.time() - self.last_frame_time
                if elapsed > self.frame_timeout:
                    print(f"[WARN] Camera {self.device_index} frame stale ({elapsed:.1f}s)")
                    if self.auto_restart:
                        self._trigger_restart()
                    return False, None

            return True, self.latest_frame.copy()

    def isOpened(self):
        """Check if camera is running"""
        return self.is_running and self.process is not None

    def is_healthy(self):
        """카메라 상태 체크 - 프레임이 정상적으로 들어오는지"""
        if not self.is_running:
            return False
        if self.last_frame_time == 0:
            return False
        elapsed = time.time() - self.last_frame_time
        return elapsed < self.frame_timeout

    def _trigger_restart(self):
        """비동기 재시작 트리거"""
        with self.restart_lock:
            if self.restart_in_progress:
                return
            if self.restart_count >= self.max_restart_attempts:
                print(f"[ERROR] Camera {self.device_index} max restart attempts reached ({self.max_restart_attempts})")
                return
            self.restart_in_progress = True

        # 별도 스레드에서 재시작
        restart_thread = threading.Thread(target=self._do_restart, daemon=True)
        restart_thread.start()

    def _do_restart(self):
        """실제 재시작 수행"""
        try:
            self.restart_count += 1
            print(f"[GstCamera] Camera {self.device_index} auto-restart attempt {self.restart_count}/{self.max_restart_attempts}")

            # 정지
            self.auto_restart = False  # 재시작 중 추가 트리거 방지
            self.stop()
            time.sleep(1.0)  # 잠시 대기

            # 재시작
            self.auto_restart = True
            self.latest_frame = None
            self.last_frame_time = 0

            if self.start():
                print(f"[GstCamera] Camera {self.device_index} restart SUCCESS")
                self.restart_count = 0  # 성공하면 카운터 리셋
            else:
                print(f"[ERROR] Camera {self.device_index} restart FAILED")

        except Exception as e:
            print(f"[ERROR] Camera {self.device_index} restart error: {e}")
        finally:
            with self.restart_lock:
                self.restart_in_progress = False

    def reset_restart_count(self):
        """재시작 카운터 리셋 (외부에서 호출)"""
        self.restart_count = 0

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

        # Kill subprocess group
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=0.3)
            except:
                pass
            self.process = None

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
