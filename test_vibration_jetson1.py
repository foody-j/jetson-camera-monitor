#!/usr/bin/env python3
"""Jetson1 vibration entrypoint (fixed UNIT_IDS)."""

import os
import subprocess
import sys


def _has_flag(argv, *flags) -> bool:
    return any(arg in flags for arg in argv)


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(script_dir, "test_vibration_pymodbus3_finalrev.py")
    env = os.environ.copy()
    env["VIB_UNIT_IDS"] = "0x53,0x54"  # 0x55 excluded for Jetson1

    argv = list(sys.argv[1:])
    if not _has_flag(argv, "--baseline"):
        argv.extend(["--baseline", os.path.join(script_dir, "vibration_baseline_jetson1.json")])
    if not _has_flag(argv, "--result"):
        argv.extend(["--result", os.path.join(script_dir, "vibration_result.json")])
    if not _has_flag(argv, "--cnn-model"):
        argv.extend(["--cnn-model", os.path.join(script_dir, "models", "vibration_cnn_jetson1_v2.pt")])
    if not _has_flag(argv, "--cnn-main"):
        argv.append("--cnn-main")

    cmd = [sys.executable, target, *argv]
    return subprocess.call(cmd, env=env, cwd=script_dir)


if __name__ == "__main__":
    raise SystemExit(main())
