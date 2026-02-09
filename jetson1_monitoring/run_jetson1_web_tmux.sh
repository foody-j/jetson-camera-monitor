#!/usr/bin/env bash
set -euo pipefail

WORKDIR="/home/hr_dku_001/jetson-food-ai/jetson1_monitoring"
PYTHON="/usr/bin/python3"
APP="${WORKDIR}/JETSON1_web.py"

cd "${WORKDIR}"

while true; do
  ${PYTHON} "${APP}"
  echo "[run] JETSON1_web.py exited. Restarting in 2s..."
  sleep 2
done
