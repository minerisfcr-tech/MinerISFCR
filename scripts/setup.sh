#!/bin/bash
set -e

echo ""
echo "========================================="
echo "  ISFCR Mining Console — Setup Script"
echo "========================================="
echo ""

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 1. System dependencies
echo "[1/7] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv curl wget nodejs npm jq

# 2. Python venv + backend deps
echo "[2/7] Setting up Python backend..."
python3 -m venv venv
venv/bin/pip install -q -r backend/requirements.txt
echo "      Backend dependencies installed."

# 3. Set up bin/ directory and ensure XMRig is present
echo "[3/7] Checking for XMRig binary..."
mkdir -p bin
if [ ! -f bin/xmrig ]; then
  if [ -f /home/isfcr/crypto_mining/monero/xmrig ]; then
    cp /home/isfcr/crypto_mining/monero/xmrig bin/xmrig
    echo "      Copied existing XMRig binary into bin/"
  else
    echo "      XMRig not found locally — downloading latest release..."
    XMRIG_URL=$(curl -s https://api.github.com/repos/xmrig/xmrig/releases/latest \
      | jq -r '.assets[] | select(.name | test("linux-static-x64.tar.gz$")) | .browser_download_url')
    wget -q "$XMRIG_URL" -O /tmp/xmrig.tar.gz
    tar -xzf /tmp/xmrig.tar.gz -C /tmp
    XMRIG_BIN=$(find /tmp -maxdepth 2 -name "xmrig" -type f | head -1)
    cp "$XMRIG_BIN" bin/xmrig
    echo "      Downloaded XMRig into bin/"
  fi
fi
chmod +x bin/xmrig

# 4. Download T-Rex miner (for ETC / RVN / ALPH / ERG)
echo "[4/7] Checking for T-Rex miner binary..."
if [ ! -f bin/t-rex ]; then
  echo "      Downloading latest T-Rex release..."
  TREX_URL=$(curl -s https://api.github.com/repos/trexminer/T-Rex/releases/latest \
    | jq -r '.assets[] | select(.name | test("linux.*\\.tar\\.gz$")) | .browser_download_url' | head -1)
  if [ -z "$TREX_URL" ]; then
    echo "      WARNING: Could not resolve T-Rex download URL automatically."
    echo "      Visit https://github.com/trexminer/T-Rex/releases and manually place the 't-rex' binary in $ROOT/bin/"
  else
    wget -q "$TREX_URL" -O /tmp/t-rex.tar.gz
    tar -xzf /tmp/t-rex.tar.gz -C /tmp/t-rex-extracted --one-top-level 2>/dev/null || (mkdir -p /tmp/t-rex-extracted && tar -xzf /tmp/t-rex.tar.gz -C /tmp/t-rex-extracted)
    TREX_BIN=$(find /tmp/t-rex-extracted -maxdepth 2 -name "t-rex" -type f | head -1)
    cp "$TREX_BIN" bin/t-rex
    echo "      Downloaded T-Rex into bin/"
  fi
fi
chmod +x bin/t-rex 2>/dev/null || true

# 5. Reserve huge pages so XMRig can use them for RandomX
echo "[5/7] Reserving huge pages for XMRig..."
sudo sysctl -w vm.nr_hugepages=1184 || true
echo "vm.nr_hugepages=1184" | sudo tee /etc/sysctl.d/99-isfcr-mining.conf > /dev/null
sudo sysctl --system >/dev/null || true

# 6. Frontend
echo "[6/7] Installing frontend dependencies..."
cd frontend
npm install --silent
echo "      Frontend dependencies installed."
cd "$ROOT"

# 7. Cloudflare tunnel
echo "[7/7] Installing Cloudflare Tunnel (cloudflared)..."
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
echo "  Coins ready: XMR (XMRig) · ETC, RVN, ALPH, ERG (T-Rex)"
echo "  Wallets and pools are already set in configs/*.json"
echo ""
echo "  Next step: run  ./scripts/start.sh"
echo "========================================="
echo ""
