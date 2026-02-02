#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual frame-by-frame inference viewer for frying segmentation.
- Keyboard: n/right = next, p/left = prev, q/esc = quit
"""

import os
import json
import argparse
from pathlib import Path

import cv2

from frying_segmenter import FoodSegmenter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(config_path: str):
    config_full = config_path
    if not os.path.isabs(config_full):
        config_full = os.path.join(SCRIPT_DIR, config_path)
    with open(config_full, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_model_path(path_str: str) -> str:
    if os.path.isabs(path_str):
        return path_str
    return os.path.join(SCRIPT_DIR, path_str)


def list_images(folder: str, recursive: bool = True):
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    files = []
    root = Path(folder)
    if recursive:
        iterator = root.rglob("*")
    else:
        iterator = root.iterdir()
    for p in sorted(iterator):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(str(p))
    return files


def overlay_mask(image, mask, alpha=0.4, color=(0, 255, 0)):
    if mask is None:
        return image
    overlay = image.copy()
    colored = image.copy()
    colored[mask > 0] = color
    return cv2.addWeighted(colored, alpha, overlay, 1 - alpha, 0)


def main():
    parser = argparse.ArgumentParser(description="Manual frame-by-frame inference viewer")
    parser.add_argument("folder", help="Image folder path")
    parser.add_argument("--config", default="config_jetson2.json", help="Config JSON path")
    args = parser.parse_args()

    config = load_config(args.config)

    model_path = resolve_model_path(config.get("frying_seg_model", "frying_seg.pt"))
    imgsz = config.get("frying_seg_imgsz", 640)
    conf = config.get("frying_seg_conf", 0.2)
    mask_thresh = config.get("frying_seg_mask_thresh", 0.3)

    segmenter = FoodSegmenter(
        model_path=model_path,
        mode="auto",
        device="cuda",
        imgsz=imgsz,
        conf=conf,
        mask_threshold=mask_thresh,
    )

    files = list_images(args.folder, recursive=True)
    if not files:
        raise SystemExit(f"No images found in: {args.folder}")

    idx = 0
    window = "Manual Inference"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    while True:
        path = files[idx]
        image = cv2.imread(path)
        if image is None:
            print(f"[WARN] Failed to read: {path}")
            idx = min(idx + 1, len(files) - 1)
            continue

        result = segmenter.segment(image)
        vis = overlay_mask(image, result.food_mask)

        text = f"{idx+1}/{len(files)}  {os.path.basename(path)}"
        cv2.putText(vis, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        if segmenter.last_yolo_stats:
            stats = segmenter.last_yolo_stats
            stat_text = f"masks={stats.get('num_masks', 0)} max_conf={stats.get('max_conf', 0.0):.2f}"
            cv2.putText(vis, stat_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        cv2.imshow(window, vis)
        key = cv2.waitKey(0) & 0xFF

        if key in (ord("q"), 27):
            break
        if key in (ord("n"), ord("d"), 83):  # next or right arrow
            idx = min(idx + 1, len(files) - 1)
        elif key in (ord("p"), ord("a"), 81):  # prev or left arrow
            idx = max(idx - 1, 0)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
