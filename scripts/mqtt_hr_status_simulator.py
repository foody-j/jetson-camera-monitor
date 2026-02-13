#!/usr/bin/env python3
"""
HR/Status MQTT simulator for Jetson1/Jetson2 integration checks.

Examples:
  python3 scripts/mqtt_hr_status_simulator.py --broker 192.168.0.100
  python3 scripts/mqtt_hr_status_simulator.py --mode j1 --interval 1
  python3 scripts/mqtt_hr_status_simulator.py --once --vibration true
"""

import argparse
import json
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime

import paho.mqtt.client as mqtt


PHASES = ["투입", "조리", "배출", "대기"]


@dataclass
class PotState:
    device_num: str
    pt_num: str
    recipe: str
    target_time_sec: int
    phase_idx: int = 0
    elapsed_sec: int = 0
    chk_vibration: bool = False

    def step(self, tick_sec: int) -> None:
        phase = PHASES[self.phase_idx]
        if phase in ("투입", "조리"):
            self.elapsed_sec += tick_sec
        else:
            self.elapsed_sec = 0

    def next_phase(self) -> None:
        self.phase_idx = (self.phase_idx + 1) % len(PHASES)
        if PHASES[self.phase_idx] in ("투입", "대기"):
            self.elapsed_sec = 0
        self.chk_vibration = PHASES[self.phase_idx] == "조리"

    def build_status(self) -> dict:
        phase = PHASES[self.phase_idx]
        minutes = self.elapsed_sec // 60
        seconds = self.elapsed_sec % 60
        target_m = self.target_time_sec // 60
        target_s = self.target_time_sec % 60
        running_time = f"{minutes}분 {seconds}초"
        target_time = f"{target_m}분 {target_s}초"

        rb_status = "RUN" if phase in ("투입", "조리") else ("DISCHARGE" if phase == "배출" else "IDLE")
        pot_temp = 175 if self.device_num == "0" else 140
        if phase == "대기":
            pot_temp -= 20

        return {
            "DeviceNum": self.device_num,
            "PTNum": self.pt_num,
            "NowRecipe": self.recipe if phase != "대기" else "",
            "ProcessType": phase,
            "RunningTime": running_time,
            "TargetTime": target_time,
            "RBstatus": rb_status,
            "ChkVibration": self.chk_vibration,
            "Mode": "AUTO",
            "Potstatus": {
                "PT_Temp": pot_temp,
                "PT_Power": "True" if phase in ("투입", "조리") else "False",
                "PT_Level": 60 if phase in ("투입", "조리") else 20,
                "RT_Speed": 30 if phase == "조리" else 0,
                "RT_Dir": 1,
            },
        }


class HRStatusSimulator:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.running = True
        self.client = mqtt.Client(client_id=args.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.tick = max(1, int(args.interval))
        self.cycle_every = max(1, int(args.cycle_every))
        self.publish_count = 0
        self.states = self._init_states(args.mode)

    def _init_states(self, mode: str) -> list[PotState]:
        states: list[PotState] = []
        if mode in ("all", "j2"):
            states.append(PotState("0", "0", "치킨", 240))
            states.append(PotState("0", "1", "새우", 210))
        if mode in ("all", "j1"):
            states.append(PotState("1", "0", "볶음밥", 180))
            states.append(PotState("1", "1", "짜장", 180))
        return states

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] connected: {self.args.broker}:{self.args.port}")
        else:
            print(f"[MQTT] connect failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] disconnected: rc={rc}")

    def _build_payload(self) -> dict:
        for st in self.states:
            st.step(self.tick)

        self.publish_count += 1
        if self.publish_count % self.cycle_every == 0:
            for st in self.states:
                st.next_phase()

        vibration_request = self.args.vibration
        if vibration_request is None:
            vibration_request = any(st.chk_vibration for st in self.states)

        rb_motion = 1 if any(PHASES[st.phase_idx] == "조리" for st in self.states) else 0

        return {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "RBMotion": rb_motion,
            "VibrationRequest": bool(vibration_request),
            "Status": [st.build_status() for st in self.states],
        }

    def run(self) -> int:
        try:
            self.client.connect(self.args.broker, self.args.port, keepalive=60)
        except Exception as e:
            print(f"[ERROR] MQTT connect failed: {e}")
            return 1

        self.client.loop_start()
        print(
            f"[SIM] topic={self.args.topic}, mode={self.args.mode}, interval={self.tick}s, cycle_every={self.cycle_every}"
        )

        try:
            while self.running:
                payload = self._build_payload()
                payload_text = json.dumps(payload, ensure_ascii=False)
                result = self.client.publish(self.args.topic, payload_text, qos=self.args.qos)
                phase_info = ", ".join(
                    [f"D{st.device_num}-P{st.pt_num}:{PHASES[st.phase_idx]}" for st in self.states]
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"[PUB] {datetime.now().strftime('%H:%M:%S')} ok | {phase_info}")
                else:
                    print(f"[PUB] publish failed: rc={result.rc}")

                if self.args.once:
                    break
                time.sleep(self.tick)
        except KeyboardInterrupt:
            pass
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("[SIM] stopped")
        return 0

    def stop(self, *_args):
        self.running = False


def parse_bool(value: str):
    if value is None:
        return None
    value = value.strip().lower()
    if value in ("1", "true", "yes", "y", "on"):
        return True
    if value in ("0", "false", "no", "n", "off"):
        return False
    raise argparse.ArgumentTypeError(f"invalid bool: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish simulated HR/Status messages.")
    parser.add_argument("--broker", default="192.168.0.100", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--topic", default="HR/Status", help="MQTT topic")
    parser.add_argument("--qos", type=int, default=1, choices=[0, 1, 2], help="MQTT QoS")
    parser.add_argument("--client-id", default="hr_status_simulator", help="MQTT client id")
    parser.add_argument("--mode", choices=["all", "j1", "j2"], default="all", help="Simulate target device set")
    parser.add_argument("--interval", type=int, default=2, help="Publish interval seconds")
    parser.add_argument(
        "--cycle-every",
        type=int,
        default=5,
        help="Move to next ProcessType phase every N publishes",
    )
    parser.add_argument(
        "--vibration",
        type=parse_bool,
        default=None,
        help="Force VibrationRequest true/false (default: auto by phase)",
    )
    parser.add_argument("--once", action="store_true", help="Publish once and exit")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    sim = HRStatusSimulator(args)
    signal.signal(signal.SIGTERM, sim.stop)
    signal.signal(signal.SIGINT, sim.stop)
    return sim.run()


if __name__ == "__main__":
    sys.exit(main())
