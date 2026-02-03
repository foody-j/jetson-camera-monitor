#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish a short MQTT sequence to test Jetson2_web data-collection flow."""

import json
import os
import time
from datetime import datetime

import paho.mqtt.client as mqtt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(path="config_jetson2_web.json"):
    with open(os.path.join(SCRIPT_DIR, path), "r", encoding="utf-8") as f:
        return json.load(f)


def publish(client, topic, payload):
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)
    client.publish(topic, payload)
    print(f"[PUB] {topic}: {payload}")


def build_status(process_left, process_right, rb_motion=0, recipe_left="chicken", recipe_right="shrimp"):
    return {
        "Status": [
            {
                "DeviceNum": "0",
                "PTNum": "0",
                "NowRecipe": recipe_left,
                "ProcessType": process_left,
                "RunningTime": "00:00:10",
                "TargetTime": "00:03:00",
                "RBstatus": "OK",
                "Potstatus": {"PT_Temp": 170, "PT_Power": "True", "PT_Level": 0, "RT_Speed": 0, "RT_Dir": 0},
            },
            {
                "DeviceNum": "0",
                "PTNum": "1",
                "NowRecipe": recipe_right,
                "ProcessType": process_right,
                "RunningTime": "00:00:12",
                "TargetTime": "00:03:00",
                "RBstatus": "OK",
                "Potstatus": {"PT_Temp": 168, "PT_Power": "True", "PT_Level": 0, "RT_Speed": 0, "RT_Dir": 0},
            },
        ],
        "RBMotion": rb_motion,
        "VibrationRequest": False,
    }


def main():
    cfg = load_config()
    broker = cfg.get("mqtt_broker", "localhost")
    port = int(cfg.get("mqtt_port", 1883))

    topic_status = cfg.get("mqtt_topic_robot_status", "HR/Status")
    topic_pot1_food = cfg.get("mqtt_topic_frying_pot1_food_type", "frying/pot1/food_type")
    topic_pot2_food = cfg.get("mqtt_topic_frying_pot2_food_type", "frying/pot2/food_type")

    client = mqtt.Client()
    client.connect(broker, port, 60)

    # 1) food type triggers
    publish(client, topic_pot1_food, "chicken")
    publish(client, topic_pot2_food, "shrimp")
    time.sleep(1)

    # 2) 투입
    publish(client, topic_status, build_status("투입", "투입", rb_motion=1))
    time.sleep(2)

    # 3) 조리
    publish(client, topic_status, build_status("조리", "조리", rb_motion=2))
    time.sleep(2)

    # 4) 배출
    publish(client, topic_status, build_status("배출", "배출", rb_motion=0))

    print("[DONE] MQTT test sequence sent.")


if __name__ == "__main__":
    main()
