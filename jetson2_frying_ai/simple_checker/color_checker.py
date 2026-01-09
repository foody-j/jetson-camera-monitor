"""
Simple color-based frying color difference checker.
"""

from typing import Dict, Optional

import numpy as np

from .color_utils import (
    extract_food_region,
    extract_color_stats,
    calculate_color_distance,
)


class SimpleColorChecker:
    """색상 변화량 계산기."""

    def __init__(self, color_threshold: float = 25.0):
        self.color_threshold = color_threshold
        self.reset()

    def reset(self):
        """새 세션 시작."""
        self.start_color: Optional[Dict[str, float]] = None

    def set_baseline(self, image: np.ndarray) -> Dict:
        """1차 탈탈: 기준 색상 저장."""
        mask, hsv = extract_food_region(image)
        self.start_color = extract_color_stats(hsv, mask)
        return {
            "baseline_set": self.start_color is not None,
            "color": self.start_color,
        }

    def measure(self, image: np.ndarray) -> Dict:
        """색상 변화량 측정."""
        if self.start_color is None:
            return {"error": "baseline_not_set"}

        mask, hsv = extract_food_region(image)
        current_color = extract_color_stats(hsv, mask)
        if current_color is None:
            return {"error": "food_region_not_found"}

        color_diff = calculate_color_distance(self.start_color, current_color)
        progress = min(color_diff / self.color_threshold, 1.0)

        return {
            "color_diff": round(color_diff, 2),
            "current_color": current_color,
            "progress_pct": round(progress * 100, 1),
        }
