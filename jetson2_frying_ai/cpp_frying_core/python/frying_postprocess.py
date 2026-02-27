#!/usr/bin/env python3
"""ctypes wrapper for frying postprocess C++ module."""

from __future__ import annotations

import ctypes
import os
from typing import Dict

import numpy as np


def _default_lib_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "build", "libfrying_postprocess.so")


class FryingPostprocessCpp:
    def __init__(self, lib_path: str | None = None):
        self.lib_path = lib_path or _default_lib_path()
        self._lib = ctypes.CDLL(self.lib_path)
        self._fn = self._lib.calc_frying_features
        self._fn.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
        ]
        self._fn.restype = ctypes.c_int

    def calc(self, hsv: np.ndarray, lab: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
        hsv_u8 = np.ascontiguousarray(hsv, dtype=np.uint8)
        lab_u8 = np.ascontiguousarray(lab, dtype=np.uint8)
        mask_u8 = np.ascontiguousarray(mask, dtype=np.uint8)

        if hsv_u8.ndim != 3 or hsv_u8.shape[2] != 3:
            raise ValueError("hsv must be HxWx3 uint8")
        if lab_u8.shape != hsv_u8.shape:
            raise ValueError("lab shape mismatch")
        if mask_u8.shape != hsv_u8.shape[:2]:
            raise ValueError("mask shape mismatch")

        h, w = hsv_u8.shape[:2]
        out = np.zeros((15,), dtype=np.float64)
        rc = self._fn(
            hsv_u8.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            lab_u8.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            mask_u8.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.c_int(h),
            ctypes.c_int(w),
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        )
        if rc != 0:
            raise RuntimeError(f"calc_frying_features failed rc={rc}")

        return {
            "food_area_ratio": float(out[0]),
            "mean_h": float(out[1]),
            "mean_s": float(out[2]),
            "mean_v": float(out[3]),
            "std_h": float(out[4]),
            "std_s": float(out[5]),
            "std_v": float(out[6]),
            "mean_l": float(out[7]),
            "mean_a": float(out[8]),
            "mean_b": float(out[9]),
            "dominant_hue": float(out[10]),
            "saturation_mean": float(out[11]),
            "value_mean": float(out[12]),
            "brown_ratio": float(out[13]),
            "golden_ratio": float(out[14]),
        }
