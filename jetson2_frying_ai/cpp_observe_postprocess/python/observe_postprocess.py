#!/usr/bin/env python3
"""ctypes wrapper for observe_postprocess C++ helper."""

from __future__ import annotations

import ctypes
import os
from typing import Dict, Iterable, List, Optional, Sequence, Union

import numpy as np


def _resolve_default_lib() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "build", "libobserve_postprocess.so")


class ObservePostprocessCpp:
    def __init__(self, lib_path: Optional[str] = None):
        self.lib_path = lib_path or _resolve_default_lib()
        self._lib = ctypes.CDLL(self.lib_path)

        self._fn = self._lib.select_inner_box
        self._fn.argtypes = [
            ctypes.POINTER(ctypes.c_float),  # boxes
            ctypes.POINTER(ctypes.c_float),  # confs
            ctypes.POINTER(ctypes.c_int),    # cls_ids
            ctypes.c_int,                    # num_boxes
            ctypes.c_char_p,                 # class_names_csv
            ctypes.c_int,                    # cam_id
            ctypes.c_int,                    # right_cam_id
            ctypes.c_float,                  # right_min_ratio
            ctypes.c_int,                    # frame_w
            ctypes.c_int,                    # frame_h
            ctypes.c_int,                    # bbox_pad
            ctypes.c_float,                  # inner_margin
            ctypes.POINTER(ctypes.c_int),    # out_has_box
            ctypes.POINTER(ctypes.c_int),    # out_x1
            ctypes.POINTER(ctypes.c_int),    # out_y1
            ctypes.POINTER(ctypes.c_int),    # out_x2
            ctypes.POINTER(ctypes.c_int),    # out_y2
            ctypes.POINTER(ctypes.c_int),    # out_ix1
            ctypes.POINTER(ctypes.c_int),    # out_iy1
            ctypes.POINTER(ctypes.c_int),    # out_ix2
            ctypes.POINTER(ctypes.c_int),    # out_iy2
        ]
        self._fn.restype = ctypes.c_int

    @staticmethod
    def _class_names_csv(names: Union[Dict[int, str], Sequence[str], Iterable[str]]) -> str:
        if isinstance(names, dict):
            max_idx = max(names.keys()) if names else -1
            arr: List[str] = [""] * (max_idx + 1)
            for k, v in names.items():
                if k >= 0:
                    arr[k] = str(v)
        else:
            arr = [str(x) for x in names]
        return ",".join(arr)

    def select_inner_box(
        self,
        boxes_xyxy: np.ndarray,
        confs: np.ndarray,
        cls_ids: np.ndarray,
        names: Union[Dict[int, str], Sequence[str], Iterable[str]],
        cam_id: int,
        right_cam_id: int,
        right_min_ratio: float,
        frame_w: int,
        frame_h: int,
        bbox_pad: int,
        inner_margin: float,
    ) -> Optional[dict]:
        boxes = np.ascontiguousarray(boxes_xyxy, dtype=np.float32)
        cf = np.ascontiguousarray(confs, dtype=np.float32)
        cls = np.ascontiguousarray(cls_ids, dtype=np.int32)

        if boxes.ndim != 2 or boxes.shape[1] != 4:
            raise ValueError("boxes_xyxy must be shape (N, 4)")
        if cf.ndim != 1 or cls.ndim != 1:
            raise ValueError("confs and cls_ids must be shape (N,)")
        if not (boxes.shape[0] == cf.shape[0] == cls.shape[0]):
            raise ValueError("N mismatch among boxes/confs/cls_ids")

        out_has_box = ctypes.c_int(0)
        out_x1 = ctypes.c_int(0)
        out_y1 = ctypes.c_int(0)
        out_x2 = ctypes.c_int(0)
        out_y2 = ctypes.c_int(0)
        out_ix1 = ctypes.c_int(0)
        out_iy1 = ctypes.c_int(0)
        out_ix2 = ctypes.c_int(0)
        out_iy2 = ctypes.c_int(0)

        csv = self._class_names_csv(names).encode("utf-8")
        rc = self._fn(
            boxes.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            cf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            cls.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
            ctypes.c_int(boxes.shape[0]),
            ctypes.c_char_p(csv),
            ctypes.c_int(cam_id),
            ctypes.c_int(right_cam_id),
            ctypes.c_float(right_min_ratio),
            ctypes.c_int(frame_w),
            ctypes.c_int(frame_h),
            ctypes.c_int(bbox_pad),
            ctypes.c_float(inner_margin),
            ctypes.byref(out_has_box),
            ctypes.byref(out_x1),
            ctypes.byref(out_y1),
            ctypes.byref(out_x2),
            ctypes.byref(out_y2),
            ctypes.byref(out_ix1),
            ctypes.byref(out_iy1),
            ctypes.byref(out_ix2),
            ctypes.byref(out_iy2),
        )

        if rc != 0:
            raise RuntimeError(f"select_inner_box failed rc={rc}")
        if out_has_box.value == 0:
            return None
        return {
            "bbox": (out_x1.value, out_y1.value, out_x2.value, out_y2.value),
            "inner_bbox": (out_ix1.value, out_iy1.value, out_ix2.value, out_iy2.value),
        }
