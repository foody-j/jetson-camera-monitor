#!/usr/bin/env python3
"""Visualize frames with most food detected"""

from pathlib import Path
import cv2
from frying_ai.food_segmentation import FoodSegmenter

# Get frames with most detection (from CSV analysis)
best_frames = ["t0023", "t0021", "t0022", "t0025", "t0020"]  # Highest food_area_ratio

session_dir = Path("frying_dataset/potato_20251027_141132")
images_dir = session_dir / "images"
output_dir = Path("frying_dataset/analysis_results/visualizations/best_frames")
output_dir.mkdir(exist_ok=True, parents=True)

segmenter = FoodSegmenter(mode="auto")

print("Generating visualizations for best frames...\n")

for frame_name in best_frames:
    img_path = images_dir / f"{frame_name}.jpg"
    if not img_path.exists():
        continue

    image = cv2.imread(str(img_path))
    save_path = output_dir / f"vis_{frame_name}.jpg"

    result = segmenter.segment(image, visualize=True, save_path=str(save_path))

    print(f"✅ {frame_name}: Food area={result.food_area_ratio:.2%}, "
          f"Brown={result.color_features.brown_ratio:.2%}, "
          f"Golden={result.color_features.golden_ratio:.2%}")

print(f"\n💾 All visualizations saved to: {output_dir}")
