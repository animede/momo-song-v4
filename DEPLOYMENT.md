# Momo Song v3 - デプロイメントガイド

## システム要件

### サーバー要件

**最小要件:**
- CPU: 4コア以上
- メモリ: 8GB以上
- ストレージ: 50GB以上
- OS: Ubuntu 20.04 LTS 以上 / CentOS 8 以上

**推奨要件:**
- CPU: 8コア以上
- メモリ: 16GB以上
- ストレージ: 100GB以上（SSD推奨）
- OS: Ubuntu 22.04 LTS

### 外部依存サービス

**必須サービス:**
1. OpenAI Compatible API Server
2. ACE-Step-direct API Server（[GitHub](https://github.com/RetricSu/ACE-Step-direct)）
3. SDXL API Server

**SDXL APIサーバー要件:**
- Stable Diffusion XL対応
- `/text2image` エンドポイント
- JSON形式のリクエスト/レスポンス
- Base64画像出力対応
- 推奨GPU: RTX 3080以上またはA100

**ネットワーク要件:**
- インターネット接続（外部API利用時）
- ポート開放: 64653（Webサーバー）

## インストール手順

### 1. システム準備

```bash
# システム更新
sudo apt update && sudo apt upgrade -y

# Python 3.11以上のインストール
sudo apt install python3.11 python3.11-venv python3.11-dev -y

# 必要なシステムパッケージ
sudo apt install git curl wget build-essential -y
```

### 2. プロジェクトセットアップ

```bash
# プロジェクトクローン
git clone <repository-url> momo_song-v3
cd momo_song-v3

# 仮想環境作成
python3.11 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 設定ファイル作成

**config.py を作成:**
```python
# config.py
import os

class Config:
    # OpenAI設定
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'http://localhost:8080/v1')
    LLM_API_KEY = os.getenv('LLM_API_KEY', 'local-not-required')

    # SDXL設定
    SDXL_URL = os.getenv('SDXL_URL', 'http://localhost:64656')

    # ACE-Step-direct設定
    ACE_STEP_URL = os.getenv('ACE_STEP_URL', 'http://localhost:64655')

    # サーバー設定
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 64653))

    # セキュリティ設定
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    REQUEST_TIMEOUT = 300  # 5分
```

**環境変数ファイル (.env) を作成:**
```bash
# .env
OPENAI_BASE_URL=http://your-openai-server:8080/v1
LLM_API_KEY=replace-with-your-key-if-required
SDXL_URL=http://your-sdxl-server:64656
ACE_STEP_URL=http://your-ace-step-server:64655
HOST=0.0.0.0
PORT=64653
```

### 4. サービス設定 (systemd)

**サービスファイル作成:**
```bash
sudo nano /etc/systemd/system/momo-song-v3.service
```

```ini
[Unit]
Description=Momo Song v3 Music Generation Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/momo_song-v3
Environment=PATH=/path/to/momo_song-v3/venv/bin
EnvironmentFile=/path/to/momo_song-v3/.env
ExecStart=/path/to/momo_song-v3/venv/bin/python music_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

**サービス有効化:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable momo-song-v3
sudo systemctl start momo-song-v3
sudo systemctl status momo-song-v3
```

## Docker デプロイメント

### Dockerfile

```dockerfile
FROM python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコピー
COPY . .

# ポート露出
EXPOSE 64653

# 起動コマンド
CMD ["python", "music_server.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  momo-song-v3:
    build: .
    ports:
      - "64653:64653"
    environment:
      - OPENAI_BASE_URL=${OPENAI_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - SDXL_URL=${SDXL_URL}
    volumes:
      - ./userdata:/app/userdata
    restart: unless-stopped
    depends_on:
      - redis
      - nginx

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - momo-song-v3
    restart: unless-stopped
```

### Docker実行

```bash
# イメージビルド
docker-compose build

# サービス起動
docker-compose up -d

# ログ確認
docker-compose logs -f momo-song-v3

# サービス停止
docker-compose down
```

## Nginx リバースプロキシ設定

### nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream momo_song_backend {
        server momo-song-v3:64653;
    }

    server {
        listen 80;
        server_name your-domain.com;

        # HTTPS リダイレクト
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL設定
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

        # ファイルアップロード制限
        client_max_body_size 16M;

        # タイムアウト設定
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        location / {
            proxy_pass http://momo_song_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # 静的ファイル配信
        location /static/ {
            alias /app/static/;
            expires 1d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

## 監視・ログ設定

### ログ設定

```python
# logging_config.py
import logging
import logging.handlers
import os

def setup_logging():
    # ログディレクトリ作成
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

    # ログフォーマット
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # アプリケーションログ
    app_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    app_handler.setFormatter(formatter)

    # エラーログ
    error_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/error.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)

    return root_logger
```

### ヘルスチェック

```python
# health_check.py
from fastapi import APIRouter
import psutil
import time

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    }

