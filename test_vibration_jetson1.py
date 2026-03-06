#!/usr/bin/env python3
"""Jetson1 vibration entrypoint (fixed UNIT_IDS)."""

import os
import subprocess
import sys


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(script_dir, "test_vibration_pymodbus3_finalrev.py")
    env = os.environ.copy()
    env["VIB_UNIT_IDS"] = "0x53,0x54"  # 0x55 excluded for Jetson1
    cmd = [sys.executable, target, *sys.argv[1:]]
    return subprocess.call(cmd, env=env, cwd=script_dir)


if __name__ == "__main__":
    raise SystemExit(main())
