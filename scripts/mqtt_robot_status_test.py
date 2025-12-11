#!/usr/bin/env python3
"""
로봇 PC MQTT 상태 메시지 파싱 테스트 스크립트

사용법:
    python3 mqtt_robot_status_test.py [브로커IP]

예시:
    python3 mqtt_robot_status_test.py 192.168.0.100
    python3 mqtt_robot_status_test.py  # localhost 사용
"""

import sys
import json
import paho.mqtt.client as mqtt
from datetime import datetime

# 설정
BROKER = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT = 1883
TOPIC = "Status/#"

def parse_robot_status(payload):
    """로봇 PC 상태 메시지 파싱"""
    data = json.loads(payload)

    # Status 배열이 있는 경우 (전체 상태 메시지)
    if "Status" in data:
        print("\n" + "="*60)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 전체 상태 메시지 수신")
        print("="*60)

        for i, pot in enumerate(data["Status"]):
            parse_pot_status(pot, i)

        if "RBMotion" in data:
            print(f"\n[쉐이킹] RBMotion: {data['RBMotion']}")
    else:
        # 개별 솥 메시지
        parse_pot_status(data)

def parse_pot_status(data, index=None):
    """개별 솥 상태 파싱"""
    pot_num = data.get("PTNum", "?")
    device_num = data.get("DeviceNum", "?")  # 0: 왼쪽, 1: 오른쪽

    # 솥 타입 결정
    # Status[0] = 튀김솥 (Jetson2), Status[1] = 볶음솥 (Jetson1)
    if index is not None:
        pot_type = "튀김솥" if index == 0 else "볶음솥"
    else:
        pot_type = "?"

    position = "왼쪽" if device_num == "0" else "오른쪽" if device_num == "1" else "?"

    recipe = data.get("NowRecipe", "")
    process_type = data.get("ProcessType", "")
    rb_status = data.get("RBstatus", "")
    running_time = data.get("RunningTime", "")
    target_time = data.get("TargetTime", "")
    mode = data.get("Mode", "")

    # Potstatus 정보
    pot_status = data.get("Potstatus", {})
    temp = pot_status.get("PT_Temp", 0)
    power = pot_status.get("PT_Power", "False")
    level = pot_status.get("PT_Level", 0)

    print(f"\n[{pot_type}] [{position}] POT{pot_num}")
    print(f"  레시피: {recipe}")
    print(f"  프로세스: {process_type}")
    print(f"  상태: {rb_status}")
    print(f"  모드: {mode}")
    print(f"  온도: {temp}°C")
    print(f"  화력: {level}")
    print(f"  경과시간: {running_time} / 목표: {target_time}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] 연결 성공: {BROKER}:{PORT}")
        print(f"[MQTT] 구독 토픽: {TOPIC}")
        print("-"*60)
        client.subscribe(TOPIC)
    else:
        print(f"[MQTT] 연결 실패: rc={rc}")

def on_message(client, userdata, message):
    try:
        topic = message.topic
        payload = message.payload.decode()

        print(f"\n[토픽] {topic}")
        print(f"[원본] {payload[:200]}..." if len(payload) > 200 else f"[원본] {payload}")

        parse_robot_status(payload)

    except json.JSONDecodeError as e:
        print(f"[오류] JSON 파싱 실패: {e}")
    except Exception as e:
        print(f"[오류] {e}")

def main():
    print("="*60)
    print("로봇 PC MQTT 상태 메시지 파싱 테스트")
    print("="*60)
    print(f"브로커: {BROKER}:{PORT}")
    print(f"토픽: {TOPIC}")
    print("")
    print("매핑 정보:")
    print("  Status[0] = 튀김솥 (Jetson2)")
    print("  Status[1] = 볶음솥 (Jetson1)")
    print("  DeviceNum 0 = 왼쪽, 1 = 오른쪽")
    print("="*60)
    print("Ctrl+C로 종료")
    print("")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n종료합니다.")
    except Exception as e:
        print(f"[오류] 연결 실패: {e}")

if __name__ == "__main__":
    main()
