# Momo Song

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

音楽生成Webアプリケーション

## GUI Example

![Momo Song GUI example](docs/images/gui-example.png)

## 機能

- AI による歌詞生成
- 音楽生成（ACE-Step 1.5 REST API 使用）
- 画像生成（SDXL使用）
- 自動生成機能
- ボーカル版/インストゥルメンタル版の選択
- 生成パラメータの詳細設定

## セットアップ

1. 自動インストーラを実行します。依存バイナリはこのリポジトリに複製せず、
   それぞれの上流配布元から直接取得します。

Linux（CUDA 12.5）:

```bash
./install.sh --backend cuda --cuda cu125
```

Windows PowerShell（CUDA 12.5）:

```powershell
.\install.ps1 -Backend cuda -Cuda cu125
```

CPU版は `--backend cpu`（PowerShellでは `-Backend cpu`）を指定します。
仮想環境は `.venv` に作成されます。

- `llama-cpp-python` は abetlen 公式ホイールインデックスから取得します。
- ソースビルドへの暗黙の切替を禁止しているため、対応ホイールがない環境では
  エラーで停止します。
- Windows版 `acestep.cpp` は上流README掲載のビルド済み配布元から直接取得します。
- 上流にはLinux版ビルド済み配布がないため、Linuxでは公式GitHubソースを取得して
  ローカルビルドします。`--acestep skip` で省略できます。
- 取得元とSHA-256（ダウンロード物）は `vendor/.sources/` に記録されます。

手動でインストールする場合:

CPU版:

```bash
python -m pip install -r requirements-cpu.txt
```

CUDA版（例: CUDA 12.5対応ホイール）:

```bash
python -m pip install -r requirements-cuda.txt \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu125
```

CUDAホイールの対応バージョンはllama-cpp-python公式配布を確認してください。

2. `.env.example` を参考に環境変数を設定します。ローカル構成ではAPIキーは不要です。

3. Remoteモードを使用する場合だけ、ACE-Step、画像生成、OpenAI互換APIのURLを環境変数で指定します。

4. サーバーの起動：
```bash
python music_server.py
```

5. ブラウザで <http://localhost:64653> にアクセス

## ファイル構成

- `music_server.py`: FastAPIサーバー（メイン）
- `music.py`: 音楽生成ロジック
- `openai_chat.py`: OpenAI API ラッパー
- `create_image_world.py`: 画像生成ロジック
- `genre_tags.json`: ジャンルタグ設定
- `templates/index.html`: WebUI
- `static/`: CSS、画像ファイル

## 使用方法

1. テキストエリアに生成したい音楽のイメージを入力
2. 生成パラメータを調整（任意）
3. 「音楽生成」ボタンをクリック
4. 自動生成を有効にすると、一定時間操作がない場合に自動で新しい音楽を生成

## 主な機能

### 生成パラメータ
- タイトル、ジャンル、ムード、楽器の指定
- infer_step、guidance_scale、omega_scale の調整
- 画像サイズ（16:9/4:3）と向き（横/縦）の選択
- ボーカルあり/なしの選択

### 自動生成
- チェックボックスをONにすると即座に音楽生成を開始
- その後、60秒間操作がないと自動で新しい音楽を生成
- ユーザーが操作すると自動で無効化
- **エラー回復機能**: 生成エラー時も停止せず、10秒後に自動リトライ
- **連続エラー保護**: 3回連続エラーで自動停止（安全機能）

## 注意事項

- 外部APIサーバーとの接続が必要
- 生成には時間がかかる場合があります

## License

Momo Song is licensed under the [Apache License 2.0](LICENSE). Model weights
are not included and remain subject to their respective upstream terms.

## 外部API依存関係

### 1. ACE-Step 1.5 REST API（音楽生成）

**デフォルトURL:** `http://127.0.0.1:8001`

**必要なエンドポイント:**
- `POST /release_task`
- `POST /query_result`
- 結果の音声ファイルURL

接続先を変更する場合:

```bash
ACE_STEP_API_URL=http://your-ace-step-host:8001 python music_server.py
```

#### Local acestep.cpp（12GB VRAM向け）

GUIの「音楽生成バックエンド」で `Local acestep.cpp`を選択できます。
既定の接続先は `http://127.0.0.1:8085` です。

