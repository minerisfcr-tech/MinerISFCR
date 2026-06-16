# XMR Mining Dashboard

Real-time Monero mining dashboard with Start/Stop control, live GPU/CPU stats, and plain-English error messages.

## Project Structure

```
xmr-dashboard/
├── backend/
│   ├── main.py          ← FastAPI server (runs on the rig)
│   └── requirements.txt
├── frontend/
│   ├── src/App.js       ← React dashboard UI
│   └── package.json
└── scripts/
    ├── setup.sh              ← Run once to install everything
    ├── start.sh              ← Run every time to launch
    └── patch_xmrig_config.py ← Enables XMRig HTTP API
```

## First-Time Setup (run on the mining rig)

```bash
# 1. Copy this folder to your rig (or clone it)
scp -r xmr-dashboard isfcr@YOUR_RIG_IP:~/

# 2. SSH into the rig
ssh isfcr@YOUR_RIG_IP

# 3. Run setup (one time only)
cd ~/xmr-dashboard
chmod +x scripts/setup.sh
./scripts/setup.sh
```

## Start the Dashboard

```bash
./scripts/start.sh
```

The terminal will print a public URL like:
```
✓ Public tunnel:  https://xyz-abc.trycloudflare.com
```

Open that URL in any browser, anywhere.

## Features

- **Start/Stop mining** with a single button click
- **Live hashrate** — 1 min, 10 min, 1 hour averages
- **Share tracking** — accepted vs rejected
- **GPU stats** — temp, utilisation, power draw, VRAM, fan speed, clock
- **CPU stats** — usage, temperature, RAM, frequency
- **Error detection** in plain English — pool issues, overheating, crashes

## Notes

- XMRig HTTP API runs on port **4048** (to avoid conflicts with other services)
- The API token is `miner123` — change it in `backend/main.py` and `config.json` if needed
- Cloudflare tunnel is free and requires no account for basic use
- Stats update every **2 seconds** via WebSocket
