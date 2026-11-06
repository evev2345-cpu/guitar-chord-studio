#!/usr/bin/env bash
set -euo pipefail

# Oracle Cloud Ubuntu (VM.Standard.E2.1.Micro 1GB RAM 및 Ampere 모두 지원) 자동 설치 스크립트
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-80}"

echo "[0/5] 메모리 확인 및 4GB 스왑(Swap) 메모리 자동 설정 (E2.1.Micro 1GB RAM OOM 방지)..."
TOTAL_MEM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
if [ "$TOTAL_MEM_MB" -lt 4000 ] && [ ! -f /swapfile ]; then
    echo " -> 물리 RAM(${TOTAL_MEM_MB}MB) 보강을 위해 4GB /swapfile 생성 중..."
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
    fi
fi
free -h

echo "[1/5] 시스템 패키지(ffmpeg, python3-venv, libsndfile1) 설치 중..."
sudo apt-get update
sudo apt-get install -y ffmpeg python3-venv python3-pip libsndfile1 libgl1 libglib2.0-0 iptables-persistent

echo "[2/5] Python 가상환경(.venv-audio-model) 구성 및 패키지 설치 중..."
if [ ! -d "$APP_DIR/.venv-audio-model" ]; then
    python3 -m venv "$APP_DIR/.venv-audio-model"
fi
"$APP_DIR/.venv-audio-model/bin/pip" install --upgrade pip
"$APP_DIR/.venv-audio-model/bin/pip" install -r "$APP_DIR/requirements-deploy.txt"

echo "[3/5] 오라클 클라우드 Ubuntu 내부 방화벽(iptables) 포트 ${PORT} 개방 중..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "${PORT}" -j ACCEPT || true
sudo netfilter-persistent save || true

echo "[4/5] systemd 백그라운드 서비스(chord-studio.service) 등록 중..."
SERVICE_FILE="/etc/systemd/system/chord-studio.service"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Guitar Lab Chord Studio Web Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
AmbientCapabilities=CAP_NET_BIND_SERVICE
Environment="OMP_NUM_THREADS=1"
Environment="MKL_NUM_THREADS=1"
Environment="OPENBLAS_NUM_THREADS=1"
Environment="PYTHONPATH=$APP_DIR:$APP_DIR/engine"
ExecStart=$APP_DIR/.venv-audio-model/bin/python $APP_DIR/chord_studio_v2/server_v2.py --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "[5/5] 서비스 시작 및 부팅 시 자동 실행 활성화..."
sudo systemctl daemon-reload
sudo systemctl enable --now chord-studio.service
sudo systemctl status chord-studio.service --no-pager

PUBLIC_IP="$(curl -s ifconfig.me || hostname -I | awk '{print $1}')"
if [ "$PORT" = "80" ]; then
    ACCESS_URL="http://${PUBLIC_IP}"
else
    ACCESS_URL="http://${PUBLIC_IP}:${PORT}"
fi
echo ""
echo "=========================================================="
echo " 배포 완료! 접속 주소: ${ACCESS_URL}"
echo "=========================================================="
