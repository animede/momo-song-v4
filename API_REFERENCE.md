# Momo Song v3 - API リファレンス

## 外部API仕様

### 1. ACE-Step-direct API

**リポジトリ:** [ACE-Step-direct](https://github.com/RetricSu/ACE-Step-direct)

**説明:** 歌詞から音楽を生成するAPIサーバー

**使用方法:** `music.py`の`generate_song()`関数内で呼び出される

### 2. SDXL画像生成API

**エンドポイント:** `POST /text2image`

**説明:** テキストプロンプトから画像を生成

**リクエストパラメータ:**

| パラメータ名 | 型 | 必須 | 説明 | デフォルト値 |
|-------------|---|------|------|-------------|
| prompt | string | ✓ | 画像生成プロンプト | - |
| width | integer | | 画像幅 | 1024 |
| height | integer | | 画像高さ | 1024 |
| steps | integer | | 生成ステップ数 | 20 |
| cfg_scale | float | | CFGスケール | 7.0 |
| seed | integer | | 乱数シード（再現性用） | -1 |

**リクエスト例:**
```json
{
  "prompt": "beautiful sunset over mountains, serene landscape, vibrant colors",
  "width": 1296,
  "height": 728,
  "steps": 20,
  "cfg_scale": 7.0
}
```

**レスポンス:**
```json
{
  "images": [
    "iVBORw0KGgoAAAANSUhEUgAA..."
  ],
  "info": {
    "steps": 20,
    "cfg_scale": 7.0,
    "seed": 1234567890,
    "model": "sdxl_1.0"
  }
}
```

**エラーレスポンス:**
```json
{
  "error": "Invalid prompt",
  "code": 400
}
```

### 3. OpenAI Compatible API

**エンドポイント:** `POST /v1/chat/completions`

**説明:** GPT互換の歌詞生成API

**使用モデル:** GPT-3.5-turbo / GPT-4

## API エンドポイント

### 1. 歌詞生成API

**エンドポイント:** `POST /generate_lyrics`

**説明:** ユーザー入力から歌詞を生成します。

**リクエストパラメータ:**

| パラメータ名 | 型 | 必須 | 説明 |
|-------------|---|------|------|
| user_input | string | ✓ | ユーザーの入力テキスト |
| previouse_title | string | | 前回のタイトル（継続性のため） |
| no_vocal | boolean | | ボーカルなし楽曲フラグ（デフォルト: false） |

**リクエスト例:**
```bash
curl -X POST http://localhost:64653/generate_lyrics \
  -F "user_input=明るいポップソング" \
  -F "previouse_title=" \
  -F "no_vocal=false"
```

**レスポンス:**
```json
{
  "result": true,
  "lyrics_dict": {
    "title": "夏の風",
    "lyrics": {
      "verse1": "青い空に白い雲が...",
      "chorus": "風が運んでくる...",
      "verse2": "緑の木陰で...",
      "bridge": "思い出の中で...",
      "outro": "夏は終わらない..."
    }
  },
  "music_world": {
    "message": "爽やかな夏の日をイメージした明るいポップソング。青空と白い雲、緑の木々が織りなす清涼感のある世界観。"
  }
}
```

**エラーレスポンス:**
```json
{
  "err": "音楽生成に失敗しました"
}
```

### 2. 音楽・画像生成API

**エンドポイント:** `POST /generate_music`

**説明:** 歌詞データから音楽と画像を並列生成します。

**リクエストパラメータ:**

| パラメータ名 | 型 | 必須 | 説明 | デフォルト値 | 範囲 |
|-------------|---|------|------|-------------|------|
| lyrics_dict | string | ✓ | 歌詞辞書のJSON文字列 | - | - |
| infer_step | integer | | 推論ステップ数 | 27 | 20-200 |
| guidance_scale | float | | ガイダンススケール | 15.0 | 1.0-50.0 |
| gomega_scale | float | | オメガスケール | 10.0 | 5.0-50.0 |
| music_world | string | ✓ | 楽曲世界観のJSON文字列 | - | - |
| height | integer | | 生成画像の高さ | 976 | - |
| width | integer | | 生成画像の幅 | 1296 | - |
| no_vocal | boolean | | ボーカルなし楽曲フラグ | false | - |

**リクエスト例:**
```bash
curl -X POST http://localhost:64653/generate_music \
  -F 'lyrics_dict={"title":"夏の風","lyrics":{"verse1":"青い空に..."}}' \
  -F "infer_step=100" \
  -F "guidance_scale=15.0" \
  -F "gomega_scale=10.0" \
  -F 'music_world={"message":"爽やかな夏の日..."}' \
  -F "height=728" \
  -F "width=1296" \
  -F "no_vocal=false"
```

**レスポンス:**
```json
{
  "lyrics_json": "{\"title\":\"夏の風\",\"lyrics\":{...}}",
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "audio_base64": "data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAA..."
}
```

## 内部API関数

### 1. music_generation()

**ファイル:** `music.py`

**説明:** OpenAI APIを使用して歌詞と楽曲世界観を生成

**シグネチャ:**
```python
async def music_generation(
    user_input: str,
    genre_tags: dict,
    previous_title: str = ""
) -> tuple[bool, dict, dict, str]
```

**パラメータ:**
- `user_input`: ユーザー入力テキスト
- `genre_tags`: ジャンルタグ辞書
- `previous_title`: 前回のタイトル

**戻り値:**
- `success`: 成功フラグ
- `lyrics_dict`: 歌詞辞書
- `music_world`: 楽曲世界観辞書
- `error_message`: エラーメッセージ

### 2. generate_song()

**ファイル:** `music.py`

**説明:** ACE-Step APIを使用して音楽を生成

**シグネチャ:**
```python
def generate_song(
    lyrics_dict: dict,
    infer_step: int = 27,
    guidance_scale: float = 15.0,
    omega_scale: float = 10.0,
    no_vocal: bool = False
) -> bytes
```

**パラメータ:**
- `lyrics_dict`: 歌詞辞書
- `infer_step`: 推論ステップ数
- `guidance_scale`: ガイダンススケール
- `omega_scale`: オメガスケール
- `no_vocal`: ボーカルなしフラグ

**戻り値:**
- `bytes`: MP3音楽データ

### 3. create_image()

**ファイル:** `create_image_world.py`

**説明:** SDXL APIを使用して画像を生成

**シグネチャ:**
```python
async def create_image(
    sdxl_url: str,
    client: AsyncOpenAI,
    music_world: dict,
    mode: str,
    method: str,
    height: int,
    width: int
) -> PIL.Image.Image
```

**パラメータ:**
- `sdxl_url`: SDXL APIのURL
- `client`: OpenAIクライアント
- `music_world`: 楽曲世界観辞書
- `mode`: 生成モード
- `method`: 生成方法
- `height`: 画像高さ
- `width`: 画像幅

**戻り値:**
- `PIL.Image.Image`: PIL画像オブジェクト

## データ構造

### lyrics_dict 構造

```json
{
  "title": "楽曲タイトル",
  "lyrics": {
    "verse1": "第1バース歌詞",
    "chorus": "コーラス歌詞",
    "verse2": "第2バース歌詞",
    "bridge": "ブリッジ歌詞",
    "outro": "アウトロ歌詞"
  }
}
```

### music_world 構造

```json
{
  "message": "楽曲の世界観を表現するテキスト。画像生成のプロンプト基礎として使用される。"
}
```

### genre_tags 構造

```json
{
  "pop": ["upbeat", "catchy", "mainstream"],
  "jazz": ["smooth", "sophisticated", "improvisation"],
  "rock": ["energetic", "guitar-driven", "powerful"],
  "classical": ["orchestral", "elegant", "timeless"]
}
```

## 設定

### 環境変数

| 変数名 | 説明 | 例 |
|--------|------|---|
| OPENAI_API_KEY | OpenAI APIキー | sk-... |
| OPENAI_BASE_URL | OpenAI APIベースURL | http://localhost:8080/v1 |
| SDXL_URL | SDXL APIのURL | http://localhost:64656 |
| SERVER_PORT | サーバーポート | 64653 |

### music_server.py 設定

```python
# OpenAI クライアント設定
a_client = AsyncOpenAI(
    base_url=os.getenv("LLM_API_URL", "http://127.0.0.1:8080/v1"),
    api_key=os.getenv("LLM_API_KEY", "local-not-required"),
)

# SDXL URL設定
sdxl_url = os.getenv("IMAGE_API_URL", "http://127.0.0.1:64656")

# サーバー設定
uvicorn.run('music_server:app', host='0.0.0.0', port=64653, reload=True)
```

## エラーコード

### HTTPステータスコード

| コード | 説明 |
|--------|------|
| 200 | 成功 |
| 400 | リクエストパラメータエラー |
| 500 | サーバー内部エラー |
| 502 | 外部API接続エラー |
| 503 | サービス一時停止 |

### カスタムエラーメッセージ

| エラーメッセージ | 原因 | 対処法 |
|-----------------|------|-------|
| "音楽生成に失敗しました" | OpenAI API エラー | APIキーとエンドポイント確認 |
| "作詞・曲データ作成に失敗しました" | 歌詞生成エラー | プロンプト内容を変更 |
| "作曲に失敗しました" | 音楽生成APIエラー | パラメータ値を調整 |
| "歌詞が生成されませんでした" | 歌詞の長さ不足 | より具体的な指示を入力 |

## パフォーマンスガイド

### 推奨パラメータ値

**高速生成（品質標準）:**
- infer_step: 50
- guidance_scale: 10.0
- omega_scale: 7.0

**バランス型（推奨）:**
- infer_step: 100
- guidance_scale: 15.0
- omega_scale: 10.0

**高品質（時間がかかる）:**
- infer_step: 200
- guidance_scale: 20.0
- omega_scale: 15.0

### 画像サイズ推奨設定

**Web表示用:**
- 16:9 横: 1296x728

**SNS投稿用:**
- 4:3 横: 1024x768

**モバイル表示用:**
- 16:9 縦: 728x1296

## セキュリティ

### 入力検証

**文字数制限:**
- user_input: 最大 1000文字
- title: 最大 100文字
- genre: 最大 50文字

**禁止文字:**
- HTMLタグ
- JavaScriptコード
- SQL文

### レート制限

**API呼び出し制限:**
- 歌詞生成: 10回/分
- 音楽生成: 5回/分
- 画像生成: 5回/分

**同時接続制限:**
- 最大同時接続数: 10

## トラブルシューティング

### よくある問題

**Q: 音楽生成が遅い**
A: infer_step値を下げて試してください（100 → 50）

**Q: 画像が生成されない**
A: SDXL APIの接続状況を確認してください

**Q: 自動生成が動作しない**
A: ブラウザの開発者ツールでJavaScriptエラーを確認してください

**Q: 音声が再生されない**
A: ブラウザの自動再生ポリシーを確認してください

### ログ出力

**サーバーログ:**
```bash
# サーバー起動時のログ確認
python music_server.py

# 詳細ログ出力
uvicorn music_server:app --host 0.0.0.0 --port 64653 --log-level debug
```

**ブラウザコンソール:**
```javascript
// 自動生成状態の確認
console.log("autoGenerateEnabled:", autoGenerateEnabled);
console.log("playQueue.length:", playQueue.length);
console.log("isGenerating:", isGenerating);
```
