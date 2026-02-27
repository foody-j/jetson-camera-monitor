#!/usr/bin/env python3
"""Benchmark Python vs C++ frying postprocess on HSV/LAB+mask stats."""

from __future__ import annotations

import argparse
import time

import cv2
import numpy as np

from frying_postprocess import FryingPostprocessCpp


def py_calc(hsv: np.ndarray, lab: np.ndarray, mask: np.ndarray):
    food_pixels_hsv = hsv[mask > 0]
    food_pixels_lab = lab[mask > 0]
    if len(food_pixels_hsv) == 0:
        return {
            "food_area_ratio": 0.0,
            "mean_h": 0.0,
            "mean_s": 0.0,
            "mean_v": 0.0,
            "std_h": 0.0,
            "std_s": 0.0,
            "std_v": 0.0,
            "mean_l": 0.0,
            "mean_a": 0.0,
            "mean_b": 0.0,
            "dominant_hue": 0.0,
            "saturation_mean": 0.0,
            "value_mean": 0.0,
            "brown_ratio": 0.0,
            "golden_ratio": 0.0,
        }
    mean_hsv = np.mean(food_pixels_hsv, axis=0)
    std_hsv = np.std(food_pixels_hsv, axis=0)
    mean_lab = np.mean(food_pixels_lab, axis=0)
    hue_hist = cv2.calcHist([hsv], [0], mask, [180], [0, 180])
    dominant_hue = float(np.argmax(hue_hist))
    sat = float(np.mean(food_pixels_hsv[:, 1]))
    val = float(np.mean(food_pixels_hsv[:, 2]))
    brown = float(np.sum((food_pixels_hsv[:, 0] >= 5) & (food_pixels_hsv[:, 0] <= 25)) / len(food_pixels_hsv))
    golden = float(np.sum((food_pixels_hsv[:, 0] >= 15) & (food_pixels_hsv[:, 0] <= 35)) / len(food_pixels_hsv))
    area = float(np.sum(mask > 0) / (mask.shape[0] * mask.shape[1]))
    return {
        "food_area_ratio": area,
        "mean_h": float(mean_hsv[0]),
        "mean_s": float(mean_hsv[1]),
        "mean_v": float(mean_hsv[2]),
        "std_h": float(std_hsv[0]),
        "std_s": float(std_hsv[1]),
        "std_v": float(std_hsv[2]),
        "mean_l": float(mean_lab[0]),
        "mean_a": float(mean_lab[1]),
        "mean_b": float(mean_lab[2]),
        "dominant_hue": dominant_hue,
        "saturation_mean": sat,
        "value_mean": val,
        "brown_ratio": brown,
        "golden_ratio": golden,
    }


def make_sample(rng: np.random.Generator, h: int, w: int):
    img = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    mask = (rng.random((h, w)) > 0.7).astype(np.uint8) * 255
    return hsv, lab, mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=1000)
    ap.add_argument("--h", type=int, default=448)
    ap.add_argument("--w", type=int, default=640)
    args = ap.parse_args()

    rng = np.random.default_rng(123)
    samples = [make_sample(rng, args.h, args.w) for _ in range(args.iters)]
    cpp = FryingPostprocessCpp()

    t0 = time.perf_counter()
    py_out = [py_calc(hsv, lab, mask) for hsv, lab, mask in samples]
    t1 = time.perf_counter()
    cpp_out = [cpp.calc(hsv, lab, mask) for hsv, lab, mask in samples]
    t2 = time.perf_counter()

    keys = ["food_area_ratio", "brown_ratio", "golden_ratio", "dominant_hue"]
    mismatch = 0
    for a, b in zip(py_out, cpp_out):
        for k in keys:
            if abs(a[k] - b[k]) > 1e-6:
                mismatch += 1
                break

    py_ms = (t1 - t0) * 1000.0
    cpp_ms = (t2 - t1) * 1000.0
    speedup = py_ms / max(cpp_ms, 1e-9)
    print(f"iters={args.iters}, shape={args.h}x{args.w}")
    print(f"python_time_ms={py_ms:.2f}")
    print(f"cpp_time_ms={cpp_ms:.2f}")
    print(f"speedup={speedup:.2f}x")
    print(f"mismatch={mismatch}")


if __name__ == "__main__":
    main()
