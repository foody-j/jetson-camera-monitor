#!/usr/bin/env python3
"""
POT 데이터 수집 테스트 스크립트
MQTT 메시지를 전송해서 실제 수집이 잘 되는지 확인

사용법:
    python3 test_pot_collection.py --pot 1 --food chicken --duration 10
    python3 test_pot_collection.py --pot 2 --food shrimp --duration 15
"""

import paho.mqtt.client as mqtt
import time
import argparse
import sys
import os

# MQTT 설정
MQTT_BROKER = "192.168.0.100"
MQTT_PORT = 1883

# 토픽
TOPIC_POT1_FOOD = "frying/pot1/food_type"
TOPIC_POT1_CONTROL = "frying/pot1/control"
TOPIC_POT2_FOOD = "frying/pot2/food_type"
TOPIC_POT2_CONTROL = "frying/pot2/control"

def test_pot_collection(pot_num, food_type, duration_sec):
    """POT 데이터 수집 테스트"""

    print(f"\n{'='*60}")
    print(f"POT{pot_num} 데이터 수집 테스트 시작")
    print(f"{'='*60}")
    print(f"음식 종류: {food_type}")
    print(f"수집 시간: {duration_sec}초")
    print(f"MQTT 브로커: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"{'='*60}\n")

    # MQTT 클라이언트 생성
    client = mqtt.Client(client_id=f"test_pot{pot_num}_client")

    try:
        print(f"[1/5] MQTT 브로커 연결 중...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(1)
        print("✓ 연결 성공\n")

        # POT 선택
        if pot_num == 1:
            food_topic = TOPIC_POT1_FOOD
            control_topic = TOPIC_POT1_CONTROL
            data_dir = os.path.expanduser("~/AI_Data/pot1")
        else:
            food_topic = TOPIC_POT2_FOOD
            control_topic = TOPIC_POT2_CONTROL
            data_dir = os.path.expanduser("~/AI_Data/pot2")

        # 기존 세션 개수 확인
        before_sessions = []
        if os.path.exists(data_dir):
            before_sessions = [d for d in os.listdir(data_dir) if d.startswith("session_")]
        print(f"[2/5] 시작 전 세션 개수: {len(before_sessions)}")

        # 투입 신호 (food_type 전송)
        print(f"\n[3/5] 투입 신호 전송: {food_type}")
        client.publish(food_topic, food_type, qos=1)
        print(f"  → 토픽: {food_topic}")
        print(f"  → 메시지: {food_type}")
        print("  → Jetson2가 데이터 수집을 시작해야 합니다...")

        # 데이터 수집 대기
        print(f"\n[4/5] {duration_sec}초 동안 데이터 수집 중...")
        for i in range(duration_sec):
            remaining = duration_sec - i
            print(f"  남은 시간: {remaining}초...", end='\r')
            time.sleep(1)
        print("\n")

        # 배출 신호 (stop 전송)
        print(f"[5/5] 배출 신호 전송: stop")
        client.publish(control_topic, "stop", qos=1)
        print(f"  → 토픽: {control_topic}")
        print(f"  → 메시지: stop")
        print("  → Jetson2가 데이터 수집을 종료해야 합니다...")

        # 결과 확인 (배출 후 지연 시간 고려)
        print("\n배출 후 지연 종료 대기 중 (50초)...")
        time.sleep(52)

        print(f"\n{'='*60}")
        print("결과 확인")
        print(f"{'='*60}")

        if os.path.exists(data_dir):
            after_sessions = [d for d in os.listdir(data_dir) if d.startswith("session_")]
            new_sessions = [s for s in after_sessions if s not in before_sessions]

            print(f"✓ 새로운 세션: {len(new_sessions)}개")

            if new_sessions:
                for session in new_sessions:
                    session_path = os.path.join(data_dir, session)
                    print(f"\n세션: {session}")

                    # 음식 종류 폴더 확인
                    food_dirs = [d for d in os.listdir(session_path) if os.path.isdir(os.path.join(session_path, d))]
                    if food_dirs:
                        for food_dir in food_dirs:
                            food_path = os.path.join(session_path, food_dir)
                            print(f"  음식: {food_dir}")

                            # 카메라 폴더 확인
                            cam_dirs = [d for d in os.listdir(food_path) if d.startswith("camera_")]
                            for cam_dir in sorted(cam_dirs):
                                cam_path = os.path.join(food_path, cam_dir)
                                images = [f for f in os.listdir(cam_path) if f.endswith('.jpg')]
                                print(f"    {cam_dir}: {len(images)}장")

                            # 메타데이터 확인
                            meta_path = os.path.join(food_path, "meta")
                            if os.path.exists(meta_path):
                                meta_files = [f for f in os.listdir(meta_path) if f.endswith('.json')]
                                print(f"    meta: {len(meta_files)}개")

                    # session_info.json 확인
                    info_file = os.path.join(session_path, "session_info.json")
                    if os.path.exists(info_file):
                        import json
                        with open(info_file, 'r') as f:
                            info = json.load(f)
                        print(f"  총 프레임: {info.get('total_frames', 0)}장")
                        print(f"  수집 시간: {info.get('duration_sec', 0):.1f}초")

                print(f"\n✅ 테스트 성공! 데이터가 정상적으로 저장되었습니다.")
            else:
                print(f"\n⚠️  경고: 새로운 세션이 생성되지 않았습니다.")
                print(f"  Jetson2가 실행 중인지 확인하세요:")
                print(f"  sudo systemctl status jetson2-monitor")
        else:
            print(f"\n❌ 오류: 데이터 디렉토리가 생성되지 않았습니다.")
            print(f"  경로: {data_dir}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        client.loop_stop()
        client.disconnect()
        print(f"\n{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description="POT 데이터 수집 테스트")
    parser.add_argument("--pot", type=int, choices=[1, 2], required=True,
                        help="POT 번호 (1 또는 2)")
    parser.add_argument("--food", type=str, default="chicken",
                        help="음식 종류 (기본값: chicken)")
    parser.add_argument("--duration", type=int, default=10,
                        help="수집 시간 (초, 기본값: 10)")

    args = parser.parse_args()

    test_pot_collection(args.pot, args.food, args.duration)

if __name__ == "__main__":
    main()
