#!/bin/bash
set -e

echo ""
echo "========================================="
echo "  XMR Dashboard — Setup Script"
echo "========================================="
echo ""

# 1. System dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv curl nodejs npm

# 2. Python venv + backend deps
echo "[2/5] Setting up Python backend..."
cd "$(dirname "$0")/.."
python3 -m venv backend/venv
backend/venv/bin/pip install -q -r backend/requirements.txt
echo "      Backend dependencies installed."

# 3. Patch XMRig config
echo "[3/5] Patching XMRig config to enable HTTP API on port 4048..."
python3 scripts/patch_xmrig_config.py

# 4. Reserve huge pages so XMRig can actually use them
echo "[4/6] Reserving huge pages for XMRig..."
sudo sysctl -w vm.nr_hugepages=1184 || true

# 5. Make the huge-page setting persistent
echo "vm.nr_hugepages=1184" | sudo tee /etc/sysctl.d/99-xmr-dashboard.conf > /dev/null
sudo sysctl --system >/dev/null || true

# 6. Frontend
echo "[5/6] Installing frontend dependencies..."
cd frontend
npm install --silent
echo "      Frontend dependencies installed."
cd ..

# 7. Cloudflare tunnel
echo "[6/6] Installing Cloudflare Tunnel (cloudflared)..."
if ! command -v cloudflared &> /dev/null; then
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
  sudo apt-get update -qq && sudo apt-get install -y cloudflared
  echo "      cloudflared installed."
else
  echo "      cloudflared already installed."
fi

echo ""
echo "========================================="
echo "  Setup complete!"
echo ""
echo "  Next step: run  ./scripts/start.sh"
echo "========================================="
echo ""
