#!/usr/bin/env python3
"""
Demo for color-based frying completion checker.
"""

import argparse
import re
from pathlib import Path
from typing import List, Optional, Tuple

import cv2

from src.data.lift_detector import LiftDetector
from src.simple_checker.color_checker import SimpleColorChecker


def _parse_time_from_filename(name: str) -> Optional[float]:
    """Parse timestamp from filename like camera_0_HHMMSS_mmm.jpg"""
    match = re.search(r"_(\d{6})_(\d{3})\.jpg$", name)
    if not match:
        return None
    hhmmss = match.group(1)
    millis = match.group(2)
    h = int(hhmmss[0:2])
    m = int(hhmmss[2:4])
    s = int(hhmmss[4:6])
    ms = int(millis)
    return h * 3600 + m * 60 + s + ms / 1000.0


def _load_images(image_paths: List[Path]) -> List[Tuple[Path, float]]:
    result = []
    first_ts = None
    for idx, path in enumerate(image_paths):
        ts = _parse_time_from_filename(path.name)
        if ts is None:
            ts = float(idx * 5)
        if first_ts is None:
            first_ts = ts
        result.append((path, ts - first_ts))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Color-based frying checker demo")
    parser.add_argument("--session", type=str, required=True, help="Session dir (food_type dir)")
    parser.add_argument("--camera_dir", type=str, default="camera_0")
    parser.add_argument("--use_lift_sequence", action="store_true")
    parser.add_argument("--max_frames", type=int, default=None)
    parser.add_argument("--color_threshold", type=float, default=25.0)
    args = parser.parse_args()

    session_dir = Path(args.session)
    image_dir = session_dir / args.camera_dir
    if image_dir.is_dir():
        image_paths = sorted(image_dir.glob("*.jpg"))
    else:
        image_paths = sorted(session_dir.glob("*.jpg"))

    if args.use_lift_sequence:
        detector = LiftDetector()
        lift_sequence = detector.get_lift_sequence([str(p) for p in image_paths])
        image_paths = [Path(p) for _, p in lift_sequence]

    if args.max_frames is not None:
        image_paths = image_paths[: args.max_frames]

    if not image_paths:
        raise SystemExit("No images found for demo")

    checker = SimpleColorChecker(color_threshold=args.color_threshold)

    print("=== 색상 기반 튀김 완료 판단 테스트 ===")
    print(f"Color threshold: {checker.color_threshold}")

    timeline = _load_images(image_paths)
    for idx, (path, ts) in enumerate(timeline, start=1):
        image = cv2.imread(str(path))
        if image is None:
            print(f"Skip: {path.name} (load failed)")
            continue

        if idx == 1:
            baseline = checker.set_baseline(image)
            color = baseline.get("color")
            if color:
                print(f"[{idx}차 탈탈] {path.name}")
                print("  기준 색상 저장")
                print(
                    f"  기준 색상: H={color['h_mean']:.1f}, "
                    f"S={color['s_mean']:.1f}, V={color['v_mean']:.1f}"
                )
            else:
                print(f"[{idx}차 탈탈] {path.name} (baseline 실패)")
            continue

        result = checker.measure(image)
        if "error" in result:
            print(f"[{idx}차 탈탈] {path.name} (error: {result['error']})")
            continue

        print(f"[{idx}차 탈탈] {path.name}")
        print(f"  색상 변화: {result['color_diff']}")
        print(f"  진행률: {result['progress_pct']}%")


if __name__ == "__main__":
    main()
