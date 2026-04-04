#!/bin/bash
# DreamStalker deployment script for Linux server
set -e
APP_DIR="/opt/dreamstalker"
echo "=== DreamStalker Deployment ==="
echo "[1/4] Installing Python dependencies..."
cd $APP_DIR
pip3 install --break-system-packages -r requirements.txt 2>/dev/null || pip install -r requirements.txt
echo "[2/4] Creating directories..."
mkdir -p data/audio data/sessions data/dreams data/logs
echo "[3/4] Creating systemd service..."
cat > /etc/systemd/system/dreamstalker.service << 'EOF'
[Unit]
Description=DreamStalker Hypnopedia Server
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/dreamstalker
ExecStart=/usr/bin/python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
echo "[4/4] Starting service..."
systemctl daemon-reload
systemctl enable dreamstalker
systemctl restart dreamstalker
sleep 3
systemctl status dreamstalker --no-pager
echo "=== Deployment complete ==="
