#!/usr/bin/env bash
set -euo pipefail

# Momo Song v4 起動スクリプト

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Momo Song v4 を起動しています..."

# 仮想環境の確認
if [ -x ".venv/bin/python" ]; then
    VENV_DIR=".venv"
elif [ -x "venv/bin/python" ]; then
    # 開発初期版で作成した仮想環境との後方互換。
    VENV_DIR="venv"
    echo "既存の venv を使用します（新規インストール時は .venv を使用します）。"
else
    echo "Python仮想環境がありません。先に ./install.sh を実行してください。" >&2
    exit 1
fi

# 仮想環境の有効化
source "$VENV_DIR/bin/activate"

# 依存関係は初回セットアップ時に requirements-cpu.txt または
# requirements-cuda.txt から導入してください。起動のたびに変更しません。
if ! python -c 'import fastapi, llama_cpp, uvicorn' >/dev/null 2>&1; then
    echo "依存パッケージが不足しています。READMEのセットアップ手順を実行してください。" >&2
    exit 1
fi

# サーバーの起動
echo "サーバーを起動しています..."
echo "ブラウザで http://localhost:64653 にアクセスしてください"
python music_server.py
