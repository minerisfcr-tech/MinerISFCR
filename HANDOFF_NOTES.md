# ISFCR Mining Console — Handoff Notes

## What's done

### Backend
- Pool routing fixed: XMR→MoneroOcean, ALPH→HeroMiners, ETC/RVN/ERG→2Miners (the ERG "wacky" issue — moved off woolypooly).
- `backend/pools/pool_clients.py`, `market_data.py`, `network_data.py` — normalize pool/market/network data, tested against real fetched/documented API shapes.
- `backend/storage/history.py` — SQLite history for charts + block-found events.
- `main.py` — wallet read from config files, extended GPU/CPU/disk/network stats, block-found detection wired to real pool data, new endpoints: `/history/snapshots`, `/history/blocks`, `/market/snapshot`, `/pool/status`.

### Frontend (new this round)
- Multi-page app with sidebar nav and real routes: `/` (Dashboard), `/hardware`, `/pool`, `/network`, `/profitability`, `/blocks` (Block Discovery), `/history`, `/alerts`, `/settings`.
- `context/MiningDataContext.js` — single shared websocket/polling data source for all pages.
- `components/Layout.js` — sidebar with live backend/miner status dots.
- `components/BlockFoundOverlay.js` — animated toast with a chain-link animation, fires only on real pool-confirmed block events (per your "real trigger only" call).
- `pages/BlockDiscovery.js` — persistent chain visualization strip + confirmed-blocks table.
- `pages/History.js` — recharts line charts (hashrate, GPU temp, power, price, shares, CPU usage) with 1h/6h/24h/7d range toggle.
- `pages/Dashboard.js` — the 8 core KPI cards you listed, plus hardware/pool/market quick-glance panels.
- `pages/Hardware.js`, `Pool.js`, `NetworkCoin.js`, `Profitability.js`, `Alerts.js`, `Settings.js` — remaining metric categories from your list.
- `package.json` updated with `react-router-dom`.

## What's NOT done / known gaps

- **I could not run `npm install` or build the frontend in my sandbox** — it has no network access (confirmed: npm registry, GitHub, and unpkg are all blocked here). Every file was manually reviewed (brace/paren balance, import/export matching, backend field-name cross-checks) but never compiled or run live. **Run `npm install && npm run build` (or `npm start` for dev mode) on your end before trusting it — there is a real chance of a small typo or prop mismatch I couldn't catch without a compiler.**
- Profitability page is intentionally a placeholder — revenue/cost/profit math was descoped per your "skip for now" decision; the page explains why instead of showing fake numbers.
- Network-level stats (block height, difficulty) show "Not exposed by this pool API" for any field the pool genuinely doesn't return — most notably MoneroOcean for XMR network hashrate/difficulty. This is a pool API limitation, not a missing feature.
- GPU "hotspot" temperature is honestly marked unsupported on GPUs where nvidia-smi doesn't expose a junction/hotspot sensor (most consumer cards) — no fabricated numbers.
- No automated tests beyond the backend logic checks done earlier; no end-to-end run of frontend+backend together.
- Block reward / pool difficulty / pool luck / latency are not populated yet — these need additional, currently-unverified pool API fields.
