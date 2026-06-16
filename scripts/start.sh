#!/bin/bash

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "========================================="
echo "  ISFCR Mining Console — Starting"
echo "========================================="

# 1. Build frontend FIRST — the backend serves this build directory directly,
#    so it has to exist before uvicorn starts.
echo "[1/3] Building frontend..."
cd frontend
npm run build --silent
cd "$ROOT"

# 2. Start FastAPI backend (serves the API *and* the built dashboard on the
#    same port, so relative fetch() calls and the Cloudflare tunnel below
#    both resolve correctly)
echo "[2/3] Starting backend + dashboard on port 8000..."
venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "      Backend PID: $BACKEND_PID"
sleep 2

# 3. Cloudflare tunnel — point this at the SAME port the dashboard is served
#    from (8000). Tunneling any other port will leave the public URL 404'ing
#    on "/" even though everything is "running".
echo "[3/3] Starting Cloudflare tunnel..."

if ! command -v cloudflared &> /dev/null; then
  echo ""
  echo "  ✗ ERROR: 'cloudflared' is not installed or not on PATH."
  echo "    Run ./scripts/setup.sh first (it installs cloudflared in step 7/7)."
  echo "    The dashboard is still running locally at http://localhost:8000"
  echo ""
  trap "echo 'Stopping...'; kill $BACKEND_PID 2>/dev/null" EXIT
  wait
  exit 1
fi

rm -f /tmp/cf_tunnel.log
cloudflared tunnel --url http://localhost:8000 &> /tmp/cf_tunnel.log &
CF_PID=$!

TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(grep -oP 'https://[a-z0-9\-]+\.trycloudflare\.com' /tmp/cf_tunnel.log | head -1)
  if [ -n "$TUNNEL_URL" ]; then
    break
  fi
  if ! kill -0 "$CF_PID" 2>/dev/null; then
    echo ""
    echo "  ✗ ERROR: cloudflared process died. Full log:"
    echo "  -----------------------------------------"
    cat /tmp/cf_tunnel.log
    echo "  -----------------------------------------"
    break
  fi
  sleep 1
done
echo "$TUNNEL_URL" > /tmp/tunnel_url

echo ""
echo "========================================="
echo "  ✓ Dashboard + Backend:  http://localhost:8000"
if [ -n "$TUNNEL_URL" ]; then
echo "  ✓ Public tunnel:  $TUNNEL_URL"
echo ""
echo "  Open $TUNNEL_URL from anywhere!"
else
echo "  ⚠ Tunnel URL not detected after 30s. Here's the full cloudflared log:"
echo "  -----------------------------------------"
cat /tmp/cf_tunnel.log
echo "  -----------------------------------------"
echo "  The dashboard still works locally at http://localhost:8000 —"
echo "  the issue above is specific to the tunnel, not the app."
fi
echo ""
echo "  Press Ctrl+C to stop everything."
echo "========================================="
echo ""

trap "echo 'Stopping...'; kill $BACKEND_PID $CF_PID 2>/dev/null" EXIT
wait
