#!/usr/bin/env python3
"""ctypes wrapper for lift tracker C++ core."""

from __future__ import annotations

import ctypes
import os


def _default_lib_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "build", "liblift_tracker_core.so")


class LiftTrackerCoreCpp:
    def __init__(self, lib_path: str | None = None):
        self.lib_path = lib_path or _default_lib_path()
        self._lib = ctypes.CDLL(self.lib_path)
        self._calc_color_delta = self._lib.calc_color_delta
        self._calc_color_delta.argtypes = [ctypes.c_double] * 6
        self._calc_color_delta.restype = ctypes.c_double

        self._check_completion_ready = self._lib.check_completion_ready
        self._check_completion_ready.argtypes = [ctypes.c_double] * 5
        self._check_completion_ready.restype = ctypes.c_int

    def calc_color_delta(self, base_h: float, base_s: float, base_v: float, cur_h: float, cur_s: float, cur_v: float) -> float:
        return float(self._calc_color_delta(base_h, base_s, base_v, cur_h, cur_s, cur_v))

    def check_completion_ready(
        self,
        running_time: float,
        target_time: float,
        early_sec: float,
        color_delta: float,
        color_threshold: float,
    ) -> bool:
        return bool(self._check_completion_ready(running_time, target_time, early_sec, color_delta, color_threshold))
