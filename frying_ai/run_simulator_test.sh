#!/bin/bash
# 센서 시뮬레이터 테스트

cd "$(dirname "$0")"
echo "🌡️ 센서 시뮬레이터 테스트..."
python3 sensor_simulator.py test
