#!/usr/bin/env python3
"""Compare Python vs C++ observe postprocess helper."""

from __future__ import annotations

import argparse
import time
from typing import Dict, Optional

import numpy as np

from observe_postprocess import ObservePostprocessCpp


def py_select_inner_box(
    boxes_xyxy: np.ndarray,
    confs: np.ndarray,
    cls_ids: np.ndarray,
    names: Dict[int, str],
    cam_id: int,
    right_cam_id: int,
    right_min_ratio: float,
    frame_w: int,
    frame_h: int,
    bbox_pad: int,
    inner_margin: float,
) -> Optional[dict]:
    def clamp_int(v: float, lo: int, hi: int) -> int:
        return max(lo, min(hi, int(v)))

    def is_in_class(name: str) -> bool:
        lower = (name or "").lower()
        return lower == "in" or ("in" in lower)

    in_indices = [i for i in range(len(cls_ids)) if is_in_class(names.get(int(cls_ids[i]), ""))]
    if not in_indices:
        return None

    if cam_id == right_cam_id:
        right_ratio = max(0.0, min(1.0, float(right_min_ratio)))
        split_x = frame_w * right_ratio
        right_indices = [i for i in in_indices if ((boxes_xyxy[i][0] + boxes_xyxy[i][2]) * 0.5) >= split_x]
        if not right_indices:
            return None
        best_in = max(right_indices, key=lambda i: boxes_xyxy[i][0])
    else:
        best_in = max(in_indices, key=lambda i: confs[i])

    x1, y1, x2, y2 = boxes_xyxy[best_in]
    x1 = clamp_int(x1 - bbox_pad, 0, frame_w - 1)
    y1 = clamp_int(y1 - bbox_pad, 0, frame_h - 1)
    x2 = clamp_int(x2 + bbox_pad, 0, frame_w - 1)
    y2 = clamp_int(y2 + bbox_pad, 0, frame_h - 1)

    bw = x2 - x1
    bh = y2 - y1
    mx = int(bw * inner_margin)
    my = int(bh * inner_margin)
    ix1 = clamp_int(x1 + mx, 0, frame_w - 1)
    iy1 = clamp_int(y1 + my, 0, frame_h - 1)
    ix2 = clamp_int(x2 - mx, 0, frame_w - 1)
    iy2 = clamp_int(y2 - my, 0, frame_h - 1)
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    return {"bbox": (x1, y1, x2, y2), "inner_bbox": (ix1, iy1, ix2, iy2)}


def make_sample(rng: np.random.Generator, n: int, w: int, h: int):
    boxes = []
    confs = []
    cls_ids = []
    for _ in range(n):
        x1 = int(rng.integers(0, max(1, w - 20)))
        y1 = int(rng.integers(0, max(1, h - 20)))
        x2 = int(rng.integers(x1 + 1, min(w, x1 + 400)))
        y2 = int(rng.integers(y1 + 1, min(h, y1 + 300)))
        boxes.append((x1, y1, x2, y2))
        confs.append(float(rng.random()))
        cls_ids.append(int(rng.integers(0, 3)))
    return np.array(boxes, dtype=np.float32), np.array(confs, dtype=np.float32), np.array(cls_ids, dtype=np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--boxes", type=int, default=8)
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1536)
    ap.add_argument("--cam-id", type=int, default=3)
    ap.add_argument("--right-cam-id", type=int, default=3)
    ap.add_argument("--right-min-ratio", type=float, default=0.5)
    ap.add_argument("--bbox-pad", type=int, default=2)
    ap.add_argument("--inner-margin", type=float, default=0.30)
    args = ap.parse_args()

    rng = np.random.default_rng(42)
    names = {0: "in", 1: "out", 2: "other"}
    cpp = ObservePostprocessCpp()

    samples = [make_sample(rng, args.boxes, args.w, args.h) for _ in range(args.iters)]

    t0 = time.perf_counter()
    py_out = []
    for boxes, confs, cls_ids in samples:
        py_out.append(
            py_select_inner_box(
                boxes, confs, cls_ids, names,
                args.cam_id, args.right_cam_id, args.right_min_ratio,
                args.w, args.h, args.bbox_pad, args.inner_margin,
            )
        )
    t1 = time.perf_counter()

    cpp_out = []
    for boxes, confs, cls_ids in samples:
        cpp_out.append(
            cpp.select_inner_box(
                boxes, confs, cls_ids, names,
                args.cam_id, args.right_cam_id, args.right_min_ratio,
                args.w, args.h, args.bbox_pad, args.inner_margin,
            )
        )
    t2 = time.perf_counter()

    mismatch = sum(1 for a, b in zip(py_out, cpp_out) if a != b)
    py_ms = (t1 - t0) * 1000.0
    cpp_ms = (t2 - t1) * 1000.0
    speedup = py_ms / max(cpp_ms, 1e-9)

    print(f"iters={args.iters}, boxes={args.boxes}")
    print(f"python_time_ms={py_ms:.2f}")
    print(f"cpp_time_ms={cpp_ms:.2f}")
    print(f"speedup={speedup:.2f}x")
    print(f"mismatch={mismatch}")


if __name__ == "__main__":
    main()
