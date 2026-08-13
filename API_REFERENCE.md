# Momo Song v4 APIリファレンス

既定のWebサーバーは `http://127.0.0.1:64653` です。ブラウザUI向けの内部APIであり、
バージョニングされた公開APIではありません。

## `GET /`

GUIのHTMLを返します。

## `POST /generate_lyrics`

`multipart/form-data`で作詞と曲解説を生成します。

| フィールド | 型 | 既定値 | 説明 |
|---|---|---|---|
| `user_input` | string | 空欄 | 曲の指示。空欄はおまかせ |
| `previouse_title` | string | 空欄 | 直前曲との重複回避用タイトル |
| `no_vocal` | boolean | `false` | インストゥルメンタル指定 |
| `music_backend` | string | `local_cpp` | `local_cpp` または `remote` |

成功時は `result`、`lyrics_dict`、`music_world`を返します。LLMが有効なデータを返さない
場合はHTTP 502です。

## `POST /generate_music`

`multipart/form-data`で作曲し、Remoteの場合だけ画像も生成します。

| フィールド | 型 | 既定値 |
|---|---|---|
| `lyrics_dict` | JSON文字列 | 必須 |
| `music_world` | JSON文字列 | 必須 |
| `infer_step` | integer | `27` |
| `guidance_scale` | number | `3` |
| `height` / `width` | integer | `976` / `1296` |
| `no_vocal` | boolean | `false` |
| `audio_duration` | integer | `-1`（自動） |
| `ace_model` | string | `acestep-v15-turbo-Q4_K_M.gguf` |
| `ace_memory_mode` | string | `keep_loaded` |
| `vocal_language` | string | `ja` |
| `thinking` | boolean | `true` |
| `bpm` / `key_scale` / `seed` | string | 空欄（自動） |
| `music_backend` | string | `local_cpp` |

成功時は `lyrics_json`、MP3の `audio_base64`、画像がある場合は `image_base64` を返します。
ローカルでは `image_base64` は `null` です。

## `POST /download_history_zip`

JSON本文 `{"songs": [...]}` を受け取り、各曲のMP3と歌詞TXTを含むZIPを返します。
各要素は `title`、`lyrics`、`audio_base64` を持ちます。同名曲には連番が付与されます。

## 外部サービス

- Remote ACE-Step: `POST /release_task`、`POST /query_result`
- Remote LLM: OpenAI互換Chat Completions API
- Remote画像: `POST /text2image`
- Local ACE-Step: acestep.cppのHTTPサーバー（既定 `127.0.0.1:8085`）

設定値は[デプロイメントガイド](DEPLOYMENT.md)と[.env.example](.env.example)を参照してください。
