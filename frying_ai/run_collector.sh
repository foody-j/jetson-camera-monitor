#!/bin/bash
# 데이터 수집기 실행 스크립트

cd "$(dirname "$0")"
echo "🍗 튀김 데이터 수집기 시작..."
python3 frying_data_collector.py
