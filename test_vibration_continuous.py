#!/usr/bin/env python3
"""Manual continuous vibration test harness."""

import argparse
import os
import time

from vibration_continuous_runtime import ContinuousVibrationMonitor


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous vibration monitor manual test")
    parser.add_argument("--jetson", choices=["1", "2"], required=True)
    parser.add_argument("--pre", type=float, default=3.0)
    parser.add_argument("--post", type=float, default=2.0)
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    if args.jetson == "1":
        unit_ids = [0x53, 0x54]
        baseline = os.path.join(repo_root, "vibration_baseline_jetson1.json")
        cnn_model = os.path.join(repo_root, "models", "vibration_cnn_jetson1_v1.pt")
        event_dir = os.path.join(os.path.expanduser("~"), "data", "vibration_events", "jetson1_manual")
    else:
        unit_ids = [0x52]
        baseline = os.path.join(repo_root, "vibration_baseline_jetson2.json")
        cnn_model = os.path.join(repo_root, "models", "vibration_cnn_jetson2_v1.pt")
        if not os.path.exists(cnn_model):
            cnn_model = None
        event_dir = os.path.join(os.path.expanduser("~"), "data", "vibration_events", "jetson2_manual")

    monitor = ContinuousVibrationMonitor(
        unit_ids,
        baseline_path=baseline,
        cnn_model_path=cnn_model if cnn_model and os.path.exists(cnn_model) else None,
        use_cnn_main=True,
        event_root_dir=event_dir,
        pre_sec=args.pre,
        post_sec=args.post,
        log_prefix="[진동테스트]",
    )
    monitor.start()
    print("Enter: capture, q: quit")
    try:
        while True:
            command = input("> ").strip().lower()
            if command == "q":
                break
            ok, reason = monitor.trigger_capture(event_tag=f"manual_j{args.jetson}")
            print(f"capture={ok} reason={reason}")
            while monitor.is_capture_running():
                time.sleep(0.1)
            if monitor.last_capture_result:
                print(
                    f"status={monitor.last_capture_result.get('status')} "
                    f"source={monitor.last_capture_result.get('decision_source')} "
                    f"dir={monitor.last_capture_result.get('event_dir')}"
                )
    finally:
        monitor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
