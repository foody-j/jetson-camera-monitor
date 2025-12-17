#!/usr/bin/env python3
"""
MQTT 원본 메시지 모니터링 (파싱 없이 그대로 출력)

사용법:
    python3 mqtt_raw_monitor.py [브로커IP] [토픽]

예시:
    python3 mqtt_raw_monitor.py 192.168.0.100           # HR/Status 토픽
    python3 mqtt_raw_monitor.py 192.168.0.100 "#"       # 모든 토픽
    python3 mqtt_raw_monitor.py 192.168.0.100 "frying/#"  # frying 하위 토픽
"""

import sys
import paho.mqtt.client as mqtt
from datetime import datetime

# 설정
BROKER = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.100"
TOPIC = sys.argv[2] if len(sys.argv) > 2 else "HR/Status"
PORT = 1883

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[연결] {BROKER}:{PORT}")
        print(f"[토픽] {TOPIC}")
        print("-" * 60)
        client.subscribe(TOPIC)
    else:
        print(f"[오류] 연결 실패: rc={rc}")

def on_message(client, userdata, message):
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    topic = message.topic
    payload = message.payload.decode()

    print(f"[{ts}] {topic}")
    print(payload)
    print("-" * 60)

def main():
    print("=" * 60)
    print("MQTT 원본 모니터링 (파싱 없음)")
    print("=" * 60)
    print(f"브로커: {BROKER}:{PORT}")
    print(f"토픽: {TOPIC}")
    print("Ctrl+C로 종료")
    print("=" * 60)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n종료")
    except Exception as e:
        print(f"[오류] {e}")

if __name__ == "__main__":
    main()
