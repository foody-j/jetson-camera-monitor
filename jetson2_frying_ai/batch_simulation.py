#!/usr/bin/env python3
"""
GUI 없는 배치 시뮬레이션 스크립트
- 녹화된 세션 데이터로 튀김 AI + 탈탈 감지 테스트
- 가볍고 빠르게 여러 세션 테스트 가능
"""

import os
import sys
import glob
import json
import cv2
import time
import argparse
from pathlib import Path

# Import modules
from frying_segmenter import FoodSegmenter
from lift_event_tracker import LiftEventTracker


class BatchSimulator:
    """배치 시뮬레이션 처리기"""

    def __init__(self, config_path="config_jetson2.json"):
        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Initialize FoodSegmenter
        print("🔧 FoodSegmenter 초기화...")
        model_path = self.config.get('frying_seg_model', 'frying_seg.pt')
        self.segmenter = FoodSegmenter(
            model_path=model_path,
            mode="auto",
            device="cuda",
            imgsz=self.config.get('frying_seg_img_size', 640),
            conf=self.config.get('frying_seg_conf', 0.5)
        )
        print(f"   ✓ 모델: {model_path}, YOLO={self.segmenter.use_yolo}")

    def simulate_pot(self, session_dir, pot_name, camera_idx):
        """
        POT 시뮬레이션 실행

        Args:
            session_dir: 세션 디렉토리 (예: ~/AI_Data/FryingData/session_xxx)
            pot_name: POT1 또는 POT2
            camera_idx: 카메라 인덱스 (0 또는 1)
        """
        print("\n" + "=" * 80)
        print(f"🍳 {pot_name} 시뮬레이션 시작")
        print("=" * 80)

        # 이미지 경로
        camera_dir = os.path.join(session_dir, f"camera_{camera_idx}")
        if not os.path.exists(camera_dir):
            print(f"❌ 카메라 디렉토리 없음: {camera_dir}")
            return None

        image_files = sorted(glob.glob(os.path.join(camera_dir, "*.jpg")))
        if len(image_files) == 0:
            print(f"❌ 이미지 없음: {camera_dir}")
            return None

        print(f"📁 세션: {os.path.basename(session_dir)}")
        print(f"📸 이미지: {len(image_files)}장")

        # 세션 정보 로드
        session_info_path = os.path.join(session_dir, "session_info.json")
        food_type = "unknown"
        target_time = 180

        if os.path.exists(session_info_path):
            with open(session_info_path, 'r') as f:
                info = json.load(f)
                food_type = info.get('food_type', 'unknown')
                target_time = info.get('target_time', 180)
            print(f"🍔 음식: {food_type}, 목표시간: {target_time}초")

        # LiftEventTracker 초기화
        tracker = LiftEventTracker(pot_name, self.config)
        session_id = os.path.basename(session_dir)
        tracker.start_session(session_id, food_type, target_time)

        # 통계
        stats = {
            'total_frames': len(image_files),
            'processed_frames': 0,
            'lift_detected': 0,
            'food_visible': 0,
            'errors': 0,
            'start_time': time.time()
        }

        print(f"\n🚀 처리 시작...\n")

        # 프레임별 처리
        for i, img_path in enumerate(image_files, 1):
            # 이미지 로드
            image = cv2.imread(img_path)
            if image is None:
                stats['errors'] += 1
                continue

            # Segmentation
            try:
                seg_result = self.segmenter.segment(image, visualize=False)
                stats['processed_frames'] += 1
            except Exception as e:
                print(f"⚠ [{i}/{len(image_files)}] Segmentation 오류: {e}")
                stats['errors'] += 1
                continue

            # Lift tracking
            lift_status = tracker.process_frame(seg_result)

            # 결과 출력
            if lift_status['lift_detected']:
                stats['lift_detected'] += 1
                print(f"[{i:4d}/{len(image_files)}] 🟢 탈탈 #{lift_status['lift_count']} | "
                      f"시간={lift_status['running_time']:.1f}s, "
                      f"색변화={lift_status['color_delta']:.1f}, "
                      f"area={seg_result.food_area_ratio:.3f}")
            elif seg_result.food_area_ratio > 0.05:
                stats['food_visible'] += 1
                if i % 30 == 0:  # 30프레임마다 출력
                    print(f"[{i:4d}/{len(image_files)}] 🔵 튀김 보임 | area={seg_result.food_area_ratio:.3f}")

            # 완료 감지
            if lift_status['completion_detected']:
                print(f"\n{'=' * 80}")
                print(f"✅ 완료 감지! (프레임 {i}/{len(image_files)})")
                print(f"   탈탈: {lift_status['lift_count']}회")
                print(f"   시간: {lift_status['running_time']:.1f}s / {target_time}s")
                print(f"   색변화: {lift_status['color_delta']:.1f}")
                print(f"{'=' * 80}\n")

        # 세션 종료
        tracker.stop_session()

        # 결과 요약
        elapsed = time.time() - stats['start_time']
        print("\n" + "=" * 80)
        print("📊 시뮬레이션 결과")
        print("=" * 80)
        print(f"총 프레임: {stats['total_frames']}")
        print(f"처리 완료: {stats['processed_frames']} ({stats['processed_frames']/stats['total_frames']*100:.1f}%)")
        print(f"탈탈 감지: {stats['lift_detected']}회")
        print(f"튀김 보임: {stats['food_visible']}프레임")
        print(f"오류: {stats['errors']}")
        print(f"처리 시간: {elapsed:.1f}초 ({stats['processed_frames']/elapsed:.1f} fps)")
        print(f"완료 감지: {'✅ YES' if lift_status['completion_detected'] else '❌ NO'}")

        status = tracker.get_status()
        if status['active']:
            print(f"마지막 색상 변화: {status['last_color_delta']:.1f}")

        # 데이터 저장
        output_dir = os.path.join(session_dir, "batch_simulation_output")
        os.makedirs(output_dir, exist_ok=True)

        saved_path = tracker.save_session_data(output_dir)
        if saved_path:
            print(f"\n💾 저장 완료: {saved_path}")

            # 저장된 데이터 확인
            with open(saved_path, 'r') as f:
                saved_data = json.load(f)

            print(f"\n📋 저장된 탈탈 이벤트:")
            if saved_data['lift_events']:
                for i, event in enumerate(saved_data['lift_events'], 1):
                    print(f"   #{i}: 시간={event['running_time']:.1f}s, "
                          f"색변화={event['color_delta']:.1f}, "
                          f"brown={event['brown_ratio']:.2f}, "
                          f"golden={event['golden_ratio']:.2f}")
            else:
                print("   (탈탈 이벤트 없음)")

        print("=" * 80 + "\n")

        return stats


