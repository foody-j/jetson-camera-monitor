#!/usr/bin/env python3
import argparse
import os
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Flatten nested vibration event CSVs into a flat run dataset")
    ap.add_argument("--input-dir", required=True, help="Nested event dir, e.g. vibration_events/jetson1")
    ap.add_argument("--output-dir", required=True, help="Flat output dir")
    ap.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    args = ap.parse_args()

    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for event_dir in sorted(p for p in in_dir.iterdir() if p.is_dir()):
        run_ts = event_dir.name.split("_jetson")[0]
        for csv_path in sorted(event_dir.glob("UID*_vibration.csv")):
            uid_part = csv_path.name.replace("UID", "").replace("_vibration.csv", "")
            out_name = f"{run_ts}_UID{uid_part}_vibration.csv"
            out_path = out_dir / out_name
            if out_path.exists() or out_path.is_symlink():
                out_path.unlink()
            if args.mode == "symlink":
                rel = os.path.relpath(csv_path, out_dir)
                out_path.symlink_to(rel)
            else:
                shutil.copy2(csv_path, out_path)
            count += 1
    print(f"[done] {count} files -> {out_dir}")


if __name__ == "__main__":
    main()
