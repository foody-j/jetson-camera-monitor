#!/usr/bin/env python3
"""
Simple GUI publisher for HR/Status MQTT messages.

Run:
  python3 scripts/mqtt_hr_status_gui.py
"""

import json
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import paho.mqtt.client as mqtt


class HRStatusGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("HR/Status MQTT Simulator")
        self.root.geometry("760x560")

        self.client = None
        self.connected = False

        self.broker_var = tk.StringVar(value="192.168.0.100")
        self.port_var = tk.StringVar(value="1883")
        self.topic_var = tk.StringVar(value="HR/Status")
        self.qos_var = tk.StringVar(value="1")

        self.target_var = tk.StringVar(value="all")   # all/j1/j2
        self.phase_var = tk.StringVar(value="투입")
        self.vibration_var = tk.BooleanVar(value=False)
        self.recipe_j1_p0 = tk.StringVar(value="볶음밥")
        self.recipe_j1_p1 = tk.StringVar(value="짜장")
        self.recipe_j2_p0 = tk.StringVar(value="치킨")
        self.recipe_j2_p1 = tk.StringVar(value="새우")
        self.running_time_var = tk.StringVar(value="0분 30초")
        self.target_time_var = tk.StringVar(value="3분 0초")

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        conn = ttk.LabelFrame(frame, text="Connection", padding=10)
        conn.pack(fill="x")
        ttk.Label(conn, text="Broker").grid(row=0, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self.broker_var, width=20).grid(row=0, column=1, padx=6)
        ttk.Label(conn, text="Port").grid(row=0, column=2, sticky="w")
        ttk.Entry(conn, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=6)
        ttk.Label(conn, text="Topic").grid(row=0, column=4, sticky="w")
        ttk.Entry(conn, textvariable=self.topic_var, width=18).grid(row=0, column=5, padx=6)
        ttk.Label(conn, text="QoS").grid(row=0, column=6, sticky="w")
        ttk.Combobox(conn, textvariable=self.qos_var, values=["0", "1", "2"], width=4, state="readonly").grid(
            row=0, column=7, padx=6
        )
        ttk.Button(conn, text="Connect", command=self.connect).grid(row=0, column=8, padx=6)
        ttk.Button(conn, text="Disconnect", command=self.disconnect).grid(row=0, column=9, padx=6)

        self.status_label = ttk.Label(conn, text="Disconnected")
        self.status_label.grid(row=1, column=0, columnspan=10, sticky="w", pady=(8, 0))

        cfg = ttk.LabelFrame(frame, text="Payload", padding=10)
        cfg.pack(fill="x", pady=(10, 0))

        ttk.Label(cfg, text="Target").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(cfg, text="All", variable=self.target_var, value="all").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(cfg, text="Jetson1", variable=self.target_var, value="j1").grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(cfg, text="Jetson2", variable=self.target_var, value="j2").grid(row=0, column=3, sticky="w")

        ttk.Label(cfg, text="Phase").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            cfg,
            textvariable=self.phase_var,
            values=["투입", "조리", "배출", "대기"],
            width=10,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Checkbutton(cfg, text="VibrationRequest", variable=self.vibration_var).grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(8, 0)
        )

        ttk.Label(cfg, text="RunningTime").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cfg, textvariable=self.running_time_var, width=12).grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(cfg, text="TargetTime").grid(row=2, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(cfg, textvariable=self.target_time_var, width=12).grid(row=2, column=3, sticky="w", pady=(8, 0))

        recipe = ttk.LabelFrame(frame, text="Recipes", padding=10)
        recipe.pack(fill="x", pady=(10, 0))
        ttk.Label(recipe, text="J1 PT0").grid(row=0, column=0, sticky="w")
        ttk.Entry(recipe, textvariable=self.recipe_j1_p0, width=14).grid(row=0, column=1, padx=6)
        ttk.Label(recipe, text="J1 PT1").grid(row=0, column=2, sticky="w")
        ttk.Entry(recipe, textvariable=self.recipe_j1_p1, width=14).grid(row=0, column=3, padx=6)
        ttk.Label(recipe, text="J2 PT0").grid(row=0, column=4, sticky="w")
        ttk.Entry(recipe, textvariable=self.recipe_j2_p0, width=14).grid(row=0, column=5, padx=6)
        ttk.Label(recipe, text="J2 PT1").grid(row=0, column=6, sticky="w")
        ttk.Entry(recipe, textvariable=self.recipe_j2_p1, width=14).grid(row=0, column=7, padx=6)

        buttons = ttk.LabelFrame(frame, text="Quick Publish", padding=10)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="투입", command=lambda: self.publish_phase("투입")).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(buttons, text="조리", command=lambda: self.publish_phase("조리")).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(buttons, text="배출", command=lambda: self.publish_phase("배출")).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(buttons, text="대기", command=lambda: self.publish_phase("대기")).grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(buttons, text="Vibration ON", command=lambda: self.publish_with_vibration(True)).grid(
            row=0, column=4, padx=10, pady=4
        )
        ttk.Button(buttons, text="Vibration OFF", command=lambda: self.publish_with_vibration(False)).grid(
            row=0, column=5, padx=4, pady=4
        )
        ttk.Button(buttons, text="Publish Current", command=self.publish_current).grid(row=0, column=6, padx=10, pady=4)

        logf = ttk.LabelFrame(frame, text="Log", padding=10)
        logf.pack(fill="both", expand=True, pady=(10, 0))
        self.log = tk.Text(logf, height=14, wrap="none")
        self.log.pack(fill="both", expand=True)

    def connect(self):
        if self.connected:
            self._write("Already connected.")
            return
        try:
            broker = self.broker_var.get().strip()
            port = int(self.port_var.get().strip())
            self.client = mqtt.Client(client_id="hr_status_gui")
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.connect(broker, port, 60)
            self.client.loop_start()
            self._write(f"Connecting to {broker}:{port} ...")
        except Exception as e:
            self._write(f"Connect error: {e}")

    def disconnect(self):
        if not self.client:
            return
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False
        self.status_label.config(text="Disconnected")

    def _on_connect(self, client, userdata, flags, rc):
        self.connected = (rc == 0)
        if self.connected:
            self.status_label.config(text="Connected")
            self._write("Connected.")
        else:
            self.status_label.config(text=f"Connect failed: rc={rc}")
            self._write(f"Connect failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        self.status_label.config(text="Disconnected")
        self._write(f"Disconnected: rc={rc}")

    def publish_phase(self, phase: str):
        self.phase_var.set(phase)
        self.publish_current()

    def publish_with_vibration(self, enabled: bool):
        self.vibration_var.set(enabled)
        self.publish_current()

    def _build_status(self, device_num: str, pt_num: str, recipe: str) -> dict:
        phase = self.phase_var.get()
        rb_status = "RUN" if phase in ("투입", "조리") else ("DISCHARGE" if phase == "배출" else "IDLE")
        if phase == "대기":
            recipe = ""
        return {
            "DeviceNum": device_num,
            "PTNum": pt_num,
            "NowRecipe": recipe,
            "ProcessType": phase,
            "RunningTime": self.running_time_var.get().strip(),
            "TargetTime": self.target_time_var.get().strip(),
            "RBstatus": rb_status,
            "ChkVibration": bool(self.vibration_var.get()),
            "Mode": "AUTO",
            "Potstatus": {
                "PT_Temp": 170 if device_num == "0" else 140,
                "PT_Power": "True" if phase in ("투입", "조리") else "False",
                "PT_Level": 60 if phase in ("투입", "조리") else 20,
                "RT_Speed": 30 if phase == "조리" else 0,
                "RT_Dir": 1,
            },
        }

    def _build_payload(self) -> dict:
        target = self.target_var.get()
        status = []
        if target in ("all", "j2"):
            status.append(self._build_status("0", "0", self.recipe_j2_p0.get().strip()))
            status.append(self._build_status("0", "1", self.recipe_j2_p1.get().strip()))
        if target in ("all", "j1"):
            status.append(self._build_status("1", "0", self.recipe_j1_p0.get().strip()))
            status.append(self._build_status("1", "1", self.recipe_j1_p1.get().strip()))
        rb_motion = 1 if self.phase_var.get() == "조리" else 0
        return {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "RBMotion": rb_motion,
            "VibrationRequest": bool(self.vibration_var.get()),
            "Status": status,
        }

    def publish_current(self):
        if not self.client or not self.connected:
            self._write("Not connected. Click Connect first.")
            return
        payload = self._build_payload()
        topic = self.topic_var.get().strip() or "HR/Status"
        qos = int(self.qos_var.get())
        body = json.dumps(payload, ensure_ascii=False)
        try:
            info = self.client.publish(topic, body, qos=qos)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                self._write(f"Published to {topic} (qos={qos})")
                self._write(body)
            else:
                self._write(f"Publish failed rc={info.rc}")
        except Exception as e:
            self._write(f"Publish error: {e}")

    def _write(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {text}\n")
        self.log.see("end")


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    HRStatusGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
