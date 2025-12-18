#!/usr/bin/env python3
"""
GStreamer Camera with Multiprocessing (Improved)
각 카메라가 별도 프로세스에서 실행 - 죽여도 메인에 영향 없음
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Value
import numpy as np
import time
import ctypes
import signal
import os


def camera_process(device_index, width, height, fps, frame_queue, running_flag, ready_flag, error_flag):
    """
    별도 프로세스에서 실행되는 카메라 캡처 루프
    """
    # 시그널 무시 (부모가 죽여도 깔끔하게)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst

    Gst.init(None)

    device_path = f"/dev/video{device_index}"
    print(f"[CameraProcess {device_index}] Starting for {device_path} @ {width}x{height}@{fps}fps", flush=True)

    # GStreamer pipeline - 더 안정적인 설정
    pipeline_str = (
        f"v4l2src device={device_path} io-mode=2 ! "
        f"video/x-raw, format=UYVY, width={width}, height={height}, framerate={fps}/1 ! "
        f"queue max-size-buffers=1 leaky=downstream ! "
        f"videoconvert n-threads=2 ! "
        f"video/x-raw, format=BGR ! "
        f"appsink name=sink emit-signals=false max-buffers=1 drop=true sync=false"
    )

    pipeline = None
    try:
        pipeline = Gst.parse_launch(pipeline_str)
        sink = pipeline.get_by_name('sink')

        if not sink:
            print(f"[CameraProcess {device_index}] ERROR: Failed to get appsink", flush=True)
            error_flag.value = 1
            return

        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print(f"[CameraProcess {device_index}] ERROR: Failed to start pipeline", flush=True)
            error_flag.value = 1
            return

        # 실제로 프레임 받을 때까지 대기
        for _ in range(20):  # 2초 대기
            sample = sink.emit('try-pull-sample', 100 * Gst.MSECOND)
            if sample:
                print(f"[CameraProcess {device_index}] First frame received!", flush=True)
                ready_flag.value = 1
                break
            time.sleep(0.1)

        if not ready_flag.value:
            print(f"[CameraProcess {device_index}] WARNING: No frames yet, continuing anyway", flush=True)
            ready_flag.value = 1

        no_frame_count = 0

        # 프레임 캡처 루프
        while running_flag.value:
            sample = sink.emit('try-pull-sample', 200 * Gst.MSECOND)

            if sample:
                no_frame_count = 0
                buf = sample.get_buffer()
                caps = sample.get_caps()
                structure = caps.get_structure(0)
                w = structure.get_value('width')
                h = structure.get_value('height')

                success, map_info = buf.map(Gst.MapFlags.READ)
                if success:
                    frame = np.ndarray(
                        shape=(h, w, 3),
                        dtype=np.uint8,
                        buffer=map_info.data
                    ).copy()

                    buf.unmap(map_info)

                    # Queue에 전송
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
                # 5초간 프레임 없으면 에러 표시
                if no_frame_count > 25:
                    print(f"[CameraProcess {device_index}] WARNING: No frames for 5 seconds", flush=True)
                    no_frame_count = 0

    except Exception as e:
        print(f"[CameraProcess {device_index}] ERROR: {e}", flush=True)
        error_flag.value = 1
    finally:
        # 반드시 파이프라인 정리
        if pipeline:
            try:
                pipeline.set_state(Gst.State.NULL)
            except:
                pass
        print(f"[CameraProcess {device_index}] Exiting", flush=True)


class GstCameraMP:
    """
    멀티프로세스 기반 GStreamer 카메라
    프로세스 격리로 죽여도 메인 프로세스 안전
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
        self.error_flag = None
        self.latest_frame = None
        self._pid = None

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
        self.error_flag = Value(ctypes.c_int, 0)

        # 카메라 프로세스 시작 (daemon=False로 변경 - 더 안정적)
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
            daemon=False  # 명시적으로 종료 관리
        )
        self.process.start()
        self._pid = self.process.pid
        print(f"[GstCameraMP] Camera {self.device_index} process started (PID: {self._pid})")

        # 프로세스 준비 대기 (최대 5초)
        for _ in range(50):
            if self.ready_flag.value:
                print(f"[GstCameraMP] Camera {self.device_index} ready!")
                return True
            if self.error_flag.value:
                print(f"[GstCameraMP] Camera {self.device_index} failed to start")
                self._force_kill()
                return False
            time.sleep(0.1)

        print(f"[GstCameraMP] Camera {self.device_index} startup timeout")
        return False

    def read(self):
        """최신 프레임 읽기"""
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

    def _force_kill(self):
        """프로세스 강제 종료 (SIGKILL)"""
        if self._pid:
            try:
                os.kill(self._pid, signal.SIGKILL)
                print(f"[GstCameraMP] Sent SIGKILL to camera {self.device_index} (PID: {self._pid})")
            except ProcessLookupError:
                pass  # 이미 죽음
            except Exception as e:
                print(f"[GstCameraMP] Kill error: {e}")

    def stop(self):
        """카메라 프로세스 중지"""
        if not self.process:
            return

        print(f"[GstCameraMP] Stopping camera {self.device_index}...")

        # 1. 종료 신호 보내기
        if self.running_flag:
            self.running_flag.value = 0

        # 2. 잠깐 대기 (0.5초)
        if self.process.is_alive():
            self.process.join(timeout=0.5)

        # 3. 아직 살아있으면 SIGKILL
        if self.process.is_alive():
            print(f"[GstCameraMP] Force killing camera {self.device_index}")
            self._force_kill()
            time.sleep(0.1)

        # 4. Queue 정리
        if self.frame_queue:
            try:
                self.frame_queue.close()
                self.frame_queue.join_thread()
            except:
                pass

        self.process = None
        self._pid = None
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
        else:
            print(f"Camera {i} FAILED")
        time.sleep(1.0)

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
