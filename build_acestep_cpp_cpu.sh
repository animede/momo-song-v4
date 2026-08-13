#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ACESTEP_CPP_DIR="${ACESTEP_CPP_DIR:-$SCRIPT_DIR/vendor/acestep.cpp}"
BUILD_DIR="${ACESTEP_CPP_CPU_BUILD_DIR:-$ACESTEP_CPP_DIR/build-cpu}"

cmake -S "$ACESTEP_CPP_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=OFF \
  -DGGML_METAL=OFF \
  -DGGML_VULKAN=OFF \
  -DGGML_NATIVE=ON
cmake --build "$BUILD_DIR" --config Release -j "$(nproc)"

echo "CPU版を構築しました: $BUILD_DIR/ace-server"
