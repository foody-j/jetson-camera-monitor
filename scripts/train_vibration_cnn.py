#!/usr/bin/env python3
import argparse
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


RUN_RE = re.compile(r"^(\d{8}_\d{6})_UID([0-9A-Fa-f]+)_vibration\.csv$")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def parse_uid_list(raw: str) -> List[str]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if part.lower().startswith("0x"):
            part = part[2:]
        out.append(part.upper())
    return out


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
    channels: List[np.ndarray] = []
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


@dataclass
class SampleItem:
    run_ts: str
    label: int
    x: np.ndarray


class VibrationDataset(Dataset):
    def __init__(self, items: List[SampleItem], mean: np.ndarray, std: np.ndarray):
        self.items = items
        self.mean = mean
        self.std = std

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int):
        item = self.items[idx]
        x = (item.x - self.mean[:, None]) / self.std[:, None]
        return torch.from_numpy(x), torch.tensor(item.label, dtype=torch.float32), item.run_ts


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


def split_items(items: List[SampleItem], val_ratio: float, seed: int) -> Tuple[List[SampleItem], List[SampleItem]]:
    by_label = {0: [], 1: []}
    for it in items:
        by_label[it.label].append(it)
    rng = random.Random(seed)
    train, val = [], []
    for label_items in by_label.values():
        rng.shuffle(label_items)
        n_val = max(1, int(round(len(label_items) * val_ratio))) if len(label_items) >= 3 else 1
        val.extend(label_items[:n_val])
        train.extend(label_items[n_val:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def compute_mean_std(items: List[SampleItem]) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.concatenate([it.x for it in items], axis=1)  # [C, total_T]
    mean = arr.mean(axis=1).astype(np.float32)
    std = arr.std(axis=1).astype(np.float32)
    std[std < 1e-6] = 1.0
    return mean, std


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device, threshold: float) -> Dict[str, float]:
    model.eval()
    probs, labels = [], []
    with torch.no_grad():
        for xb, yb, _ in loader:
            xb = xb.to(device)
            logits = model(xb)
            p = torch.sigmoid(logits).cpu().numpy()
            probs.extend(p.tolist())
            labels.extend(yb.numpy().tolist())
    y_true = np.array(labels, dtype=np.int32)
    y_pred = (np.array(probs) >= threshold).astype(np.int32)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-8, prec + rec)
    return {
        "acc": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Train 1D CNN for vibration run classification")
    ap.add_argument("--normal-dir", required=True, help="Normal CSV directory")
    ap.add_argument("--abnormal-dir", required=True, help="Abnormal CSV directory")
    ap.add_argument("--uids", default="0x53,0x54", help="Comma-separated UIDs")
    ap.add_argument("--seq-len", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="models/vibration_cnn_jetson1.pt")
    args = ap.parse_args()

    set_seed(args.seed)
    uid_list = parse_uid_list(args.uids)
    feature_cols = [
        "VEL_X(mm/s)",
        "VEL_Y(mm/s)",
        "VEL_Z(mm/s)",
        "FREQ_X(Hz)",
        "FREQ_Y(Hz)",
        "FREQ_Z(Hz)",
    ]
    normal_runs = collect_runs(Path(args.normal_dir))
    abnormal_runs = collect_runs(Path(args.abnormal_dir))

    items: List[SampleItem] = []
    for ts, files in normal_runs.items():
        x = build_sample(files, uid_list, args.seq_len, feature_cols)
        items.append(SampleItem(run_ts=ts, label=0, x=x))
    for ts, files in abnormal_runs.items():
        x = build_sample(files, uid_list, args.seq_len, feature_cols)
        items.append(SampleItem(run_ts=ts, label=1, x=x))

    if len(items) < 4:
        raise SystemExit("Not enough run samples.")

    train_items, val_items = split_items(items, args.val_ratio, args.seed)
    mean, std = compute_mean_std(train_items)

    train_ds = VibrationDataset(train_items, mean, std)
    val_ds = VibrationDataset(val_items, mean, std)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SmallVibrationCNN(in_ch=train_items[0].x.shape[0]).to(device)

    n_pos = sum(it.label for it in train_items)
    n_neg = len(train_items) - n_pos
    pos_weight = torch.tensor([n_neg / max(1, n_pos)], dtype=torch.float32, device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    best_f1 = -1.0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for xb, yb, _ in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            logits = model(xb)
            loss = criterion(logits, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))
        metrics = evaluate(model, val_loader, device, args.threshold)
        print(
            f"[epoch {epoch:03d}] loss={np.mean(losses):.4f} "
            f"val_f1={metrics['f1']:.3f} val_rec={metrics['recall']:.3f} val_fp={metrics['fp']}"
        )
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_state = {k: v.cpu() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    final_metrics = evaluate(model, val_loader, device, args.threshold)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_state_dict": model.state_dict(),
        "mean": mean,
        "std": std,
        "uid_list": uid_list,
        "feature_cols": feature_cols,
        "seq_len": args.seq_len,
        "threshold": args.threshold,
        "metrics_val": final_metrics,
        "train_runs": [it.run_ts for it in train_items],
        "val_runs": [it.run_ts for it in val_items],
    }
    torch.save(payload, out_path)
    print(f"[saved] {out_path}")
    print(json.dumps(final_metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
