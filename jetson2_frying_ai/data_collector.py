#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터 수집 도구 - Jetson #2 AI 모니터링
4개 카메라에서 이미지 캡처 (튀김 AI / 바켓 감지 데이터 수집용)
"""

import cv2
import os
import sys
import json
from datetime import datetime
import argparse
from gst_camera import GstCamera

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# =========================
# Load Configuration
# =========================
def load_config(config_path="config_jetson2.json"):
    """Load configuration from JSON file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()

# Camera settings
CAMERA_WIDTH = config.get('camera_width', 1280)
CAMERA_HEIGHT = config.get('camera_height', 720)
CAMERA_FPS = config.get('camera_fps', 30)

# Camera indices
CAMERAS = {
    'frying_left': config.get('frying_left_camera_index', 0),
    'frying_right': config.get('frying_right_camera_index', 1),
    'observe_left': config.get('observe_left_camera_index', 2),
    'observe_right': config.get('observe_right_camera_index', 3)
}

# =========================
# Data Collector Class
# =========================
class DataCollector:
    def __init__(self, camera_indices, output_dir, auto_mode=False, interval=5):
        """
        데이터 수집기 초기화

        Args:
            camera_indices: 사용할 카메라 인덱스 리스트 [0, 1, 2, 3]
            output_dir: 저장할 디렉토리
            auto_mode: 자동 캡처 모드 (True/False)
            interval: 자동 캡처 간격 (초)
        """
        self.camera_indices = camera_indices
        self.output_dir = output_dir
        self.auto_mode = auto_mode
        self.interval = interval

        # 저장 디렉토리 생성
        self.create_directories()

        # 카메라 초기화
        self.cameras = {}
        self.init_cameras()

        # 통계
        self.total_saved = 0
        self.auto_running = False

    def create_directories(self):
        """저장 디렉토리 생성"""
        os.makedirs(self.output_dir, exist_ok=True)

        # 카메라별 디렉토리
        for idx in self.camera_indices:
            cam_dir = os.path.join(self.output_dir, f"camera_{idx}")
            os.makedirs(cam_dir, exist_ok=True)
            print(f"[디렉토리] {cam_dir} 생성 완료")

    def init_cameras(self):
        """카메라 초기화"""
        print("\n[카메라 초기화]")
        for idx in self.camera_indices:
            try:
                cap = GstCamera(
                    device_index=idx,
                    width=CAMERA_WIDTH,
                    height=CAMERA_HEIGHT,
                    fps=CAMERA_FPS
                )
                cap.start()
                self.cameras[idx] = cap
                print(f"  ✓ 카메라 {idx} 초기화 완료")
            except Exception as e:
                print(f"  ✗ 카메라 {idx} 초기화 실패: {e}")

        if not self.cameras:
            print("\n❌ 사용 가능한 카메라가 없습니다!")
            sys.exit(1)

    def capture_all(self):
        """모든 카메라에서 이미지 캡처 및 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_count = 0

        for idx, cap in self.cameras.items():
            ret, frame = cap.read()
            if ret:
                # 파일명 생성
                filename = f"cam{idx}_{timestamp}.jpg"
                filepath = os.path.join(self.output_dir, f"camera_{idx}", filename)

                # 저장
                cv2.imwrite(filepath, frame)
                saved_count += 1
                print(f"  ✓ 저장: {filepath}")
            else:
                print(f"  ✗ 카메라 {idx} 읽기 실패")

        self.total_saved += saved_count
        return saved_count

    def run_manual(self):
        """수동 캡처 모드"""
        print("\n" + "="*60)
        print("📸 수동 캡처 모드")
        print("="*60)
        print("키 조작:")
        print("  스페이스바: 캡처")
        print("  'a': 자동 캡처 시작/중지")
        print("  'q': 종료")
        print("="*60 + "\n")

        import time
        last_auto_capture = time.time()

        while True:
            # 프레임 표시 (첫 번째 카메라만)
            first_cam_idx = list(self.cameras.keys())[0]
            ret, frame = self.cameras[first_cam_idx].read()

            if ret:
                # 리사이즈해서 표시
                display_frame = cv2.resize(frame, (640, 480))

                # 상태 표시
                status_text = f"카메라: {len(self.cameras)}개 | 저장: {self.total_saved}개"
                if self.auto_running:
                    status_text += f" | 자동 캡처 중 ({self.interval}초 간격)"

                cv2.putText(display_frame, status_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                cv2.imshow("Data Collector (Camera 0)", display_frame)

            # 자동 캡처
            if self.auto_running:
                current_time = time.time()
                if current_time - last_auto_capture >= self.interval:
                    print(f"\n[자동 캡처] {datetime.now().strftime('%H:%M:%S')}")
                    self.capture_all()
                    last_auto_capture = current_time

            # 키 입력
            key = cv2.waitKey(100) & 0xFF

            if key == ord(' '):  # 스페이스바
                print(f"\n[수동 캡처] {datetime.now().strftime('%H:%M:%S')}")
                self.capture_all()

            elif key == ord('a'):  # 자동 캡처 토글
                self.auto_running = not self.auto_running
                if self.auto_running:
                    print(f"\n✅ 자동 캡처 시작 ({self.interval}초 간격)")
                    last_auto_capture = time.time()
                else:
                    print("\n⏸ 자동 캡처 중지")

            elif key == ord('q'):  # 종료
                break

        cv2.destroyAllWindows()

    def run_auto(self):
        """자동 캡처 모드 (헤드리스)"""
        print("\n" + "="*60)
        print("📸 자동 캡처 모드 (헤드리스)")
        print("="*60)
        print(f"간격: {self.interval}초")
        print("종료: Ctrl+C")
        print("="*60 + "\n")

        import time
        try:
            while True:
                print(f"\n[캡처] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                saved = self.capture_all()
                print(f"  → {saved}개 파일 저장 완료 (총 {self.total_saved}개)")

                # 대기
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\n⏹ 자동 캡처 중지됨")

    def cleanup(self):
        """카메라 정리"""
        print("\n[정리] 카메라 종료 중...")
        for idx, cap in self.cameras.items():
            cap.stop()
            print(f"  ✓ 카메라 {idx} 종료")

        print(f"\n✅ 총 {self.total_saved}개 이미지 저장 완료!")
        print(f"📁 저장 위치: {self.output_dir}")

# =========================
# Main
# =========================
def main():
    parser = argparse.ArgumentParser(description="Jetson #2 데이터 수집 도구")

    parser.add_argument('--cameras', type=str, default='0,1,2,3',
                       help='사용할 카메라 인덱스 (쉼표로 구분, 예: 0,1 또는 2,3)')

    parser.add_argument('--output', type=str, default='./data',
                       help='저장 디렉토리 경로')

    parser.add_argument('--mode', type=str, choices=['manual', 'auto'], default='manual',
                       help='캡처 모드: manual (수동) 또는 auto (자동)')

    parser.add_argument('--interval', type=int, default=5,
                       help='자동 캡처 간격 (초)')

    args = parser.parse_args()

    # 카메라 인덱스 파싱
    camera_indices = [int(x.strip()) for x in args.cameras.split(',')]

    print("="*60)
    print("📸 Jetson #2 데이터 수집 도구")
    print("="*60)
    print(f"카메라: {camera_indices}")
    print(f"출력 디렉토리: {args.output}")
    print(f"모드: {args.mode}")
    if args.mode == 'auto':
        print(f"간격: {args.interval}초")
    print("="*60)

    # 데이터 수집기 생성
    collector = DataCollector(
        camera_indices=camera_indices,
        output_dir=args.output,
        auto_mode=(args.mode == 'auto'),
        interval=args.interval
    )

    try:
        if args.mode == 'manual':
            collector.run_manual()
        else:
            collector.run_auto()

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        collector.cleanup()

if __name__ == "__main__":
    main()
