# ISFCR Mining Console

Real-time mining dashboard for the ISFCR rig (Intel i9 + RTX 4090). Supports five coins from one dashboard: Monero (XMR), Ethereum Classic (ETC), Ravencoin (RVN), Alephium (ALPH), and Ergo (ERG). Switching coins stops whatever is currently mining and starts the new one — no manual steps needed on the rig.

## How coin switching works

XMR mines on **XMRig** (CPU, RandomX algorithm). ETC, RVN, ALPH, and ERG all mine on **T-Rex** (GPU, since each of those uses a different GPU-friendly algorithm — etchash, kawpow, blake3, autolykos2 — none of which XMRig supports). Only one miner runs at a time, since they'd otherwise fight over the GPU/CPU.

When you click "Switch to X" on the dashboard:
1. The backend sends a stop signal to whatever miner is currently running and waits for it to fully exit
2. It loads that coin's config from `configs/<coin>.json`
3. It launches the correct binary (`bin/xmrig` or `bin/t-rex`) with that config
4. The dashboard's hashrate/stats panels start reading from the new miner's HTTP API

## Project Structure

```
isfcr-mining-console/
├── backend/
│   ├── main.py          ← FastAPI server — multi-coin start/stop/switch logic
│   └── requirements.txt
├── configs/              ← one config per coin, wallet + pool already filled in
│   ├── xmr.json
│   ├── etc.json
│   ├── rvn.json
│   ├── alph.json
│   └── erg.json
├── bin/                   ← miner binaries land here after setup.sh (not committed)
├── logs/                  ← periodic plain-English snapshots (not committed)
├── frontend/
│   └── src/App.js         ← dashboard UI
└── scripts/
    ├── setup.sh           ← run once: installs deps, downloads both miners
    └── start.sh           ← run every time: launches backend + frontend + tunnel
```

## First-Time Setup (on the mining rig)

```bash
cd ~/MinerISFCR
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This installs Python/Node dependencies, downloads XMRig and T-Rex into `bin/`, reserves huge pages for XMRig, and installs the Cloudflare tunnel.

## Start the Dashboard

```bash
./scripts/start.sh
```

Prints a public URL like `https://xyz.trycloudflare.com` — open that from any device.

## Features

- **Start/stop/switch** between 5 coins from a single dropdown — no manual rig access needed
- **Live hashrate, shares, difficulty, pool status** — updates every 2 seconds
- **GPU stats** — temp, utilisation, power draw, VRAM, fan speed, clock
- **CPU stats** — usage, temperature, RAM, frequency
- **Plain-English error detection** — pool issues, overheating, crashes
- **Activity log panel** — a readable snapshot (hashrate, difficulty, pool connection, shares) written every 30 minutes to `logs/mining_activity.log`, viewable from the dashboard

## Wallets and pools

Already configured in `configs/*.json` — no need to edit them unless you want to change pools.

| Coin | Wallet | Pool |
|---|---|---|
| XMR | `43becXiN...4VA` | MoneroOcean |
| ETC | `0x4237C0...4F6` | WoolyPooly |
| RVN | `RVF6yRWr...vT4` | 2Miners |
| ALPH | `3cUsRxSq...Svv` | WoolyPooly |
| ERG | `9iP2k4Pd...E1y` | WoolyPooly |

## Notes

- XMRig HTTP API: `127.0.0.1:4048` · T-Rex HTTP API: `127.0.0.1:4067`
- Only one miner runs at a time — switching coins always stops the current one first
- Dashboard polls every 2 seconds via WebSocket; activity log writes every 30 minutes