@router.get("/ready")
async def readiness_check():
    # 外部API接続チェック
    try:
        # OpenAI API チェック
        # SDXL API チェック
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, 503
```

## バックアップ・復旧

### データベースバックアップ（将来の機能拡張用）

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
mkdir -p $BACKUP_DIR

# 設定ファイルバックアップ
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
    .env \
    config.py \
    genre_tags.json

# ユーザーデータバックアップ
tar -czf $BACKUP_DIR/userdata_$DATE.tar.gz userdata/

# 古いバックアップ削除（30日以上）
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### 復旧手順

```bash
# サービス停止
sudo systemctl stop momo-song-v3

# バックアップから復旧
cd /path/to/momo_song-v3
tar -xzf /backups/config_YYYYMMDD_HHMMSS.tar.gz
tar -xzf /backups/userdata_YYYYMMDD_HHMMSS.tar.gz

# 権限修正
chown -R your-username:your-username .
chmod 600 .env

# サービス再開
sudo systemctl start momo-song-v3
sudo systemctl status momo-song-v3
```

## パフォーマンス最適化

### システム最適化

```bash
# ファイルディスクリプタ制限増加
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# TCP設定最適化
echo "net.core.rmem_max = 134217728" >> /etc/sysctl.conf
echo "net.core.wmem_max = 134217728" >> /etc/sysctl.conf
echo "net.ipv4.tcp_rmem = 4096 87380 134217728" >> /etc/sysctl.conf
echo "net.ipv4.tcp_wmem = 4096 65536 134217728" >> /etc/sysctl.conf

sysctl -p
```

### アプリケーション最適化

```python
# uvicorn_config.py
import multiprocessing

# ワーカープロセス数
workers = multiprocessing.cpu_count()

# 接続設定
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# タイムアウト設定
timeout = 300
keepalive = 5

# メモリ最適化
preload_app = True
```

## セキュリティ設定

### ファイアウォール設定

```bash
# UFW設定
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 必要なポートのみ開放
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 64653/tcp   # アプリケーション（必要に応じて）

sudo ufw reload
```

### SSL証明書設定（Let's Encrypt）

```bash
# Certbot インストール
sudo apt install certbot python3-certbot-nginx -y

# 証明書取得
sudo certbot --nginx -d your-domain.com

# 自動更新設定
sudo crontab -e
# 以下を追加
0 12 * * * /usr/bin/certbot renew --quiet
```

## トラブルシューティング

### よくある問題と解決策

**1. サービスが起動しない**
```bash
# ログ確認
sudo journalctl -u momo-song-v3 -f

# 設定ファイル確認
python -c "import music_server"

# ポート使用状況確認
sudo netstat -tlnp | grep 64653
```

**2. メモリ不足**
```bash
# メモリ使用量確認
free -h
ps aux --sort=-%mem | head

# スワップファイル追加
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**3. API接続エラー**
```bash
# 外部API接続テスト
curl -I http://your-openai-server:8080/v1/models
curl -I http://your-sdxl-server:64656/health

# DNS解決確認
nslookup your-api-server.com
```

### ログ分析

```bash
# エラーログ分析
grep "ERROR" logs/error.log | tail -20

# アクセスパターン分析
grep "POST /generate_" logs/app.log | wc -l

# パフォーマンス分析
grep "generation took" logs/app.log | awk '{print $NF}' | sort -n
```

## アップデート手順

### 通常アップデート

```bash
# バックアップ作成
./backup.sh

# サービス停止
sudo systemctl stop momo-song-v3

# コード更新
git pull origin main

# 依存関係更新
source venv/bin/activate
pip install -r requirements.txt

# サービス再開
sudo systemctl start momo-song-v3
sudo systemctl status momo-song-v3
```

### メジャーアップデート

```bash
# 全体バックアップ
tar -czf full_backup_$(date +%Y%m%d).tar.gz .

# 新バージョン並行デプロイ
git clone <repository-url> momo_song-v3-new
cd momo_song-v3-new

# 設定ファイルコピー
cp ../momo_song-v3/.env .
cp ../momo_song-v3/config.py .

# テスト実行
python music_server.py --port 64654

# 問題なければ切り替え
sudo systemctl stop momo-song-v3
mv ../momo_song-v3 ../momo_song-v3-old
mv ../momo_song-v3-new ../momo_song-v3
sudo systemctl start momo-song-v3
```
