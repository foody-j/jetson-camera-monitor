#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


RUN_RE = re.compile(r"^(\d{8}_\d{6})_UID([0-9A-Fa-f]+)_vibration\.csv$")


def resample_1d(arr: np.ndarray, seq_len: int) -> np.ndarray:
    if arr.size == 0:
        return np.zeros(seq_len, dtype=np.float32)
    if arr.size == seq_len:
        return arr.astype(np.float32)
    x_old = np.linspace(0.0, 1.0, num=arr.size, endpoint=True)
    x_new = np.linspace(0.0, 1.0, num=seq_len, endpoint=True)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def collect_runs(folder: Path) -> Dict[str, Dict[str, Path]]:
    grouped: Dict[str, Dict[str, Path]] = {}
    for path in sorted(folder.glob("*.csv")):
        m = RUN_RE.match(path.name)
        if not m:
            continue
        ts, uid = m.group(1), m.group(2).upper()
        grouped.setdefault(ts, {})[uid] = path
    return grouped


def build_sample(
    run_files: Dict[str, Path],
    uid_list: List[str],
    seq_len: int,
    feature_cols: List[str],
) -> np.ndarray:
    channels = []
    for uid in uid_list:
        csv_path = run_files.get(uid)
        if csv_path is None:
            for _ in feature_cols:
                channels.append(np.zeros(seq_len, dtype=np.float32))
            continue
        df = pd.read_csv(csv_path)
        for col in feature_cols:
            if col not in df.columns:
                channels.append(np.zeros(seq_len, dtype=np.float32))
                continue
            series = pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
            series = np.abs(series)
            channels.append(resample_1d(series, seq_len))
    return np.stack(channels, axis=0).astype(np.float32)


class SmallVibrationCNN(nn.Module):
    def __init__(self, in_ch: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(in_ch, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(2),
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(128, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.net(x).squeeze(-1)
        return self.head(x).squeeze(-1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Infer vibration run labels with trained 1D CNN")
    ap.add_argument("--model", required=True, help="Path to .pt file from train_vibration_cnn.py")
    ap.add_argument("--input-dir", required=True, help="Folder containing run CSVs")
    ap.add_argument("--run-ts", default="", help="Optional run timestamp filter (e.g., 20260225_182130)")
    ap.add_argument("--out-json", default="", help="Optional output JSON path")
    args = ap.parse_args()

    ckpt = torch.load(args.model, map_location="cpu", weights_only=False)
    uid_list = ckpt["uid_list"]
    feature_cols = ckpt["feature_cols"]
    seq_len = int(ckpt["seq_len"])
    threshold = float(ckpt.get("threshold", 0.5))
    mean = np.asarray(ckpt["mean"], dtype=np.float32)
    std = np.asarray(ckpt["std"], dtype=np.float32)
    std[std < 1e-6] = 1.0

    model = SmallVibrationCNN(in_ch=len(uid_list) * len(feature_cols))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    runs = collect_runs(Path(args.input_dir))
    if args.run_ts:
        runs = {k: v for k, v in runs.items() if k == args.run_ts}
    if not runs:
        raise SystemExit("No runs found.")

    rows = []
    with torch.no_grad():
        for ts, files in sorted(runs.items()):
            x = build_sample(files, uid_list, seq_len, feature_cols)
            x = (x - mean[:, None]) / std[:, None]
            xb = torch.from_numpy(x).unsqueeze(0)
            prob = torch.sigmoid(model(xb)).item()
            pred = "ABNORMAL" if prob >= threshold else "NORMAL"
            rows.append({"run_ts": ts, "prob_abnormal": prob, "pred": pred, "threshold": threshold})

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[saved] {out}")


if __name__ == "__main__":
    main()
