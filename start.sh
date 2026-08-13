#!/bin/bash

# Momo Song v3 起動スクリプト

echo "Momo Song v3 を起動しています..."

# 仮想環境の確認
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
fi

# 仮想環境の有効化
source venv/bin/activate

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
