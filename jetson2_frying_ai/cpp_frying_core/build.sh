#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
mkdir -p "${BUILD_DIR}"

SRC_FRY="${SCRIPT_DIR}/src/frying_postprocess.cpp"
OUT_FRY="${BUILD_DIR}/libfrying_postprocess.so"
g++ -O3 -std=c++17 -fPIC -shared "${SRC_FRY}" -o "${OUT_FRY}"
echo "Built: ${OUT_FRY}"

SRC_LIFT="${SCRIPT_DIR}/src/lift_tracker_core.cpp"
OUT_LIFT="${BUILD_DIR}/liblift_tracker_core.so"
g++ -O3 -std=c++17 -fPIC -shared "${SRC_LIFT}" -o "${OUT_LIFT}"
echo "Built: ${OUT_LIFT}"