ローカル選択時は作詞・曲解説にも `llama-cpp-python` のHigh-level Text
Completion APIとGemma 4 E4B Q4_K_Mを使用し、画像生成APIは呼び出しません。
生成画像の代わりに、ヘッダーで選択した初期画像をそのまま表示します。
Gemma 4 E4Bでは専用プロンプトを使用し、意図分類を省いた「作詞・タグ生成」と
「曲解説」の2回だけで処理します。歌詞は4セクション・合計16行を検証します。

```bash
./start_acestep_cpp.sh --backend cuda --gpu 0
```

12GB向け既定構成:

- LM: `acestep-5Hz-lm-1.7B-Q8_0.gguf`
- DiT（起動時）: `acestep-v15-turbo-Q4_K_M.gguf`
- GUIから `TURBO-Q4` / `TURBO-Q8` / `XL Turbo (Q4_K_M)` を切替可能
- GUIのVRAMモードは、既定の「モデル常駐（高速）」と「STRICT（省VRAM）」を選択可能
- モデルまたはVRAMモードを変更すると、次回の音楽生成直前にACEサーバーだけを自動再起動
- 同じモデル・VRAMモードで続けて生成する場合は再起動せず、常駐モデルを再利用
- batch: 1
- VAE chunk: 512
- `--keep-loaded` なし（モデルを逐次入れ替え）

接続先とモデルは `ACESTEP_CPP_URL`, `ACESTEP_CPP_LM_MODEL`,
`ACESTEP_CPP_SYNTH_MODEL` で変更できます。

ローカルLLMの既定モデルパスはリポジトリ内の
`models/gemma-4-E4B-it-Q4_K_M.gguf` です。変更する場合は
`LOCAL_LLM_MODEL`、CPUスレッド数は `LOCAL_LLM_THREADS`、使用GPUは
`LOCAL_LLM_MAIN_GPU` で指定します。`LOCAL_LLM_GPU_LAYERS` の既定値は
`-1`（全層GPU）です。作詞と曲解説が終わるとGemmaを解放し、その後に
ACE-Stepをロードする逐次方式で12GB VRAMを共有します。

#### Local acestep.cpp（x86 CPU版）

CPU版はCUDA版と別の `build-cpu` ディレクトリへ構築されるため、両方を
切り替えて使用できます。

```bash
./build_acestep_cpp_cpu.sh
./start_acestep_cpp.sh --backend cpu
```

起動後の接続先はCUDA版と同じ `http://127.0.0.1:8085` です。GUIでは
`Local acestep.cpp` を選択してください。環境変数で指定する場合は
`ACESTEP_CPP_BACKEND=cpu ./start_acestep_cpp.sh` も使用できます。

従来の `start_acestep_cpp_12gb.sh` はCUDA版を起動する互換コマンドとして
引き続き利用できます。

### 2. SDXL API（画像生成）

**必要なAPI仕様:**

**エンドポイント:** `POST /text2image`

**リクエスト形式:**
```json
{
  "prompt": "画像生成プロンプト",
  "width": 1296,
  "height": 728,
  "steps": 20,
  "cfg_scale": 7.0
}
```

**レスポンス形式:**
```json
{
  "images": ["base64_encoded_image_data"],
  "info": "generation_info"
}
```

**必要な機能:**
- テキストから画像生成（text2image）
- 複数解像度対応（16:9、4:3）
- カスタムプロンプト対応
- Base64エンコード画像出力

### 3. OpenAI Compatible API（歌詞生成）

**必要なエンドポイント:**
- `/v1/chat/completions`
- GPT-3.5/GPT-4互換API
- 非同期リクエスト対応

## 詳細ドキュメント

- **[📱 ユーザーガイド](USER_GUIDE.md)** - フロントエンドの詳細な使い方
- **[❓ よくある質問（FAQ）](FAQ.md)** - トラブルシューティング・Tips
- **[📚 詳細仕様・処理フロー](DOCUMENTATION.md)** - アプリケーションの詳細機能説明と処理フロー
- **[🔧 API リファレンス](API_REFERENCE.md)** - APIエンドポイントと関数の詳細仕様
- **[🚀 デプロイメントガイド](DEPLOYMENT.md)** - 本番環境への導入手順とシステム設定

## ライセンス

Apache License 2.0
