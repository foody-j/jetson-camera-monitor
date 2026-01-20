#!/usr/bin/env python3
"""
GStreamer Camera Wrapper for GMSL UYVY cameras
Direct GStreamer usage to avoid OpenCV format issues
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
import time

# Initialize GStreamer
Gst.init(None)


class GstCamera:
    """GStreamer-based camera capture for UYVY format"""

    def __init__(self, device_index, width=1920, height=1536, fps=30,
                 output_width=None, output_height=None, output_fps=None):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.device_path = f"/dev/video{device_index}"

        # 출력 해상도/FPS (기본값: 입력의 절반 해상도, 1/3 FPS)
        self.output_width = output_width if output_width else width // 2
        self.output_height = output_height if output_height else height // 2
        self.output_fps = output_fps if output_fps else max(10, fps // 3)

        self.pipeline = None
        self.mainloop = None

        # 더블버퍼: 고정 크기 배열 2개를 번갈아 쓰면서 할당 제거
        self.buffer_pool = [
            np.empty((self.output_height, self.output_width, 3), dtype=np.uint8),
            np.empty((self.output_height, self.output_width, 3), dtype=np.uint8)
        ]
        self.write_index = 0
        self.read_index = 0

        self.frame_lock = threading.Lock()
        self.is_running = False
        self.thread = None

        print(f"[GstCamera] Creating camera for {self.device_path}")
        print(f"  Input: {width}x{height}@{fps}fps → Output: {self.output_width}x{self.output_height}@{self.output_fps}fps")
        frame_size_before = width * height * 3 / 1024 / 1024
        frame_size_after = self.output_width * self.output_height * 3 / 1024 / 1024
        print(f"  Frame size: {frame_size_after:.2f} MB (was {frame_size_before:.2f} MB)")

    def start(self):
        """Start the GStreamer pipeline in a background thread"""
        if self.is_running:
            print(f"[GstCamera] Camera {self.device_index} already running")
            return True

        # Build GStreamer pipeline (개선: videorate + videoscale 추가)
        pipeline_str = (
            f"v4l2src device={self.device_path} ! "
            f"video/x-raw, format=UYVY, width={self.width}, height={self.height}, framerate={self.fps}/1 ! "
            f"videorate ! video/x-raw, framerate={self.output_fps}/1 ! "
            f"videoscale ! video/x-raw, width={self.output_width}, height={self.output_height} ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! "
            f"appsink name=sink emit-signals=true max-buffers=1 drop=true"
        )

        print(f"[GstCamera] Pipeline: {pipeline_str}")

        try:
            self.pipeline = Gst.parse_launch(pipeline_str)

            # Get the appsink element
            sink = self.pipeline.get_by_name('sink')
            if not sink:
                print(f"[ERROR] Failed to get appsink from pipeline")
                return False

            # Connect to new-sample signal
            sink.connect('new-sample', self._on_new_sample)

            # Start pipeline in background thread
            self.is_running = True
            self.thread = threading.Thread(target=self._run_pipeline, daemon=True)
            self.thread.start()

            # Wait a bit for pipeline to start
            time.sleep(0.5)

            print(f"[GstCamera] Camera {self.device_index} started successfully")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start camera {self.device_index}: {e}")
            return False

    def _run_pipeline(self):
        """Run GStreamer mainloop in background thread"""
        try:
            # Set pipeline to PLAYING state
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print(f"[ERROR] Failed to set pipeline to PLAYING state")
                self.is_running = False
                return

            # GMSL 초기화 타임아웃 체크 (5초)
            print(f"[GstCamera] Waiting for camera {self.device_index} to initialize...")
            ret = self.pipeline.get_state(timeout=5 * Gst.SECOND)
            if ret[0] == Gst.StateChangeReturn.FAILURE:
                print(f"[ERROR] Camera {self.device_index} initialization timeout (5s)")
                self.is_running = False
                return
            elif ret[0] == Gst.StateChangeReturn.ASYNC:
                print(f"[WARNING] Camera {self.device_index} still initializing...")

            print(f"[GstCamera] Pipeline for camera {self.device_index} is PLAYING")

            # Add bus watch for errors
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message', self._on_bus_message)

            # GLib MainLoop 사용 (CPU 효율적, busy-wait 제거)
            self.mainloop = GLib.MainLoop()
            print(f"[GstCamera] Starting GLib MainLoop for camera {self.device_index}")
            self.mainloop.run()  # 블로킹 방식이지만 이벤트 기반 (CPU 효율적)

        except Exception as e:
            print(f"[ERROR] Pipeline thread error for camera {self.device_index}: {e}")
        finally:
            self.is_running = False
            print(f"[GstCamera] Pipeline thread for camera {self.device_index} finished")

    def _on_bus_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[ERROR] GStreamer error on camera {self.device_index}: {err}, {debug}")
            # 데드락 방지: stop() 대신 플래그 설정 후 mainloop 종료
            self.is_running = False
            if self.mainloop and self.mainloop.is_running():
                self.mainloop.quit()
        elif t == Gst.MessageType.EOS:
            print(f"[INFO] End-of-stream on camera {self.device_index}")
            self.is_running = False
            if self.mainloop and self.mainloop.is_running():
                self.mainloop.quit()

    def _on_new_sample(self, sink):
        """Callback for new frame from appsink"""
        try:
            # Pull sample from appsink
            sample = sink.emit('pull-sample')
            if not sample:
                return Gst.FlowReturn.ERROR

            # Get buffer from sample
            buf = sample.get_buffer()
            caps = sample.get_caps()

            # Get frame dimensions from caps
            structure = caps.get_structure(0)
            width = structure.get_value('width')
            height = structure.get_value('height')

            # Extract buffer data
            success, map_info = buf.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.ERROR

            # Convert to numpy array (BGR format, 읽기 전용 뷰)
            frame_view = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            )

            # 다음 쓰기 버퍼에 복사 (덮어쓰기, 할당 없음)
            next_write_idx = (self.write_index + 1) % 2
            np.copyto(self.buffer_pool[next_write_idx], frame_view)

            with self.frame_lock:
                self.read_index = self.write_index
                self.write_index = next_write_idx

            buf.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            print(f"[ERROR] Error processing frame from camera {self.device_index}: {e}")
            return Gst.FlowReturn.ERROR

    def read(self):
        """
        Read the latest frame (제로카피: 참조만 반환, 소비자는 읽기 전용으로만 사용!)
        Returns: (success, frame) tuple
        """
        if not self.is_running:
            return False, None

        with self.frame_lock:
            # 더블버퍼에서 읽기용 프레임 참조 반환 (복사 없음!)
            # 주의: 소비자가 이 프레임을 수정하면 안 됨 (읽기 전용)
            return True, self.buffer_pool[self.read_index]

    def isOpened(self):
        """Check if camera is running"""
        return self.is_running

    def stop(self):
        """Stop the camera"""
        if not self.is_running:
            return

        print(f"[GstCamera] Stopping camera {self.device_index}...")
        self.is_running = False

        # Quit GLib MainLoop (이벤트 루프 종료)
        if self.mainloop and self.mainloop.is_running():
            print(f"[GstCamera] Quitting MainLoop for camera {self.device_index}")
            self.mainloop.quit()

        # Stop pipeline
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        # Wait for thread to finish (only if not called from the same thread)
        if self.thread and self.thread.is_alive():
            if threading.current_thread() != self.thread:
                self.thread.join(timeout=2.0)
            else:
                print(f"[GstCamera] Skipping join (called from same thread)")

        print(f"[GstCamera] Camera {self.device_index} stopped")

    def release(self):
        """Release camera resources"""
        self.stop()


# Test code
if __name__ == "__main__":
    print("Testing GstCamera with camera 0...")

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
            print(f"Frame {i+1}: No frame available yet")

    cam.stop()
    print("Test complete!")
