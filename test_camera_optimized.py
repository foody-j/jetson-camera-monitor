#!/usr/bin/env python3
"""
개선된 gst_camera.py 테스트 스크립트
- 메모리 사용량 모니터링
- FPS 측정
- 프레임 품질 확인
"""

import sys
import os
import time
import psutil
import numpy as np

# Jetson2 버전 테스트
sys.path.insert(0, '/home/yjk/jetson-food-ai/jetson2_frying_ai')
from gst_camera import GstCamera


def get_memory_usage():
    """현재 프로세스 메모리 사용량 (MB)"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def test_camera(device_index=0, duration_sec=30):
    """카메라 테스트 및 메모리/FPS 모니터링"""

    print(f"\n{'='*60}")
    print(f"카메라 테스트 시작: /dev/video{device_index}")
    print(f"테스트 시간: {duration_sec}초")
    print(f"{'='*60}\n")

    # 초기 메모리
    mem_start = get_memory_usage()
    print(f"시작 메모리: {mem_start:.1f} MB\n")

    # 카메라 시작
    cam = GstCamera(
        device_index=device_index,
        width=1920,
        height=1536,
        fps=30,
        # 출력 설정 (기본값: 960x768@10fps)
        output_width=960,
        output_height=768,
        output_fps=10
    )

    if not cam.start():
        print("❌ 카메라 시작 실패!")
        return False

    print(f"✅ 카메라 시작 성공\n")

    # 메모리/FPS 모니터링
    frame_count = 0
    fps_samples = []
    mem_samples = []

    start_time = time.time()
    last_fps_check = start_time
    fps_frame_count = 0

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed > duration_sec:
                break

            ret, frame = cam.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame_count += 1
            fps_frame_count += 1

            # FPS 측정 (1초마다)
            now = time.time()
            if now - last_fps_check >= 1.0:
                fps = fps_frame_count / (now - last_fps_check)
                fps_samples.append(fps)

                # 메모리 측정
                mem_now = get_memory_usage()
                mem_samples.append(mem_now)

                # 진행 상황 출력
                print(f"[{int(elapsed):3d}s] "
                      f"Frames: {frame_count:4d} | "
                      f"FPS: {fps:5.1f} | "
                      f"Memory: {mem_now:6.1f} MB | "
                      f"Shape: {frame.shape} | "
                      f"Mean: {frame.mean():6.1f}")

                last_fps_check = now
                fps_frame_count = 0

    except KeyboardInterrupt:
        print("\n\n중단됨 (Ctrl+C)")

    finally:
        cam.stop()

    # 최종 통계
    mem_end = get_memory_usage()

    print(f"\n{'='*60}")
    print(f"테스트 완료")
    print(f"{'='*60}")
    print(f"총 프레임:     {frame_count}")
    print(f"평균 FPS:      {np.mean(fps_samples):.2f} ± {np.std(fps_samples):.2f}")
    print(f"시작 메모리:   {mem_start:.1f} MB")
    print(f"종료 메모리:   {mem_end:.1f} MB")
    print(f"메모리 증가:   {mem_end - mem_start:+.1f} MB")
    print(f"평균 메모리:   {np.mean(mem_samples):.1f} MB")
    print(f"최대 메모리:   {np.max(mem_samples):.1f} MB")
    print(f"{'='*60}\n")

    # 메모리 누수 체크
    mem_growth = mem_end - mem_start
    if mem_growth > 50:  # 50MB 이상 증가
        print(f"⚠️  메모리 누수 의심: {mem_growth:+.1f} MB 증가")
        return False
    else:
        print(f"✅ 메모리 안정: {mem_growth:+.1f} MB 증가")
        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='개선된 카메라 테스트')
    parser.add_argument('--device', type=int, default=0, help='카메라 장치 번호 (기본: 0)')
    parser.add_argument('--duration', type=int, default=30, help='테스트 시간 (초, 기본: 30)')

    args = parser.parse_args()

    success = test_camera(device_index=args.device, duration_sec=args.duration)
    sys.exit(0 if success else 1)
