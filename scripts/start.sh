#!/bin/bash

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "========================================="
echo "  ISFCR Mining Console — Starting"
echo "========================================="

# 1. Start FastAPI backend
echo "[1/3] Starting backend on port 8000..."
venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "      Backend PID: $BACKEND_PID"
sleep 2

# 2. Build & serve frontend
echo "[2/3] Building frontend..."
cd frontend
npm run build --silent
npx serve -s build -l 3002 &
FRONTEND_PID=$!
cd "$ROOT"
echo "      Frontend PID: $FRONTEND_PID (port 3002)"

# 3. Cloudflare tunnel
echo "[3/3] Starting Cloudflare tunnel..."
cloudflared tunnel --url http://localhost:8000 &> /tmp/cf_tunnel.log &
CF_PID=$!
sleep 4

TUNNEL_URL=$(grep -oP 'https://[a-z0-9\-]+\.trycloudflare\.com' /tmp/cf_tunnel.log | head -1)
echo "$TUNNEL_URL" > /tmp/tunnel_url

echo ""
echo "========================================="
echo "  ✓ Backend:        http://localhost:8000"
echo "  ✓ Dashboard:      http://localhost:3002"
if [ -n "$TUNNEL_URL" ]; then
echo "  ✓ Public tunnel:  $TUNNEL_URL"
echo ""
echo "  Open $TUNNEL_URL from anywhere!"
else
echo "  ⚠ Tunnel URL not detected yet — check /tmp/cf_tunnel.log"
fi
echo ""
echo "  Press Ctrl+C to stop everything."
echo "========================================="
echo ""

trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID $CF_PID 2>/dev/null" EXIT
wait
