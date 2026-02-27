#!/usr/bin/env python3
"""ctypes wrapper for observe overlay/jpeg C++ helper."""

from __future__ import annotations

import ctypes
import os

import numpy as np


def _resolve_default_lib() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "build", "libobserve_overlay.so")


class ObserveOverlayCpp:
    def __init__(self, lib_path: str | None = None):
        self.lib_path = lib_path or _resolve_default_lib()
        self._lib = ctypes.CDLL(self.lib_path)
        self._fn = self._lib.build_overlay_jpeg
        self._fn.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._fn.restype = ctypes.c_int

    def build_jpeg(self, frame_bgr: np.ndarray, mask: np.ndarray, target_w: int, jpeg_quality: int) -> bytes | None:
        frame = np.ascontiguousarray(frame_bgr, dtype=np.uint8)
        mask_u8 = np.ascontiguousarray(mask, dtype=np.uint8)
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must be HxWx3 uint8")
        if mask_u8.shape != frame.shape[:2]:
            raise ValueError("mask shape mismatch")

        src_h, src_w = frame.shape[:2]
        out_capacity = max(1, src_h * src_w * 3)
        out_buf = np.empty((out_capacity,), dtype=np.uint8)
        out_size = ctypes.c_int(0)

        rc = self._fn(
            frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            mask_u8.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.c_int(src_h),
            ctypes.c_int(src_w),
            ctypes.c_int(target_w),
            ctypes.c_int(jpeg_quality),
            out_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            ctypes.c_int(out_capacity),
            ctypes.byref(out_size),
        )
        if rc < 0:
            raise RuntimeError(f"build_overlay_jpeg failed rc={rc}")
        if rc == 0 or out_size.value <= 0:
            return None
        return out_buf[: out_size.value].tobytes()
