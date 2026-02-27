#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
mkdir -p "${BUILD_DIR}"

SRC_POST="${SCRIPT_DIR}/src/observe_postprocess.cpp"
OUT_POST="${BUILD_DIR}/libobserve_postprocess.so"
g++ -O3 -std=c++17 -fPIC -shared "${SRC_POST}" -o "${OUT_POST}"
echo "Built: ${OUT_POST}"

SRC_OVR="${SCRIPT_DIR}/src/observe_overlay.cpp"
OUT_OVR="${BUILD_DIR}/libobserve_overlay.so"
read -r -a OPENCV_FLAGS <<< "$(pkg-config --cflags --libs opencv4)"
if [[ ! -d /usr/local/include/opencv4 && -d /usr/include/opencv4 ]]; then
  OPENCV_FLAGS=("-I/usr/include/opencv4" "${OPENCV_FLAGS[@]}")
fi
g++ -O3 -std=c++17 -fPIC -shared "${SRC_OVR}" -o "${OUT_OVR}" "${OPENCV_FLAGS[@]}"
echo "Built: ${OUT_OVR}"
