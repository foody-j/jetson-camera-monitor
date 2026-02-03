#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 과제보고서용 실제 MQTT 이벤트 시뮬레이터

원본 코드 건드리지 않고, 실제 MQTT 데이터를 전송하여
Jetson GUI가 실제로 반응하도록 함!
"""

import tkinter as tk
from tkinter import ttk
import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time

# MQTT 설정 (config.json과 동일)
MQTT_BROKER = "192.168.0.100"
MQTT_PORT = 1883

class RealMQTTEventSimulator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎬 과제보고서용 실제 MQTT 이벤트 시뮬레이터")
        self.root.geometry("700x750")
        self.root.configure(bg="white")

        # MQTT 클라이언트
        self.mqtt_client = None
        self.mqtt_connected = False

        self.setup_gui()
        self.connect_mqtt()

    def setup_gui(self):
        """GUI 구성"""
        # 헤더
        header_frame = tk.Frame(self.root, bg="#2C3E50", height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text="🎬 실제 MQTT 이벤트 시뮬레이터",
            font=("맑은 고딕", 18, "bold"),
            bg="#2C3E50",
            fg="white"
        ).pack(pady=25)

        # MQTT 상태
        status_frame = tk.Frame(self.root, bg="white")
        status_frame.pack(pady=10)

        self.mqtt_status = tk.Label(
            status_frame,
            text="MQTT: 연결 중...",
            font=("맑은 고딕", 12),
            bg="white",
            fg="#E74C3C"
        )
        self.mqtt_status.pack()

        # 안내
        info_frame = tk.Frame(self.root, bg="#ECF0F1", bd=1, relief='solid')
        info_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(
            info_frame,
            text="💡 원본 코드 수정 없이 실제 HR/Status 메시지를 전송합니다\n"
                 "Jetson GUI가 실제로 반응하여 토스트를 표시합니다",
            font=("맑은 고딕", 10),
            bg="#ECF0F1",
            fg="#34495E",
            justify='center'
        ).pack(pady=10)

        # 메인 컨텐츠
        main_frame = tk.Frame(self.root, bg="white")
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # ========================================
        # Jetson #1 이벤트
        # ========================================
        j1_frame = tk.LabelFrame(
            main_frame,
            text="📟 Jetson #1 (사람 감지 + 볶음)",
            font=("맑은 고딕", 14, "bold"),
            bg="white",
            fg="#3498DB",
            padx=15,
            pady=15
        )
        j1_frame.pack(fill='x', pady=10)

        # 진동 이벤트
        tk.Label(
            j1_frame,
            text="📳 진동센서 이벤트 (HR/Status)",
            font=("맑은 고딕", 11, "bold"),
            bg="white",
            fg="#E67E22"
        ).pack(anchor='w', pady=(0, 5))

        vib_frame = tk.Frame(j1_frame, bg="white")
        vib_frame.pack(fill='x', pady=5)

        tk.Button(
            vib_frame,
            text="진동 측정 시작\n(ChkVibration=True)",
            font=("맑은 고딕", 10),
            bg="#3498DB",
            fg="white",
            command=lambda: self.send_vibration_event(True),
            relief=tk.FLAT,
            padx=10,
            pady=10
        ).pack(side='left', expand=True, fill='x', padx=(0, 5))

        tk.Button(
            vib_frame,
            text="진동 측정 종료\n(ChkVibration=False)",
            font=("맑은 고딕", 10),
            bg="#95A5A6",
            fg="white",
            command=lambda: self.send_vibration_event(False),
            relief=tk.FLAT,
            padx=10,
            pady=10
        ).pack(side='left', expand=True, fill='x', padx=(5, 0))

        # 볶음 투입 이벤트
        tk.Label(
            j1_frame,
            text="🍳 볶음 투입 이벤트 (HR/Status → ProcessType='투입')",
            font=("맑은 고딕", 11, "bold"),
            bg="white",
            fg="#E67E22"
        ).pack(anchor='w', pady=(15, 5))

        pot_frame = tk.Frame(j1_frame, bg="white")
        pot_frame.pack(fill='x', pady=5)

        recipes = ["짜장", "짬뽕", "볶음밥", "우동"]

        # POT1 프레임
        pot1_frame = tk.Frame(j1_frame, bg="white")
        pot1_frame.pack(fill='x', pady=5)

        tk.Label(
            pot1_frame,
            text="POT1 (왼쪽, PTNum=0):",
            font=("맑은 고딕", 10),
            bg="white"
        ).pack(side='left', padx=(0, 10))

        for recipe in recipes:
            tk.Button(
                pot1_frame,
                text=recipe,
                font=("맑은 고딕", 9),
                bg="#F39C12",
                fg="white",
                command=lambda r=recipe: self.send_stirfry_event("0", r),
                relief=tk.FLAT,
                padx=8,
                pady=5
            ).pack(side='left', padx=2)

        # POT2 프레임
        pot2_frame = tk.Frame(j1_frame, bg="white")
        pot2_frame.pack(fill='x', pady=5)

        tk.Label(
            pot2_frame,
            text="POT2 (오른쪽, PTNum=1):",
            font=("맑은 고딕", 10),
            bg="white"
        ).pack(side='left', padx=(0, 10))

        for recipe in recipes:
            tk.Button(
                pot2_frame,
                text=recipe,
                font=("맑은 고딕", 9),
                bg="#E67E22",
                fg="white",
                command=lambda r=recipe: self.send_stirfry_event("1", r),
                relief=tk.FLAT,
                padx=8,
                pady=5
            ).pack(side='left', padx=2)

        # ========================================
        # 로그 영역
        # ========================================
        log_label_frame = tk.LabelFrame(
            main_frame,
            text="📋 실행 로그 (MQTT 메시지)",
            font=("맑은 고딕", 12, "bold"),
            bg="white",
            padx=10,
            pady=10
        )
        log_label_frame.pack(fill='both', expand=True, pady=(20, 0))

        log_container = tk.Frame(log_label_frame, bg="white")
        log_container.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side='right', fill='y')

        self.log_text = tk.Text(
            log_container,
            font=("Consolas", 9),
            bg="#2C3E50",
            fg="#ECF0F1",
            yscrollcommand=scrollbar.set,
            wrap='word'
        )
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.log_text.yview)

        # 버튼 프레임
        btn_frame = tk.Frame(self.root, bg="white")
        btn_frame.pack(fill='x', padx=20, pady=10)

        tk.Button(
            btn_frame,
            text="로그 지우기",
            font=("맑은 고딕", 10),
            bg="#95A5A6",
            fg="white",
            command=self.clear_log,
            relief=tk.FLAT,
            padx=15,
            pady=8
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame,
            text="종료",
            font=("맑은 고딕", 10),
            bg="#E74C3C",
            fg="white",
            command=self.root.quit,
            relief=tk.FLAT,
            padx=15,
            pady=8
        ).pack(side='right', padx=5)

    def log(self, message, color="#ECF0F1"):
        """로그 출력"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')
        print(f"[{timestamp}] {message}")

    def clear_log(self):
        """로그 지우기"""
        self.log_text.delete('1.0', 'end')

    def connect_mqtt(self):
        """MQTT 연결"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.log(f"❌ MQTT 연결 실패: {e}")
            self.mqtt_status.config(text=f"MQTT: ❌ 연결 실패", fg="#E74C3C")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT 연결 콜백"""
        if rc == 0:
            self.mqtt_connected = True
            self.mqtt_status.config(text=f"MQTT: ✅ 연결됨 ({MQTT_BROKER})", fg="#27AE60")
            self.log(f"✅ MQTT 브로커 연결 성공: {MQTT_BROKER}")
        else:
            self.mqtt_status.config(text=f"MQTT: ❌ 연결 실패 (code {rc})", fg="#E74C3C")
            self.log(f"❌ MQTT 연결 실패: code {rc}")

    def publish_mqtt(self, topic, payload):
        """MQTT 메시지 발행"""
        if not self.mqtt_connected:
            self.log("⚠ MQTT 연결 안 됨")
            return False

        try:
            msg_str = json.dumps(payload, ensure_ascii=False, indent=2)
            self.mqtt_client.publish(topic, msg_str)
            self.log(f"📤 Topic: {topic}")
            self.log(f"📦 Payload:\n{msg_str}")
            self.log("-" * 60)
            return True
        except Exception as e:
            self.log(f"❌ 발행 실패: {e}")
            return False

    # ========================================
    # 이벤트 트리거 함수들
    # ========================================

    def send_vibration_event(self, chk_value):
        """진동 측정 이벤트 (HR/Status)"""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "Status": [
                {
                    "DeviceNum": "1",  # Jetson #1
                    "ChkVibration": chk_value
                }
            ]
        }

        action = "시작" if chk_value else "종료"
        self.log(f"📳 진동 측정 {action} 이벤트 발송")
        self.publish_mqtt("HR/Status", payload)

    def send_stirfry_event(self, pt_num, recipe):
        """볶음 투입 이벤트 (HR/Status)"""
        pot_name = "POT1(왼쪽)" if pt_num == "0" else "POT2(오른쪽)"

        payload = {
            "timestamp": datetime.now().isoformat(),
            "Status": [
                {
                    "DeviceNum": "1",  # Jetson #1 (볶음솥)
                    "PTNum": pt_num,   # 0=왼쪽(POT1), 1=오른쪽(POT2)
                    "ProcessType": "투입",  # 투입 시 토스트 표시
                    "NowRecipe": recipe,
                    "Mode": "AUTO",
                    "RunningTime": "0분 0초",
                    "TargetTime": "5분 0초",
                    "Potstatus": {
                        "PT_Temp": 0,
                        "PT_Level": 0,
                        "PT_Power": "False",
                        "RT_Speed": 0,
                        "RT_Dir": 0
                    }
                }
            ]
        }

        self.log(f"🍳 {pot_name} '{recipe}' 투입 이벤트 발송")
        self.publish_mqtt("HR/Status", payload)

    def run(self):
        """메인 루프 실행"""
        self.root.mainloop()

    def __del__(self):
        """종료 시 MQTT 연결 해제"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

if __name__ == "__main__":
    print("=" * 70)
    print("🎬 과제보고서용 실제 MQTT 이벤트 시뮬레이터 시작")
    print("=" * 70)
    print()
    print("사용법:")
    print("1. Jetson GUI (JETSON1_INTEGRATED.py)를 먼저 실행")
    print("2. 이 스크립트를 실행")
    print("3. 원하는 이벤트 버튼 클릭")
    print("4. Jetson GUI에 실제 토스트가 표시됨!")
    print("5. 스크린샷 캡쳐")
    print()
    print("=" * 70)
    print()

    app = RealMQTTEventSimulator()
    app.run()
