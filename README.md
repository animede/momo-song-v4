# Momo Song v4

[English](README.en.md) | 日本語

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

歌詞生成、ACE-Step 1.5による作曲、背景と音響連動演出を統合したWebアプリケーションです。

## GUI Example

![Momo Song GUI example](docs/images/gui-example.png)

## 主な機能

- ローカルGemma 4またはOpenAI互換APIによる歌詞・曲解説生成
- Local acestep.cppまたはRemote ACE-Step 1.5による音楽生成
- 曲に合う背景の自動選択、ランダム選択、手動選択
- 音量・波形・周波数成分へ反応する前景演出
- 連続再生する「ループ生成」と、画像クリックによる即時停止
- セッション単位の20行の生成履歴、個別保存・削除・再生・一括ダウンロード

Local acestep.cppでは画像生成を行わず、選択した背景を維持します。Remoteでは設定した
画像生成APIを利用できます。

## セットアップ

Python 3.10〜3.12を使用します。インストーラはMomo Song v4のGitHub Releasesから
検証済みビルド済みパッケージを取得します。

Linux CUDA（例: CUDA 12.5）:

```bash
./install.sh --backend cuda --cuda cu125
```

Windows PowerShell:

```powershell
.\install.ps1 -Backend cuda -Cuda cu125
```

CPU版は `--backend cpu`（PowerShellでは `-Backend cpu`）を指定します。

- Python仮想環境は `.venv` に作成されます。
- `llama-cpp-python` 0.3.34は公式ホイールをRelease用ZIPへ再梱包したものを取得します。
- `--only-binary=:all:`を使用し、対応ホイールがない場合の暗黙のソースビルドを禁止します。
- Linux版acestep.cppは固定した上流ソースリビジョンからRelease作成時にビルドします。
- Linux CUDA版は動作確認済みビルドを専用スクリプトでパッケージ化してReleaseへ添付します。
- Windows版acestep.cppは上流README掲載のビルド済み配布をRelease用ZIPへ再梱包します。
- ACE-Stepを別途用意する場合は `--acestep skip` / `-AceStep skip` を指定できます。
- インストーラはRelease添付のSHA-256と照合し、取得元を `vendor/.sources/` に記録します。
- 公式ホイールの対応範囲はLinuxがCPU/CUDA 12.1〜12.5、WindowsがCPU/CUDA 12.4〜12.5です。
- モデルウェイトは同梱・自動取得されません。

> Windows用依存物の取得には対応していますが、現行のACEサーバー自動再起動処理はLinuxの
> `ss`、`/proc`、シェルスクリプトを使用します。WindowsでLocalモードを完全自動運用する
> 対応は未完了です。

## モデル配置

ローカルLLMの既定パス:

```text
models/gemma-4-E4B-it-Q4_K_M.gguf
```

acestep.cppのモデルは `vendor/acestep.cpp/models/` に配置します。既定構成は次の通りです。

- LM: `acestep-5Hz-lm-1.7B-Q8_0.gguf`
- TURBO-Q4: `acestep-v15-turbo-Q4_K_M.gguf`
- TURBO-Q8: `acestep-v15-turbo-Q8_0.gguf`
- XL TURBO: `acestep-v15-xl-turbo-Q4_K_M.gguf`

モデルウェイトには各配布元のライセンスと利用条件が適用されます。

## 起動

Linuxでは次のいずれかを使用します。

```bash
./start.sh
# または
.venv/bin/python music_server.py
```

ブラウザで <http://localhost:64653> を開きます。既定の音楽生成バックエンドは
`Local acestep.cpp`、モデルはTURBO-Q4、演出は音量リングです。

ローカルACEサーバーを手動起動する場合:

```bash
./start_acestep_cpp.sh --backend cuda --gpu 0
./start_acestep_cpp.sh --backend cpu
```

## ローカルモデルとVRAMモード

- **TURBO-Q4（標準／STRICT時6GB～）**: 既定モデル
- **TURBO-Q8（高品質／12GB～）**: 12GB以上の目安
- **XL TURBO（超高品質／16GB～）**: 16GB以上の目安
- **モデル常駐（高速）**: 同じ設定での連続生成を高速化
- **STRICT（省VRAM）**: モデル解放を増やしてVRAMを節約

作詞と作曲は逐次方式でGPUを共有します。モデルまたはVRAMモードを変えると、次回生成直前に
ACEサーバーを必要に応じて再起動します。必要VRAMは環境、ドライバー、曲長でも変化します。

## Remoteバックエンド

Remote利用時だけ、次のサービスを環境変数で指定します。

- `LLM_API_URL`: OpenAI互換Chat Completions API
- `ACE_STEP_API_URL`: `/release_task`と`/query_result`を持つACE-Step API
- `IMAGE_API_URL`: `/text2image`を持つ画像生成API

設定例は[.env.example](.env.example)を参照してください。アプリは`.env`を自動読込しないため、
値は起動環境へ設定してください。

## ドキュメント

- [クイックスタート](QUICK_START.md)
- [ユーザーガイド](USER_GUIDE.md)
- [FAQ](FAQ.md)
- [技術概要](DOCUMENTATION.md)
- [APIリファレンス](API_REFERENCE.md)
- [デプロイメントガイド](DEPLOYMENT.md)
- [セキュリティポリシー](SECURITY.md)

## ライセンス

Momo Song v4は[Apache License 2.0](LICENSE)で提供されます。外部ライブラリ、ビルド済み
バイナリ、モデルウェイトには、それぞれの上流ライセンスが適用されます。再配布物の情報は
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。
