#!/usr/bin/env python3
"""
이미지 저장 프로세스 (멀티프로세싱)
JPEG 압축 및 파일 저장을 별도 프로세스에서 수행하여 GUI 프리징 방지
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Value
import ctypes
import os


def saver_process(save_queue, running_flag, jpeg_quality, save_width, save_height):
    """
    별도 프로세스에서 실행되는 이미지 저장 루프
    """
    import cv2
    import time

    print(f"[ImageSaver] Process started (JPEG Q={jpeg_quality}, {save_width}x{save_height})")
    saved_count = 0

    while running_flag.value:
        try:
            # Queue에서 저장 요청 가져오기 (100ms timeout)
            try:
                item = save_queue.get(timeout=0.1)
            except:
                continue

            if item is None:  # 종료 신호
                break

            save_path, frame = item

            # Resize and save
            frame_resized = cv2.resize(frame, (save_width, save_height), interpolation=cv2.INTER_LINEAR)
            cv2.imwrite(save_path, frame_resized, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])

            saved_count += 1
            if saved_count % 30 == 0:
                print(f"[ImageSaver] {saved_count}장 저장 완료")

        except Exception as e:
            print(f"[ImageSaver] ERROR: {e}")

    print(f"[ImageSaver] Process stopped (총 {saved_count}장 저장)")


class ImageSaverMP:
    """
    멀티프로세스 기반 이미지 저장기
    메인 프로세스의 GUI를 블로킹하지 않음
    """

    def __init__(self, jpeg_quality=100, save_width=1280, save_height=720):
        self.jpeg_quality = jpeg_quality
        self.save_width = save_width
        self.save_height = save_height

        self.process = None
        self.save_queue = None
        self.running_flag = None

        print(f"[ImageSaverMP] Created (JPEG Q={jpeg_quality}, {save_width}x{save_height})")

    def start(self):
        """저장 프로세스 시작"""
        if self.process and self.process.is_alive():
            print("[ImageSaverMP] Already running")
            return True

        self.save_queue = Queue(maxsize=100)  # 최대 100개 대기
        self.running_flag = Value(ctypes.c_int, 1)

        self.process = Process(
            target=saver_process,
            args=(
                self.save_queue,
                self.running_flag,
                self.jpeg_quality,
                self.save_width,
                self.save_height
            ),
            daemon=True
        )
        self.process.start()
        print("[ImageSaverMP] Process started")
        return True

    def save(self, save_path, frame):
        """
        이미지 저장 요청 (non-blocking)
        save_path: 저장 경로
        frame: numpy array (BGR)
        """
        if not self.process or not self.process.is_alive():
            return False

        try:
            # 디렉토리 생성 (메인 프로세스에서)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Queue에 저장 요청 추가 (non-blocking)
            self.save_queue.put_nowait((save_path, frame.copy()))
            return True
        except Exception as e:
            # Queue 가득 참 - 오래된 요청 버리고 새 요청 추가
            try:
                self.save_queue.get_nowait()
                self.save_queue.put_nowait((save_path, frame.copy()))
                return True
            except:
                print(f"[ImageSaverMP] Queue full, dropping frame")
                return False

    def get_queue_size(self):
        """대기 중인 저장 요청 수"""
        if self.save_queue:
            return self.save_queue.qsize()
        return 0

    def stop(self):
        """저장 프로세스 중지"""
        if not self.process:
            return

        print("[ImageSaverMP] Stopping...")

        # 종료 신호
        if self.running_flag:
            self.running_flag.value = 0

        # 종료 신호 전송
        try:
            self.save_queue.put_nowait(None)
        except:
            pass

        # 프로세스 종료 대기
        if self.process.is_alive():
            self.process.join(timeout=3.0)
            if self.process.is_alive():
                print("[ImageSaverMP] Force killing")
                self.process.terminate()
                self.process.join(timeout=1.0)

        self.process = None
        print("[ImageSaverMP] Stopped")


# 싱글톤 인스턴스
_saver_instance = None


def get_image_saver(jpeg_quality=100, save_width=1280, save_height=720):
    """싱글톤 이미지 저장기 가져오기"""
    global _saver_instance
    if _saver_instance is None:
        _saver_instance = ImageSaverMP(jpeg_quality, save_width, save_height)
        _saver_instance.start()
    return _saver_instance


def stop_image_saver():
    """이미지 저장기 중지"""
    global _saver_instance
    if _saver_instance:
        _saver_instance.stop()
        _saver_instance = None


# 테스트 코드
if __name__ == "__main__":
    import numpy as np
    import time

    print("=" * 60)
    print("Testing ImageSaverMP...")
    print("=" * 60)

    saver = ImageSaverMP(jpeg_quality=100, save_width=1280, save_height=720)
    saver.start()

    # 테스트 이미지 생성 및 저장
    test_dir = "/tmp/image_saver_test"
    os.makedirs(test_dir, exist_ok=True)

    for i in range(30):
        # 랜덤 이미지 생성 (1920x1536)
        frame = np.random.randint(0, 255, (1536, 1920, 3), dtype=np.uint8)
        save_path = os.path.join(test_dir, f"test_{i:03d}.jpg")
        saver.save(save_path, frame)
        print(f"Queued {i+1}/30, queue size: {saver.get_queue_size()}")
        time.sleep(0.1)

    print("\nWaiting for saves to complete...")
    time.sleep(3)

    print(f"Final queue size: {saver.get_queue_size()}")
    saver.stop()

    # 저장된 파일 확인
    saved_files = os.listdir(test_dir)
    print(f"Saved {len(saved_files)} files")

    print("Test complete!")