def main():
    parser = argparse.ArgumentParser(description="GUI 없는 배치 시뮬레이션")
    parser.add_argument("session_dir", help="세션 디렉토리 경로")
    parser.add_argument("--pot", choices=["pot1", "pot2", "both"], default="both",
                       help="POT 선택 (기본: both)")
    parser.add_argument("--config", default="config_jetson2.json",
                       help="설정 파일 경로")

    args = parser.parse_args()

    # 경로 확장
    session_dir = os.path.expanduser(args.session_dir)

    if not os.path.exists(session_dir):
        print(f"❌ 세션 디렉토리 없음: {session_dir}")
        return

    # 시뮬레이터 초기화
    simulator = BatchSimulator(args.config)

    # POT 시뮬레이션 실행
    if args.pot in ["pot1", "both"]:
        simulator.simulate_pot(session_dir, "POT1", camera_idx=0)

    if args.pot in ["pot2", "both"]:
        simulator.simulate_pot(session_dir, "POT2", camera_idx=1)


if __name__ == "__main__":
    # 기본 사용법 표시
    if len(sys.argv) == 1:
        print("=" * 80)
        print("🍳 GUI 없는 배치 시뮬레이션")
        print("=" * 80)
        print("\n사용법:")
        print("  python batch_simulation.py <session_dir> [--pot pot1|pot2|both]")
        print("\n예시:")
        print("  python batch_simulation.py ~/AI_Data/FryingData/session_20251217_141907")
        print("  python batch_simulation.py ~/AI_Data/FryingData/session_20251217_141907 --pot pot1")
        print("\n사용 가능한 세션:")

        data_dir = os.path.expanduser("~/AI_Data/FryingData")
        if os.path.exists(data_dir):
            sessions = sorted(glob.glob(os.path.join(data_dir, "session_*")))
            for session in sessions[-10:]:  # 최근 10개
                session_name = os.path.basename(session)
                cam0 = len(glob.glob(os.path.join(session, "camera_0", "*.jpg")))
                cam1 = len(glob.glob(os.path.join(session, "camera_1", "*.jpg")))
                print(f"  - {session_name}")
                print(f"      POT1 (camera_0): {cam0}장")
                print(f"      POT2 (camera_1): {cam1}장")
        else:
            print(f"  ❌ 데이터 디렉토리 없음: {data_dir}")

        print("\n" + "=" * 80)
    else:
        main()
