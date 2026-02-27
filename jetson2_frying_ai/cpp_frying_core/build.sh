#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
SRC="${SCRIPT_DIR}/src/frying_postprocess.cpp"
OUT="${BUILD_DIR}/libfrying_postprocess.so"

mkdir -p "${BUILD_DIR}"
g++ -O3 -std=c++17 -fPIC -shared "${SRC}" -o "${OUT}"
echo "Built: ${OUT}"
