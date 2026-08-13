# Momo Song v4 技術概要

## 処理フロー

1. ブラウザが `/generate_lyrics` へ指示を送信します。
2. LocalではGemma 4 E4Bを `llama-cpp-python` High-level Completion APIで実行します。
   RemoteではOpenAI互換Chat Completions APIを使用します。
3. サーバーは歌詞、タイトル、音楽タグ、曲解説を正規化してブラウザへ返します。
4. ブラウザが `/generate_music` へ歌詞と生成パラメータを送信します。
5. LocalではGemmaを解放してからacestep.cppを使用します。RemoteではACE-Step REST APIと
   画像生成APIを並行実行します。
6. MP3と、Remoteの場合は生成画像をData URIで返し、ブラウザが再生・履歴管理します。

## ローカルVRAM管理

ローカル作詞と作曲は逐次方式です。2曲目以降も作詞前にACEサーバーを停止してGemma用VRAMを
確保し、作詞後にGemmaを解放してACE-Stepを起動します。モデルまたはVRAMモードが変わった
場合は、次の作曲直前にACEサーバーを新しい設定で再起動します。

`keep_loaded`は同じ設定での連続生成を速くし、`strict`はVRAM使用量を抑えます。実際の
ピーク使用量はGPU、ドライバー、曲長、モデルで変わります。

## ブラウザ状態

生成履歴、現在曲、次曲候補、ループ生成状態を分離して保持します。曲を切り替える時だけ
タイトル、歌詞、解説を現在曲へ反映するため、先行生成中の内容を再生曲へ重ねません。
履歴はサーバー永続データではなく、接続中のブラウザセッション内に保持されます。

音声解析にはWeb Audio APIを使用し、選択した前景演出へ音量・波形・周波数成分を反映します。
歌詞は再生進行率に合わせてスクロールし、末尾が表示領域に収まる位置で止まります。

## モジュール

- `music_server.py`: FastAPIルート、モデル切替、ZIP生成
- `music.py`: 作詞・タグ・解説生成とバックエンド振り分け
- `local_llm.py`: llama-cpp-pythonによるGemma実行
- `acestep_cpp_client.py`: ローカルacestep.cppクライアント
- `create_image_world.py`: Remote画像生成
- `templates/index.html`: GUI、再生、履歴、ループ生成、音響演出
- `installer/install.py`: 上流配布元を利用する共通インストーラ

APIの入出力は[APIリファレンス](API_REFERENCE.md)、運用設定は
[デプロイメントガイド](DEPLOYMENT.md)を参照してください。
