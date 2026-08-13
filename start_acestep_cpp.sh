#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ACESTEP_CPP_DIR="${ACESTEP_CPP_DIR:-$SCRIPT_DIR/vendor/acestep.cpp}"
ACESTEP_CPP_MODELS="${ACESTEP_CPP_MODELS:-$ACESTEP_CPP_DIR/models}"
backend="${ACESTEP_CPP_BACKEND:-cuda}"
gpu="${ACESTEP_CPP_GPU:-0}"
port="${ACESTEP_CPP_PORT:-8085}"
keep_loaded="${ACESTEP_CPP_KEEP_LOADED:-0}"

usage() {
  cat <<'EOF'
Usage: ./start_acestep_cpp.sh [--backend cuda|cpu] [--gpu INDEX] [--port PORT] [--keep-loaded]

  --backend cuda  12GB VRAM向けCUDA構成（既定）
  --backend cpu   x86 CPU専用バイナリ
  --gpu INDEX     CUDAで使用するGPU番号（既定: 0）
  --port PORT     待受ポート（既定: 8085）
  --keep-loaded   使用モデルをVRAMに常駐（モデル変更時は再起動が必要）
EOF
}

while (($#)); do
  case "$1" in
    --backend)
      [[ $# -ge 2 ]] || { echo "--backend requires a value" >&2; exit 2; }
      backend="$2"
      shift 2
      ;;
    --gpu)
      [[ $# -ge 2 ]] || { echo "--gpu requires a value" >&2; exit 2; }
      gpu="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || { echo "--port requires a value" >&2; exit 2; }
      port="$2"
      shift 2
      ;;
    --keep-loaded)
      keep_loaded="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$backend" in
  cuda)
    server="$ACESTEP_CPP_DIR/build/ace-server"
    export CUDA_VISIBLE_DEVICES="$gpu"
    ;;
  cpu)
    server="$ACESTEP_CPP_DIR/build-cpu/ace-server"
    # CPU版でCUDA設定が誤って引き継がれないようにする。
    unset CUDA_VISIBLE_DEVICES || true
    ;;
  *)
    echo "Unsupported backend: $backend (cuda or cpu)" >&2
    exit 2
    ;;
esac

if [[ ! -x "$server" ]]; then
  echo "ace-server not found: $server" >&2
  if [[ "$backend" == "cpu" ]]; then
    echo "Run ./build_acestep_cpp_cpu.sh first." >&2
  fi
  exit 1
fi

server_args=(
  --models "$ACESTEP_CPP_MODELS"
  --host 127.0.0.1
  --port "$port"
  --max-batch 1
  --vae-chunk 512
  --vae-overlap 64
)
if [[ "$keep_loaded" == "1" ]]; then
  server_args+=(--keep-loaded)
fi

echo "Starting acestep.cpp backend=$backend port=$port keep_loaded=$keep_loaded"
exec "$server" "${server_args[@]}"
