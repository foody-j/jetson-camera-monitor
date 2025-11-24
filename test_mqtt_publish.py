#!/usr/bin/env python3
"""
MQTT 토픽 테스트 발행 툴
"""

import paho.mqtt.client as mqtt
import json
import sys
from datetime import datetime

def publish_test_message(broker, port, topic, message):
    """Test MQTT message publishing"""

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"✓ MQTT Broker 연결 성공: {broker}:{port}")
        else:
            print(f"✗ MQTT Broker 연결 실패: {rc}")

    def on_publish(client, userdata, mid):
        print(f"✓ 메시지 발행 완료 (mid={mid})")

    # Create client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish

    try:
        # Connect
        print(f"\n[연결] {broker}:{port}")
        client.connect(broker, port, 60)
        client.loop_start()

        # Prepare message
        if isinstance(message, str):
            payload = message
        else:
            payload = json.dumps(message, ensure_ascii=False)

        # Publish
        print(f"[발행] 토픽: {topic}")
        print(f"[내용] {payload}")
        result = client.publish(topic, payload, qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"✓ 발행 성공!")
        else:
            print(f"✗ 발행 실패: {result.rc}")

        # Wait a bit
        import time
        time.sleep(1)

        client.loop_stop()
        client.disconnect()

    except Exception as e:
        print(f"✗ 오류: {e}")
        return False

    return True


def main():
    """Main function"""
    print("=" * 60)
    print("MQTT 토픽 테스트 발행 툴")
    print("=" * 60)

    # Get broker info
    broker = input("\nMQTT Broker IP (기본: localhost): ").strip() or "localhost"
    port = input("MQTT Broker Port (기본: 1883): ").strip() or "1883"
    port = int(port)

    # Select message type
    print("\n=== 메시지 타입 선택 ===")
    print("1. Jetson1 AI 모드 (jetson1/system/ai_mode)")
    print("2. Jetson2 AI 모드 (jetson2/system/ai_mode)")
    print("3. Jetson2 바구니 상태 (jetson2/observe/status)")
    print("4. 볶음 음식 종류 - 자동 시작 (stirfry/food_type)")
    print("5. 볶음 종료 신호 (stirfry/control)")
    print("6. 튀김 음식 종류 - 자동 시작 (frying/food_type)")
    print("7. 튀김 종료 신호 (frying/control)")
    print("8. 커스텀 토픽")

    choice = input("\n선택 (1-8): ").strip()

    if choice == "1":
        topic = "jetson1/system/ai_mode"
        status = input("AI 상태 (ON/OFF): ").strip().upper()
        message = {
            "device_id": "jetson1",
            "device_name": "Jetson1_StirFry_Station",
            "message": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    elif choice == "2":
        topic = "jetson2/system/ai_mode"
        status = input("AI 상태 (ON/OFF): ").strip().upper()
        message = {
            "device_id": "jetson2",
            "device_name": "Jetson2_Frying_Station",
            "message": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    elif choice == "3":
        topic = "jetson2/observe/status"
        status = input("바구니 상태 (예: LEFT:BASKET_IN): ").strip()
        message = {
            "device_id": "jetson2",
            "message": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    elif choice == "4":
        topic = "stirfry/food_type"
        food_type = input("음식 종류 (예: 볶음밥, 짜장, 짬뽕): ").strip() or "테스트볶음밥"
        message = food_type
        print(f"\n>>> Jetson1이 '{food_type}' 수신 후 자동으로 녹화 시작됩니다.")

    elif choice == "5":
        topic = "stirfry/control"
        message = "stop"
        print(f"\n>>> Jetson1이 녹화 중지 신호를 받아 자동으로 녹화를 종료합니다.")

    elif choice == "6":
        topic = "frying/food_type"
        food_type = input("음식 종류 (예: 치킨, 새우, 감자): ").strip() or "테스트치킨"
        message = food_type
        print(f"\n>>> Jetson2가 '{food_type}' 수신 후 자동으로 수집 시작됩니다 (튀김솥+바스켓 모두).")

    elif choice == "7":
        topic = "frying/control"
        message = "stop"
        print(f"\n>>> Jetson2가 수집 중지 신호를 받아 자동으로 수집을 종료합니다.")

    elif choice == "8":
        topic = input("토픽: ").strip()
        message_text = input("메시지 (JSON 또는 텍스트): ").strip()
        try:
            message = json.loads(message_text)
        except:
            message = message_text

    else:
        print("잘못된 선택입니다.")
        return

    # Publish
    print("\n" + "=" * 60)
    success = publish_test_message(broker, port, topic, message)
    print("=" * 60)

    if success:
        print("\n✓ 테스트 완료!")
        print(f"\n로봇 PC에서 확인:")
        print(f"  mosquitto_sub -h localhost -t '{topic}' -v")
    else:
        print("\n✗ 테스트 실패")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
    except Exception as e:
        print(f"\n오류: {e}")
