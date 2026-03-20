#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np


def _maximize(fig) -> None:
    manager = plt.get_current_fig_manager()
    try:
        manager.full_screen_toggle()
        return
    except Exception:
        pass
    window = getattr(manager, "window", None)
    if window is None:
        return
    for fn_name, arg in (("state", "zoomed"), ("showMaximized", None), ("Maximize", None)):
        try:
            fn = getattr(window, fn_name)
        except Exception:
            continue
        try:
            if arg is None:
                fn()
            else:
                fn(arg)
            return
        except Exception:
            continue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path", nargs="?")
    parser.add_argument("--snapshot-json")
    parser.add_argument("--event-dir")
    parser.add_argument("--title", default="Vibration Plot")
    args = parser.parse_args()

    if args.snapshot_json:
        fig = _figure_from_snapshot_json(os.path.abspath(args.snapshot_json), args.title)
    elif args.event_dir:
        fig = _figure_from_event_dir(os.path.abspath(args.event_dir), args.title)
    elif args.image_path:
        fig = _figure_from_image(os.path.abspath(args.image_path), args.title)
    else:
        print("[plot-viewer] no input specified", file=sys.stderr)
        return 1
    if fig is None:
        return 1
    _maximize(fig)

    def _close(_event):
        plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", lambda event: _close(event) if event.key in {"escape", "q"} else None)
    plt.show()
    return 0


def _figure_from_image(image_path: str, title: str):
    import matplotlib.image as mpimg

    if not os.path.exists(image_path):
        print(f"[plot-viewer] missing file: {image_path}", file=sys.stderr)
        return None
    img = mpimg.imread(image_path)
    fig = plt.figure(title, facecolor="black")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.imshow(img)
    ax.axis("off")
    fig.canvas.manager.set_window_title(title)
    return fig


def _figure_from_snapshot_json(snapshot_path: str, title: str):
    if not os.path.exists(snapshot_path):
        print(f"[plot-viewer] missing file: {snapshot_path}", file=sys.stderr)
        return None
    with open(snapshot_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    snapshot = {int(uid): rows for uid, rows in raw.items()}
    return _plot_snapshot(snapshot, title)


def _figure_from_event_dir(event_dir: str, title: str):
    if not os.path.isdir(event_dir):
        print(f"[plot-viewer] missing dir: {event_dir}", file=sys.stderr)
        return None
    snapshot = {}
    for name in sorted(os.listdir(event_dir)):
        if not (name.startswith("UID") and name.endswith("_vibration.csv")):
            continue
        uid = int(name[3:5], 16)
        rows = []
        base_ts = None
        with open(os.path.join(event_dir, name), "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cur_ts = _parse_time(row.get("time", ""))
                if base_ts is None:
                    base_ts = cur_ts
                rows.append(
                    {
                        "time": max(0.0, cur_ts - base_ts),
                        "vel": (
                            float(row.get("VEL_X(mm/s)", 0.0) or 0.0),
                            float(row.get("VEL_Y(mm/s)", 0.0) or 0.0),
                            float(row.get("VEL_Z(mm/s)", 0.0) or 0.0),
                        ),
                        "freq": (
                            float(row.get("FREQ_X(Hz)", 0.0) or 0.0),
                            float(row.get("FREQ_Y(Hz)", 0.0) or 0.0),
                            float(row.get("FREQ_Z(Hz)", 0.0) or 0.0),
                        ),
                    }
                )
        snapshot[uid] = rows
    return _plot_snapshot(snapshot, title)


def _parse_time(value: str) -> float:
    from datetime import datetime

    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0


def _plot_snapshot(snapshot: dict, title: str):
    unit_ids = sorted(snapshot.keys())
    if not unit_ids:
        print("[plot-viewer] no data to plot", file=sys.stderr)
        return None
    fig, axes = plt.subplots(len(unit_ids), 2, figsize=(18, max(6, 4 * len(unit_ids))), squeeze=False, facecolor="black")
    fig.canvas.manager.set_window_title(title)
    fig.suptitle(title, fontsize=18, color="white")
    colors = ("#ff6b6b", "#4ecdc4", "#ffe66d")
    for row_idx, uid in enumerate(unit_ids):
        rows = snapshot.get(uid, [])
        t = np.asarray([float(r["time"]) for r in rows], dtype=float) if rows else np.asarray([0.0], dtype=float)
        if t.size and t[0] > 1e6:
            t = t - t[0]
        vel_ax = axes[row_idx][0]
        freq_ax = axes[row_idx][1]
        for ax, label, ylabel in (
            (vel_ax, f"UID 0x{uid:02X} Velocity", "mm/s"),
            (freq_ax, f"UID 0x{uid:02X} Frequency", "Hz"),
        ):
            ax.set_facecolor("black")
            ax.grid(True, alpha=0.25, color="#888888")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_color("white")
            ax.set_title(label, color="white", fontsize=14)
            ax.set_xlabel("Time (s)", color="white")
            ax.set_ylabel(ylabel, color="white")
        for idx, axis_name in enumerate(("X", "Y", "Z")):
            vel_vals = np.asarray([float(r["vel"][idx]) for r in rows], dtype=float) if rows else np.asarray([])
            freq_vals = np.asarray([float(r["freq"][idx]) for r in rows], dtype=float) if rows else np.asarray([])
            if vel_vals.size:
                vel_ax.plot(t[: len(vel_vals)], vel_vals, label=axis_name, linewidth=2.0, color=colors[idx])
            if freq_vals.size:
                freq_ax.plot(t[: len(freq_vals)], freq_vals, label=axis_name, linewidth=2.0, color=colors[idx])
        vel_ax.legend(loc="upper right")
        freq_ax.legend(loc="upper right")
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    return fig


if __name__ == "__main__":
    raise SystemExit(main())
