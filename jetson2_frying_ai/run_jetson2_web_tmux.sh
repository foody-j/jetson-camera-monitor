#!/usr/bin/env bash
set -euo pipefail

WORKDIR="/home/hr_dku_002/jetson-food-ai/jetson2_frying_ai"
PYTHON="/usr/bin/python3"
APP="${WORKDIR}/JETSON2_web.py"

cd "${WORKDIR}"

while true; do
  ${PYTHON} "${APP}"
  echo "[run] JETSON2_web.py exited. Restarting in 2s..."
  sleep 2
done
