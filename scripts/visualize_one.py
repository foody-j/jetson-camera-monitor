#!/usr/bin/env python3
"""Visualize one sample"""

from pathlib import Path
import cv2
from frying_ai.food_segmentation import FoodSegmenter

# Get first image from potato dataset
session_dir = Path("frying_dataset/potato_20251027_141132")
images_dir = session_dir / "images"
first_image = sorted(images_dir.glob("*.jpg"))[10]  # Use middle image

print(f"Analyzing: {first_image}")

image = cv2.imread(str(first_image))
segmenter = FoodSegmenter(mode="auto")
result = segmenter.segment(image, visualize=True)

print(f"\n✅ Results:")
print(f"   Food area: {result.food_area_ratio:.2%}")
print(f"   Brown ratio: {result.color_features.brown_ratio:.2%}")
print(f"   Golden ratio: {result.color_features.golden_ratio:.2%}")
print(f"   Mean HSV: H={result.color_features.mean_hsv[0]:.1f}° "
      f"S={result.color_features.mean_hsv[1]:.1f} V={result.color_features.mean_hsv[2]:.1f}")
