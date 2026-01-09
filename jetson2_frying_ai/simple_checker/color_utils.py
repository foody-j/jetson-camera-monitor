"""
Color utilities for simple color-based frying completion checker.
"""

from typing import Dict, Optional, Tuple

import cv2
import numpy as np


def extract_food_region(
    image_bgr: np.ndarray,
    hsv_lower: Tuple[int, int, int] = (8, 40, 80),
    hsv_upper: Tuple[int, int, int] = (30, 255, 255),
) -> Tuple[np.ndarray, np.ndarray]:
    """튀김 영역만 추출 (HSV 마스킹)."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array(hsv_lower, dtype=np.uint8)
    upper = np.array(hsv_upper, dtype=np.uint8)

    mask = cv2.inRange(hsv, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    return mask, hsv


def extract_color_stats(hsv_image: np.ndarray, mask: np.ndarray) -> Optional[Dict[str, float]]:
    """마스크 영역의 HSV 통계 추출."""
    h, s, v = cv2.split(hsv_image)
    h_values = h[mask > 0]
    s_values = s[mask > 0]
    v_values = v[mask > 0]

    if h_values.size == 0:
        return None

    return {
        "h_mean": float(np.mean(h_values)),
        "h_std": float(np.std(h_values)),
        "s_mean": float(np.mean(s_values)),
        "v_mean": float(np.mean(v_values)),
        "v_std": float(np.std(v_values)),
        "pixel_count": int(h_values.size),
    }


def calculate_color_distance(
    start_color: Dict[str, float],
    current_color: Dict[str, float],
) -> float:
    """가중 유클리드 거리 기반 색상 변화량."""
    delta_h = abs(current_color["h_mean"] - start_color["h_mean"])
    delta_s = abs(current_color["s_mean"] - start_color["s_mean"])
    delta_v = abs(current_color["v_mean"] - start_color["v_mean"])

    weights = {"h": 2.0, "s": 0.5, "v": 1.5}
    distance = (
        weights["h"] * delta_h +
        weights["s"] * delta_s +
        weights["v"] * delta_v
    )

    return float(distance)
