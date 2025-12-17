#!/usr/bin/env python3
"""
GStreamer Camera with Multiprocessing
각 카메라가 별도 프로세스에서 실행되어 GLib 충돌 방지
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Value
import numpy as np
import time
import ctypes


def camera_process(device_index, width, height, fps, frame_queue, running_flag, ready_flag):
    """
    별도 프로세스에서 실행되는 카메라 캡처 루프
    GStreamer 초기화가 이 프로세스 내에서만 이루어짐
    """
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib

    Gst.init(None)

    device_path = f"/dev/video{device_index}"
    print(f"[CameraProcess {device_index}] Starting for {device_path} @ {width}x{height}@{fps}fps")

    # GStreamer pipeline
    pipeline_str = (
        f"v4l2src device={device_path} io-mode=2 num-buffers=-1 ! "
        f"video/x-raw, format=UYVY, width={width}, height={height}, framerate={fps}/1 ! "
        f"queue max-size-buffers=2 leaky=downstream ! "
        f"videoconvert ! "
        f"video/x-raw, format=BGR ! "
        f"appsink name=sink emit-signals=false max-buffers=1 drop=true sync=false"
    )

    try:
        pipeline = Gst.parse_launch(pipeline_str)
        sink = pipeline.get_by_name('sink')

        if not sink:
            print(f"[CameraProcess {device_index}] ERROR: Failed to get appsink")
            return

        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print(f"[CameraProcess {device_index}] ERROR: Failed to start pipeline")
            return

        print(f"[CameraProcess {device_index}] Pipeline started")
        ready_flag.value = 1

        # 프레임 캡처 루프 (polling 방식)
        while running_flag.value:
            # Pull sample (blocking with timeout)
            sample = sink.emit('try-pull-sample', 100 * Gst.MSECOND)  # 100ms timeout

            if sample:
                buf = sample.get_buffer()
                caps = sample.get_caps()
                structure = caps.get_structure(0)
                w = structure.get_value('width')
                h = structure.get_value('height')

                success, map_info = buf.map(Gst.MapFlags.READ)
                if success:
                    # numpy array로 변환
                    frame = np.ndarray(
                        shape=(h, w, 3),
                        dtype=np.uint8,
                        buffer=map_info.data
                    ).copy()

                    buf.unmap(map_info)

                    # Queue에 전송 (non-blocking, 오래된 프레임 버림)
                    try:
                        # Queue가 가득 차면 오래된 것 제거
                        while not frame_queue.empty():
                            try:
                                frame_queue.get_nowait()
                            except:
                                break
                        frame_queue.put_nowait(frame)
                    except:
                        pass

            time.sleep(0.001)  # CPU 사용률 감소

        # Cleanup
        pipeline.set_state(Gst.State.NULL)
        print(f"[CameraProcess {device_index}] Stopped")

    except Exception as e:
        print(f"[CameraProcess {device_index}] ERROR: {e}")
        import traceback
        traceback.print_exc()


class GstCameraMP:
    """
    멀티프로세스 기반 GStreamer 카메라
    메인 프로세스의 GLib와 충돌하지 않음
    """

    def __init__(self, device_index, width=1920, height=1536, fps=30):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps

        self.process = None
        self.frame_queue = None
        self.running_flag = None
        self.ready_flag = None
        self.latest_frame = None

        print(f"[GstCameraMP] Creating camera {device_index} @ {width}x{height}")

    def start(self):
        """카메라 프로세스 시작"""
        if self.process and self.process.is_alive():
            print(f"[GstCameraMP] Camera {self.device_index} already running")
            return True

        # 프로세스 간 통신 설정
        self.frame_queue = Queue(maxsize=2)
        self.running_flag = Value(ctypes.c_int, 1)
        self.ready_flag = Value(ctypes.c_int, 0)

        # 카메라 프로세스 시작
        self.process = Process(
            target=camera_process,
            args=(
                self.device_index,
                self.width,
                self.height,
                self.fps,
                self.frame_queue,
                self.running_flag,
                self.ready_flag
            ),
            daemon=True
        )
        self.process.start()

        # 프로세스 준비 대기 (최대 5초)
        for _ in range(50):
            if self.ready_flag.value:
                print(f"[GstCameraMP] Camera {self.device_index} started successfully")
                return True
            time.sleep(0.1)

        print(f"[GstCameraMP] WARNING: Camera {self.device_index} startup timeout")
        return True  # 계속 시도

    def read(self):
        """
        최신 프레임 읽기
        Returns: (success, frame) tuple
        """
        if not self.process or not self.process.is_alive():
            return False, None

        # Queue에서 최신 프레임 가져오기
        try:
            while not self.frame_queue.empty():
                self.latest_frame = self.frame_queue.get_nowait()
        except:
            pass

        if self.latest_frame is not None:
            return True, self.latest_frame.copy()
        return False, None

    def isOpened(self):
        """카메라 실행 중인지 확인"""
        return self.process is not None and self.process.is_alive()

    def stop(self):
        """카메라 프로세스 중지"""
        if not self.process:
            return

        print(f"[GstCameraMP] Stopping camera {self.device_index}...")

        # 종료 신호
        if self.running_flag:
            self.running_flag.value = 0

        # 프로세스 종료 대기
        if self.process.is_alive():
            self.process.join(timeout=2.0)
            if self.process.is_alive():
                print(f"[GstCameraMP] Force killing camera {self.device_index}")
                self.process.terminate()
                self.process.join(timeout=1.0)

        # Queue 정리
        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    self.frame_queue.get_nowait()
            except:
                pass

        self.process = None
        self.latest_frame = None
        print(f"[GstCameraMP] Camera {self.device_index} stopped")

    def release(self):
        """리소스 해제"""
        self.stop()


# 테스트 코드
if __name__ == "__main__":
    print("=" * 60)
    print("Testing GstCameraMP with 4 cameras...")
    print("=" * 60)

    cameras = []
    for i in range(4):
        cam = GstCameraMP(device_index=i, width=1920, height=1536, fps=30)
        if cam.start():
            cameras.append(cam)
            print(f"Camera {i} started")
        time.sleep(1.0)  # 순차 시작

    print(f"\n{len(cameras)} cameras running, reading frames...")

    for iteration in range(10):
        time.sleep(0.5)
        print(f"\n--- Iteration {iteration + 1} ---")
        for i, cam in enumerate(cameras):
            ret, frame = cam.read()
            if ret:
                print(f"  Camera {i}: Shape={frame.shape}, Mean={frame.mean():.1f}")
            else:
                print(f"  Camera {i}: No frame")

    print("\nStopping cameras...")
    for cam in cameras:
        cam.stop()

    print("Test complete!")
