#!/bin/bash

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "========================================="
echo "  ISFCR Mining Console — Starting"
echo "========================================="

stop_port_processes() {
  local port="$1"
  if command -v fuser &>/dev/null; then
    fuser -k "${port}/tcp" &>/dev/null || true
  elif command -v lsof &>/dev/null; then
    local pids
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      kill $pids 2>/dev/null || true
    fi
  fi
}

echo "[0/3] Cleaning up old dashboard processes..."
stop_port_processes 8000
stop_port_processes 3002
pkill -f "cloudflared tunnel --url http://localhost:8000" 2>/dev/null || true
sleep 1

# ── 1. Build frontend ─────────────────────────────────────────────────────────
echo "[1/3] Building frontend..."
cd frontend
npm run build --silent
cd "$ROOT"

# ── 2. Start FastAPI backend + built dashboard ────────────────────────────────
echo "[2/3] Starting backend and dashboard on port 8000..."
BACKEND_LOG="/tmp/isfcr_backend.log"
venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "      Backend PID: $BACKEND_PID  (log → $BACKEND_LOG)"
sleep 2

# Verify backend actually started
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo ""
  echo "  ✖ Backend failed to start — check $BACKEND_LOG"
  cat "$BACKEND_LOG"
  exit 1
fi

# ── 3. Cloudflare tunnel ──────────────────────────────────────────────────────
echo "[3/3] Starting Cloudflare tunnel to http://localhost:8000 ..."
CF_LOG="/tmp/cf_tunnel.log"
rm -f "$CF_LOG"
cloudflared tunnel --url http://localhost:8000 > "$CF_LOG" 2>&1 &
CF_PID=$!

# Wait up to 20s for the tunnel URL (new CF format uses trycloudflare.com)
TUNNEL_URL=""
for i in $(seq 1 20); do
  sleep 1
  TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | head -1)
  if [ -n "$TUNNEL_URL" ]; then break; fi
done
echo "$TUNNEL_URL" > /tmp/tunnel_url

# ── 4. Open log viewer in a second terminal ───────────────────────────────────
# Try common terminal emulators in order; fall back to a background tail to file
LOG_WINDOW_OPENED=false
if command -v gnome-terminal &>/dev/null; then
  gnome-terminal --title="ISFCR — Live Logs" -- bash -c "
    echo '╔══════════════════════════════════════════╗'
    echo '║   ISFCR Mining Console — Live Backend Logs ║'
    echo '╚══════════════════════════════════════════╝'
    tail -F \"$BACKEND_LOG\"
  " &>/dev/null & LOG_WINDOW_OPENED=true
elif command -v xterm &>/dev/null; then
  xterm -title "ISFCR — Live Logs" -bg black -fg "#00e676" -fa "Monospace" -fs 11 \
    -e "echo '=== ISFCR Live Backend Logs ==='; tail -F \"$BACKEND_LOG\"" &>/dev/null &
  LOG_WINDOW_OPENED=true
elif command -v konsole &>/dev/null; then
  konsole --title "ISFCR — Live Logs" -e bash -c "tail -F \"$BACKEND_LOG\"" &>/dev/null &
  LOG_WINDOW_OPENED=true
elif command -v xfce4-terminal &>/dev/null; then
  xfce4-terminal --title="ISFCR — Live Logs" -e "tail -F \"$BACKEND_LOG\"" &>/dev/null &
  LOG_WINDOW_OPENED=true
elif command -v tmux &>/dev/null && [ -z "$TMUX" ]; then
  # Not in tmux — launch a named session with two panes
  tmux new-session -d -s isfcr -x 220 -y 50 2>/dev/null
  tmux rename-window -t isfcr:0 "Main"
  tmux split-window -t isfcr:0 -h
  tmux send-keys -t isfcr:0.1 "echo '=== ISFCR Live Backend Logs ==='; tail -F \"$BACKEND_LOG\"" Enter
  tmux select-pane -t isfcr:0.0
  echo ""
  echo "  📺 Log pane opened in right split of a tmux session."
  echo "     Attach with:  tmux attach -t isfcr"
  LOG_WINDOW_OPENED=true
elif [ -n "$TMUX" ]; then
  # Already inside tmux — open a new pane
  tmux split-window -h "tail -F \"$BACKEND_LOG\""
  tmux select-pane -t '{left}'
  LOG_WINDOW_OPENED=true
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  ✓ Dashboard/API:  http://localhost:8000"
if [ -n "$TUNNEL_URL" ]; then
  echo "  ✓ Public tunnel:  $TUNNEL_URL"
  echo ""
  echo "  Open $TUNNEL_URL from anywhere!"
else
  echo "  ⚠ Tunnel URL not detected yet."
  echo "    Check: $CF_LOG"
  echo "    Or run: grep -oE 'https://.*trycloudflare.com' $CF_LOG"
fi
if [ "$LOG_WINDOW_OPENED" = true ]; then
  echo ""
  echo "  📺 Backend logs are streaming in a separate terminal."
else
  echo ""
  echo "  📄 No GUI terminal found — stream logs manually:"
  echo "     tail -F $BACKEND_LOG"
fi
echo ""
echo "  Press Ctrl+C to stop everything."
echo "========================================="
echo ""

trap "echo 'Stopping...'; kill $BACKEND_PID $CF_PID 2>/dev/null; wait" EXIT SIGINT SIGTERM
wait $BACKEND_PID
