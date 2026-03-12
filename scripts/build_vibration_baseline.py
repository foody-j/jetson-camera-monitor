#!/usr/bin/env python3
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


RUN_RE = re.compile(r"^(\d{8}_\d{6})_UID([0-9A-Fa-f]+)_vibration\.csv$")


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


def collect_runs(folder: Path) -> Dict[str, Dict[str, Path]]:
    grouped: Dict[str, Dict[str, Path]] = defaultdict(dict)
    for path in sorted(folder.glob("*.csv")):
        m = RUN_RE.match(path.name)
        if not m:
            continue
        ts, uid = m.group(1), m.group(2).upper()
        grouped[ts][uid] = path
    return grouped


def series_stats(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return {"mean": 0.0, "std": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build vibration baseline JSON from flat normal CSV runs")
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--uids", required=True, help="Comma-separated UIDs, e.g. 0x53,0x54")
    ap.add_argument("--output", required=True)
    ap.add_argument("--system-name", required=True)
    ap.add_argument("--template", default="", help="Optional existing baseline JSON to preserve structure")
    args = ap.parse_args()

    uid_list = parse_uid_list(args.uids)
    runs = collect_runs(Path(args.input_dir))

    template = {}
    if args.template and Path(args.template).exists():
        template = json.loads(Path(args.template).read_text(encoding="utf-8"))

    all_acc = {"X": [], "Y": [], "Z": []}
    all_vel = {"X": [], "Y": [], "Z": [], "MAGNITUDE": []}
    all_disp = {"X": [], "Y": [], "Z": []}
    all_freq = {"X": [], "Y": [], "Z": []}
    all_fft = {"X": [], "Y": [], "Z": []}
    run_feats = []
    total_samples = 0

    for run_ts, files in sorted(runs.items()):
        per_run = {"run_ts": run_ts}
        run_has_data = False
        for uid in uid_list:
            csv_path = files.get(uid)
            if csv_path is None:
                continue
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            if df.empty:
                continue
            run_has_data = True
            total_samples += len(df)

            ax = pd.to_numeric(df["ACC_X(g)"], errors="coerce").fillna(0.0).abs().to_numpy()
            ay = pd.to_numeric(df["ACC_Y(g)"], errors="coerce").fillna(0.0).abs().to_numpy()
            az = pd.to_numeric(df["ACC_Z(g)"], errors="coerce").fillna(0.0).abs().to_numpy()
            vx = pd.to_numeric(df["VEL_X(mm/s)"], errors="coerce").fillna(0.0).abs().to_numpy()
            vy = pd.to_numeric(df["VEL_Y(mm/s)"], errors="coerce").fillna(0.0).abs().to_numpy()
            vz = pd.to_numeric(df["VEL_Z(mm/s)"], errors="coerce").fillna(0.0).abs().to_numpy()
            dx = pd.to_numeric(df["DISP_X(um)"], errors="coerce").fillna(0.0).abs().to_numpy()
            dy = pd.to_numeric(df["DISP_Y(um)"], errors="coerce").fillna(0.0).abs().to_numpy()
            dz = pd.to_numeric(df["DISP_Z(um)"], errors="coerce").fillna(0.0).abs().to_numpy()
            fx = pd.to_numeric(df["FREQ_X(Hz)"], errors="coerce").fillna(0.0).abs().to_numpy()
            fy = pd.to_numeric(df["FREQ_Y(Hz)"], errors="coerce").fillna(0.0).abs().to_numpy()
            fz = pd.to_numeric(df["FREQ_Z(Hz)"], errors="coerce").fillna(0.0).abs().to_numpy()
            fpx = pd.to_numeric(df["FFT_PEAK_X(Hz)"], errors="coerce").fillna(0.0).abs().to_numpy()
            fpy = pd.to_numeric(df["FFT_PEAK_Y(Hz)"], errors="coerce").fillna(0.0).abs().to_numpy()
            fpz = pd.to_numeric(df["FFT_PEAK_Z(Hz)"], errors="coerce").fillna(0.0).abs().to_numpy()

            mag = np.sqrt(vx ** 2 + vy ** 2 + vz ** 2)

            all_acc["X"].extend(ax.tolist())
            all_acc["Y"].extend(ay.tolist())
            all_acc["Z"].extend(az.tolist())
            all_vel["X"].extend(vx.tolist())
            all_vel["Y"].extend(vy.tolist())
            all_vel["Z"].extend(vz.tolist())
            all_vel["MAGNITUDE"].extend(mag.tolist())
            all_disp["X"].extend(dx.tolist())
            all_disp["Y"].extend(dy.tolist())
            all_disp["Z"].extend(dz.tolist())
            all_freq["X"].extend(fx.tolist())
            all_freq["Y"].extend(fy.tolist())
            all_freq["Z"].extend(fz.tolist())
            all_fft["X"].extend(fpx[fpx > 0].tolist())
            all_fft["Y"].extend(fpy[fpy > 0].tolist())
            all_fft["Z"].extend(fpz[fpz > 0].tolist())

            uid_key = f"uid{uid}"
            per_run[f"{uid_key}_vel_x_p99"] = float(np.percentile(vx, 99))
            per_run[f"{uid_key}_vel_y_p99"] = float(np.percentile(vy, 99))
            per_run[f"{uid_key}_vel_z_p99"] = float(np.percentile(vz, 99))
            per_run[f"{uid_key}_vel_mag_p99"] = float(np.percentile(mag, 99))
            per_run[f"{uid_key}_freq_x_p99"] = float(np.percentile(fx, 99))
            per_run[f"{uid_key}_freq_y_p99"] = float(np.percentile(fy, 99))
            per_run[f"{uid_key}_freq_z_p99"] = float(np.percentile(fz, 99))
            per_run[f"{uid_key}_freq_x_max"] = float(np.max(fx))
            per_run[f"{uid_key}_freq_y_max"] = float(np.max(fy))
            per_run[f"{uid_key}_freq_z_max"] = float(np.max(fz))
        if run_has_data:
            run_feats.append(per_run)

    if not run_feats:
        raise SystemExit("No valid runs found")

    run_df = pd.DataFrame(run_feats)

    acceleration = {axis: series_stats(np.asarray(vals)) for axis, vals in all_acc.items()}
    for axis in acceleration:
        acceleration[axis]["threshold_3sigma"] = acceleration[axis]["mean"] + 3.0 * acceleration[axis]["std"]

    velocity = {axis: series_stats(np.asarray(vals)) for axis, vals in all_vel.items()}
    for axis in velocity:
        velocity[axis]["threshold_3sigma"] = velocity[axis]["mean"] + 3.0 * velocity[axis]["std"]

    displacement = {axis: series_stats(np.asarray(vals)) for axis, vals in all_disp.items()}
    frequency = {axis: series_stats(np.asarray(vals)) for axis, vals in all_freq.items()}
    fft_peak = {}
    for axis, vals in all_fft.items():
        valid = np.asarray(vals, dtype=np.float64)
        fft_peak[axis] = {
            "mean": float(np.mean(valid)) if valid.size else 0.0,
            "std": float(np.std(valid)) if valid.size else 0.0,
            "valid_ratio": float(100.0 * valid.size / max(1, len(all_freq[axis]))),
        }

    def q(series_name: str, qv: float, default: float = 0.0) -> float:
        vals = pd.to_numeric(run_df[series_name], errors="coerce").dropna().to_numpy(dtype=np.float64)
        return float(np.percentile(vals, qv)) if vals.size else default

    vel_mag_run = []
    for uid in uid_list:
        col = f"uid{uid}_vel_mag_p99"
        if col in run_df.columns:
            vel_mag_run.extend(pd.to_numeric(run_df[col], errors="coerce").dropna().tolist())
    vel_mag_run = np.asarray(vel_mag_run, dtype=np.float64) if vel_mag_run else np.asarray([], dtype=np.float64)

    thresholds = dict(template.get("thresholds", {}))
    thresholds.update(
        {
            "velocity_magnitude_p99": float(np.percentile(vel_mag_run, 99)) if vel_mag_run.size else velocity["MAGNITUDE"]["p99"],
            "velocity_magnitude_3sigma": float(np.percentile(vel_mag_run, 99.5) * 1.03) if vel_mag_run.size else velocity["MAGNITUDE"]["threshold_3sigma"],
            "vel_x_p99": q(f"uid{uid_list[0]}_vel_x_p99", 99, velocity["X"]["p99"]),
            "vel_y_p99": q(f"uid{uid_list[0]}_vel_y_p99", 99, velocity["Y"]["p99"]),
            "vel_z_p99": q(f"uid{uid_list[0]}_vel_z_p99", 99, velocity["Z"]["p99"]),
            "vel_x_3sigma": q(f"uid{uid_list[0]}_vel_x_p99", 99.5, velocity["X"]["threshold_3sigma"]) * 1.03,
            "vel_y_3sigma": q(f"uid{uid_list[0]}_vel_y_p99", 99.5, velocity["Y"]["threshold_3sigma"]) * 1.03,
            "vel_z_3sigma": q(f"uid{uid_list[0]}_vel_z_p99", 99.5, velocity["Z"]["threshold_3sigma"]) * 1.03,
            "velocity_magnitude_low": float(np.percentile(vel_mag_run, 1) * 0.90) if vel_mag_run.size else 0.0,
            "vel_x_low": q(f"uid{uid_list[0]}_vel_x_p99", 1, 0.0) * 0.90,
            "vel_y_low": q(f"uid{uid_list[0]}_vel_y_p99", 1, 0.0) * 0.90,
            "vel_z_low": q(f"uid{uid_list[0]}_vel_z_p99", 1, 0.0) * 0.90,
            "freq_x_low": 0.0,
            "freq_y_low": 0.0,
            "freq_z_low": 0.0,
            "freq_x_high": max(q(f"uid{uid_list[0]}_freq_x_max", 99.5, frequency["X"]["p99"]) * 1.02, 1.0),
            "freq_y_high": max(q(f"uid{uid_list[0]}_freq_y_max", 99.5, frequency["Y"]["p99"]) * 1.02, 1.0),
            "freq_z_high": max(q(f"uid{uid_list[0]}_freq_z_max", 99.5, frequency["Z"]["p99"]) * 1.02, 1.0),
            "freq_x_single_uid_high": max(q(f"uid{uid_list[0]}_freq_x_max", 99.5, frequency["X"]["p99"]) * 1.02, 1.0),
            "freq_y_single_uid_high": max(q(f"uid{uid_list[0]}_freq_y_max", 99.5, frequency["Y"]["p99"]) * 1.02, 1.0),
            "freq_z_single_uid_high": max(q(f"uid{uid_list[0]}_freq_z_max", 99.5, frequency["Z"]["p99"]) * 1.02, 1.0),
            "min_exceed_duration_sec": float(thresholds.get("min_exceed_duration_sec", 0.2)),
            "freq_checks_enabled": bool(thresholds.get("freq_checks_enabled", True)),
        }
    )

    if len(uid_list) == 2:
        thresholds["velocity_include_uids"] = [f"0x{uid}" for uid in uid_list]
        thresholds["velocity_combo_min_triggers"] = 2
        for uid in uid_list:
            vals = pd.to_numeric(run_df[f"uid{uid}_vel_mag_p99"], errors="coerce").dropna().to_numpy(dtype=np.float64)
            if vals.size:
                thresholds[f"uid{uid.lower()}_vel_mag_max"] = float(np.percentile(vals, 99.5) * 1.03)
                thresholds[f"uid{uid.lower()}_vel_mag_min"] = float(np.percentile(vals, 1.0) * 0.90)

    result = {
        "system": args.system_name,
        "total_samples": int(total_samples),
        "acceleration": acceleration,
        "velocity": velocity,
        "displacement": displacement,
        "frequency": frequency,
        "fft_peak": fft_peak,
        "thresholds": thresholds,
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[saved] {out_path}")
    print(json.dumps({"thresholds": thresholds}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
