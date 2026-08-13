# Momo Song v4 デプロイメントガイド

## 対象環境

- Python 3.10〜3.12
- x86-64 LinuxまたはWindows
- ローカルCUDA利用時はNVIDIA GPUと対応ドライバー
- モデルを格納できるディスク容量

初期インストーラはビルド済み依存物をMomo Song v4 GitHub Releasesから取得し、同じReleaseの
SHA-256ファイルで検証します。モデルウェイトと外部サービスはそれぞれの利用条件を確認してください。

## インストール

```bash
# Linux CUDA（例: CUDA 12.5）
./install.sh --backend cuda --cuda cu125

# Linux CPU
./install.sh --backend cpu
```

```powershell
# Windows PowerShell
.\install.ps1 -Backend cuda -Cuda cu125
```

Linux/Windowsとも既定でGitHub Releaseのビルド済みacestep.cppを取得します。ソースから
構築する場合は `--acestep source`、別途用意する場合は `--acestep skip`を指定します。

## 環境変数

`.env.example`は設定例です。アプリは`.env`を自動読込しないため、シェル、サービス管理、
または起動コマンドから環境へ設定してください。

| 変数 | 既定値 | 用途 |
|---|---|---|
| `MOMO_HOST` | `127.0.0.1` | GUI待受アドレス |
| `MOMO_PORT` | `64653` | GUI待受ポート |
| `MOMO_RELOAD` | `0` | 開発用自動リロード |
| `LOCAL_LLM_MODEL` | `models/gemma-4-E4B-it-Q4_K_M.gguf` | ローカルGemma |
| `LOCAL_LLM_MAIN_GPU` | `0` | LLM用GPU |
| `LOCAL_LLM_GPU_LAYERS` | `-1` | GPUへ載せるレイヤー数 |
| `LOCAL_LLM_N_CTX` | `8192` | コンテキスト長 |
| `ACESTEP_CPP_DIR` | `vendor/acestep.cpp` | acestep.cpp配置先 |
| `ACESTEP_CPP_GPU` | `0` | ACE-Step用GPU |
| `ACESTEP_CPP_URL` | `http://127.0.0.1:8085` | ローカルACEサーバー |
| `LLM_API_URL` | `http://127.0.0.1:8080/v1` | Remote LLM |
| `LLM_API_KEY` | `local-not-required` | Remote LLMキー |
| `LLM_MODEL` | 空欄 | Remote LLMモデル |
| `ACE_STEP_API_URL` | `http://127.0.0.1:8001` | Remote ACE-Step |
| `IMAGE_API_URL` | `http://127.0.0.1:64656` | Remote画像生成 |

## モデル配置

ローカルLLMの既定パスは `models/gemma-4-E4B-it-Q4_K_M.gguf` です。ACE-Stepモデルは
`vendor/acestep.cpp/models/` に配置します。必要なモデル名はREADMEを参照してください。

## 起動

```bash
.venv/bin/python music_server.py
```

```powershell
.\.venv\Scripts\python.exe music_server.py
```

既定ではローカルホストだけから接続できます。LAN公開が必要な場合に限り
`MOMO_HOST=0.0.0.0`を設定し、ファイアウォールとリバースプロキシでアクセスを制限してください。

## セキュリティ上の注意

- 本アプリには利用者認証やレート制限がありません。インターネットへ直接公開しないでください。
- APIキー、モデル、生成音声、ログ、`vendor/`をGitへ追加しないでください。
- HTTPS終端と認証が必要な場合は、信頼できるリバースプロキシを前段に配置してください。
- 公開前に `python3 scripts/check_public_repo.py` を実行してください。
