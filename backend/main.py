import asyncio
import json
import logging
import subprocess
import threading
import psutil
import httpx
import os
import signal
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pools.pool_clients import fetch_pool_stats
from .pools.market_data import refresh_market_cache, get_cached_market_snapshot, COINGECKO_IDS
from .pools.network_data import fetch_network_stats
from .storage import history

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("isfcr-mining-console")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── PATHS ────────────────────────────────────────────────────────────────────
# Everything lives inside the repo now — no external folders required.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"
BIN_DIR = REPO_ROOT / "bin"
LOGS_DIR = REPO_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
FRONTEND_BUILD_DIR = REPO_ROOT / "frontend" / "build"

XMRIG_PATH = str(BIN_DIR / "xmrig")
TREX_PATH = str(BIN_DIR / "t-rex")

XMRIG_API = "http://127.0.0.1:4048"
TREX_API = "http://127.0.0.1:4067"

PERIODIC_LOG_PATH = LOGS_DIR / "mining_activity.log"
PERIODIC_LOG_INTERVAL_SECONDS = 30 * 60  # every 30 minutes


class MineRequest(BaseModel):
    coin: str = "XMR"


# ── COIN REGISTRY ────────────────────────────────────────────────────────────
# Each coin says which engine runs it and where its config file lives.
# "xmrig" engine = CPU/RandomX. "trex" engine = NVIDIA GPU algorithms.
COIN_REGISTRY = {
    "XMR":  {"engine": "xmrig", "config": CONFIGS_DIR / "xmr.json",  "label": "Monero",            "api": XMRIG_API, "api_kind": "xmrig", "algo": "RandomX",    "pool_provider": "MoneroOcean"},
    "ETC":  {"engine": "trex",  "config": CONFIGS_DIR / "etc.json",  "label": "Ethereum Classic",   "api": TREX_API,  "api_kind": "trex",  "algo": "Etchash",    "pool_provider": "2Miners"},
    "RVN":  {"engine": "trex",  "config": CONFIGS_DIR / "rvn.json",  "label": "Ravencoin",          "api": TREX_API,  "api_kind": "trex",  "algo": "KawPow",     "pool_provider": "2Miners"},
    "ALPH": {"engine": "trex",  "config": CONFIGS_DIR / "alph.json", "label": "Alephium",           "api": TREX_API,  "api_kind": "trex",  "algo": "Blake3",     "pool_provider": "HeroMiners"},
    "ERG":  {"engine": "trex",  "config": CONFIGS_DIR / "erg.json",  "label": "Ergo",               "api": TREX_API,  "api_kind": "trex",  "algo": "Autolykos2", "pool_provider": "2Miners"},
}

_wallet_cache: dict[str, str] = {}


def get_wallet_for_coin(coin_key: str) -> str:
    """Read the configured wallet address straight out of the coin's miner config file.
    Cached in-memory; config files are essentially static at runtime."""
    if coin_key in _wallet_cache:
        return _wallet_cache[coin_key]
    entry = COIN_REGISTRY.get(coin_key)
    if not entry:
        return ""
    try:
        cfg = json.loads(Path(entry["config"]).read_text())
    except Exception:
        logger.warning("Could not read config for %s to extract wallet", coin_key)
        return ""

    wallet = ""
    if entry["engine"] == "xmrig":
        pools = cfg.get("pools", [])
        if pools:
            wallet = pools[0].get("user", "")
    else:
        pools = cfg.get("pools", [])
        if pools:
            wallet = pools[0].get("user", "")

    _wallet_cache[coin_key] = wallet
    return wallet


# ── PROCESS STATE ────────────────────────────────────────────────────────────
mining_process = None
mining_pid = None
active_coin = None
console_log_task = None
periodic_log_task = None
market_refresh_task = None


def _cmdline_has_path(cmdline: list[str], target_path: str) -> bool:
    target = Path(target_path).resolve()
    for arg in cmdline:
        try:
            if Path(arg).resolve() == target:
                return True
        except Exception:
            if arg == target_path:
                return True
    return False


def _cmdline_has_config(cmdline: list[str], config_path: str) -> bool:
    config_name = Path(config_path).name
    for arg in cmdline:
        if arg == config_path or arg.endswith(f"/{config_name}") or arg == config_name:
            return True
    return False


def find_mining_pid(coin_key: str):
    """Look for an already-running miner process matching this coin's binary+config."""
    entry = COIN_REGISTRY[coin_key]
    binary_path = XMRIG_PATH if entry["engine"] == "xmrig" else TREX_PATH
    config_path = str(entry["config"])
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if not cmdline:
                continue
            if _cmdline_has_path(cmdline, binary_path) and _cmdline_has_config(cmdline, config_path):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def sync_active_miner_from_processes() -> tuple[str | None, int | None]:
    """Adopt a miner that was started outside this backend, if one is running."""
    global mining_pid, active_coin, mining_process

    if mining_pid is not None and active_coin is not None and is_mining(check_external=False):
        return active_coin, mining_pid

    for coin_key in COIN_REGISTRY:
        pid = find_mining_pid(coin_key)
        if pid:
            mining_process = None
            mining_pid = pid
            active_coin = coin_key
            logger.info("Adopted existing %s miner process with PID %s", coin_key, pid)
            return coin_key, pid

    mining_process = None
    mining_pid = None
    active_coin = None
    return None, None


def translate_error(raw: str) -> str:
    raw_lower = raw.lower()
    if "connection refused" in raw_lower or "connect" in raw_lower:
        return "Cannot reach the mining pool — check your internet connection."
    if "invalid" in raw_lower and "share" in raw_lower:
        return "Submitted a share but the pool rejected it — this is sometimes normal."
    if "no active pool" in raw_lower:
        return "No mining pool configured — check the coin's config file."
    if "permission denied" in raw_lower:
        return "Miner doesn't have permission to run — try: chmod +x on the binary."
    if "huge pages" in raw_lower:
        return "Huge pages not enabled — mining will work but at lower efficiency."
    if "cuda" in raw_lower or "opencl" in raw_lower or "no cuda" in raw_lower:
        return "GPU driver issue detected — check your Nvidia drivers."
    if "killed" in raw_lower or "signal 9" in raw_lower:
        return "Miner was force-stopped."
    if "no such file" in raw_lower:
        return "Miner binary not found — did setup.sh finish downloading it?"
    if raw.strip():
        return f"Miner error: {raw.strip()}"
    return ""


def empty_stats() -> dict:
    return {
        "hashrate_1m": 0, "hashrate_10m": 0, "hashrate_1h": 0,
        "accepted_shares": 0, "rejected_shares": 0,
        "pool": "N/A", "uptime": 0, "difficulty": 0, "connected": False,
    }


@app.middleware("http")
async def log_http_requests(request, call_next):
    logger.info("HTTP %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info("HTTP %s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception:
        logger.exception("HTTP %s %s failed", request.method, request.url.path)
        raise


async def get_xmrig_stats() -> dict:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{XMRIG_API}/2/summary")
            resp.raise_for_status()
            data = resp.json()
            hashrate = data.get("hashrate", {}).get("total", [])
            results = data.get("results", {})
            connection = data.get("connection", {})
            connected = bool(
                connection.get("pool")
                and connection.get("ip")
                and connection.get("uptime_ms", 0) > 0
            )
            return {
                "hashrate_1m": hashrate[0] if len(hashrate) > 0 and hashrate[0] else 0,
                "hashrate_10m": hashrate[1] if len(hashrate) > 1 and hashrate[1] else 0,
                "hashrate_1h": hashrate[2] if len(hashrate) > 2 and hashrate[2] else 0,
                "accepted_shares": results.get("shares_good", 0),
                "rejected_shares": max(results.get("shares_total", 0) - results.get("shares_good", 0), 0),
                "pool": connection.get("pool", "N/A"),
                "uptime": data.get("uptime", 0),
                "difficulty": results.get("diff_current", 0),
                "connected": connected,
            }
    except httpx.RequestError as e:
        logger.warning("XMRig API unavailable: %s", e)
        return empty_stats()
    except Exception:
        logger.exception("XMRig API error")
        return empty_stats()


async def get_trex_stats() -> dict:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{TREX_API}/summary")
            resp.raise_for_status()
            data = resp.json()
            active_pool = data.get("active_pool", {})
            hashrate = data.get("hashrate", 0) or 0
            hashrate_avg = data.get("hashrate_avr", hashrate) or hashrate
            connected = bool(active_pool.get("url")) and data.get("connected_pools", data.get("active_pool") is not None)
            return {
                "hashrate_1m": hashrate,
                "hashrate_10m": hashrate_avg,
                "hashrate_1h": data.get("hashrate_max", hashrate_avg) or hashrate_avg,
                "accepted_shares": data.get("accepted_count", 0),
                "rejected_shares": data.get("rejected_count", 0) + data.get("invalid_count", 0),
                "pool": active_pool.get("url", "N/A"),
                "uptime": data.get("uptime", 0),
                "difficulty": active_pool.get("difficulty", 0),
                "connected": bool(active_pool.get("url")),
            }
    except httpx.RequestError as e:
        logger.warning("T-Rex API unavailable: %s", e)
        return empty_stats()
    except Exception:
        logger.exception("T-Rex API error")
        return empty_stats()


async def get_engine_stats(coin_key: str) -> dict:
    entry = COIN_REGISTRY[coin_key]
    if entry["api_kind"] == "xmrig":
        return await get_xmrig_stats()
    return await get_trex_stats()


def get_gpu_stats() -> dict:
    try:
        result = subprocess.run([
            "nvidia-smi",
            "--query-gpu=temperature.gpu,temperature.memory,utilization.gpu,utilization.memory,"
            "power.draw,power.limit,memory.used,memory.total,fan.speed,"
            "clocks.current.graphics,clocks.current.memory,name",
            "--format=csv,noheader,nounits"
        ], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split("\n")[0].split(",")]
            def safe_float(val, default=0):
                try:
                    return float(val)
                except Exception:
                    return default
            temp = safe_float(parts[0])
            # temperature.memory ("hotspot"-adjacent) isn't supported on all GPUs;
            # nvidia-smi has no standard "hotspot" sensor at all — we surface what's
            # actually available (memory junction temp where the driver reports it)
            # and flag it as unsupported rather than fabricate a number.
            mem_temp_raw = parts[1] if len(parts) > 1 else ""
            mem_temp = safe_float(mem_temp_raw, default=None) if mem_temp_raw not in ("", "[N/A]", "N/A") else None
            gpu_name = parts[11].strip() if len(parts) > 11 else "GPU"
            return {
                "name": gpu_name,
                "temp": temp,
                "hotspot_temp": mem_temp,
                "hotspot_supported": mem_temp is not None,
                "gpu_util": safe_float(parts[2]),
                "mem_util": safe_float(parts[3]),
                "power_draw": safe_float(parts[4]),
                "power_limit": safe_float(parts[5]),
                "mem_used": safe_float(parts[6]),
                "mem_total": safe_float(parts[7]),
                "fan_speed": safe_float(parts[8]),
                "clock_mhz": safe_float(parts[9]),
                "mem_clock_mhz": safe_float(parts[10]) if len(parts) > 10 else 0,
                "warning": temp > 82,
            }
    except Exception:
        pass
    return {
        "name": "GPU", "temp": 0, "hotspot_temp": None, "hotspot_supported": False,
        "gpu_util": 0, "mem_util": 0, "power_draw": 0,
        "power_limit": 0, "mem_used": 0, "mem_total": 0,
        "fan_speed": 0, "clock_mhz": 0, "mem_clock_mhz": 0, "warning": False,
    }


_net_io_prev = None
_net_io_prev_ts = None


def get_system_stats() -> dict:
    """Disk usage, network throughput, and system uptime — independent of CPU/GPU."""
    global _net_io_prev, _net_io_prev_ts
    import time as _time

    try:
        disk = psutil.disk_usage("/")
        disk_stats = {
            "disk_used_gb": round(disk.used / 1e9, 2),
            "disk_total_gb": round(disk.total / 1e9, 2),
            "disk_percent": disk.percent,
        }
    except Exception:
        disk_stats = {"disk_used_gb": 0, "disk_total_gb": 0, "disk_percent": 0}

    try:
        net_io = psutil.net_io_counters()
        now = _time.monotonic()
        upload_bps = download_bps = 0.0
        if _net_io_prev is not None and _net_io_prev_ts is not None:
            elapsed = max(now - _net_io_prev_ts, 0.001)
            upload_bps = max((net_io.bytes_sent - _net_io_prev.bytes_sent) / elapsed, 0)
            download_bps = max((net_io.bytes_recv - _net_io_prev.bytes_recv) / elapsed, 0)
        _net_io_prev = net_io
        _net_io_prev_ts = now
        net_stats = {
            "upload_kbps": round(upload_bps / 1024, 2),
            "download_kbps": round(download_bps / 1024, 2),
            "total_sent_gb": round(net_io.bytes_sent / 1e9, 2),
            "total_recv_gb": round(net_io.bytes_recv / 1e9, 2),
        }
    except Exception:
        net_stats = {"upload_kbps": 0, "download_kbps": 0, "total_sent_gb": 0, "total_recv_gb": 0}

    try:
        uptime_seconds = _time.time() - psutil.boot_time()
    except Exception:
        uptime_seconds = 0

    return {**disk_stats, **net_stats, "system_uptime_seconds": int(uptime_seconds)}


def get_cpu_stats() -> dict:
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_temp = 0
        try:
            sensor_data = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz"]:
                if name in sensor_data and sensor_data[name]:
                    cpu_temp = sensor_data[name][0].current
                    break
        except Exception:
            pass
        return {
            "usage_percent": psutil.cpu_percent(interval=None),
            "core_count": psutil.cpu_count(logical=False),
            "thread_count": psutil.cpu_count(logical=True),
            "freq_mhz": cpu_freq.current if cpu_freq else 0,
            "freq_max_mhz": cpu_freq.max if cpu_freq else 0,
            "temp": cpu_temp,
            "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 2),
            "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
            "ram_percent": psutil.virtual_memory().percent,
        }
    except Exception:
        return {
            "usage_percent": 0, "core_count": 0, "thread_count": 0,
            "freq_mhz": 0, "freq_max_mhz": 0, "temp": 0,
            "ram_used_gb": 0, "ram_total_gb": 0, "ram_percent": 0,
        }


def is_mining(check_external: bool = True) -> bool:
    global mining_pid, active_coin
    if mining_pid is None or active_coin is None:
        if check_external:
            _, pid = sync_active_miner_from_processes()
            return pid is not None
        return False
    try:
        proc = psutil.Process(mining_pid)
        if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
            return True
        mining_pid = None
        active_coin = None
        if check_external:
            _, pid = sync_active_miner_from_processes()
            return pid is not None
        return False
    except psutil.NoSuchProcess:
        mining_pid = None
        active_coin = None
        if check_external:
            _, pid = sync_active_miner_from_processes()
            return pid is not None
        return False


async def get_mining_snapshot():
    sync_active_miner_from_processes()
    if not active_coin:
        return False, empty_stats()
    stats = await get_engine_stats(active_coin)
    running = is_mining()
    if stats.get("uptime", 0) > 0 or stats.get("connected"):
        running = True
    return running, stats


# Tracks the last-seen "blocks found" count per coin so we can detect a NEW
# block being found (not just repeat the same count every poll).
_last_blocks_found: dict[str, int] = {}
_last_history_snapshot_ts = 0.0
HISTORY_SNAPSHOT_INTERVAL_SECONDS = 60  # one row per minute is plenty for charts


def detect_new_block(coin_key: str, pool_stats: dict) -> dict | None:
    """Compare this poll's pool-reported blocks_found against the last poll's.
    Returns a block-found event dict if a NEW block was detected, else None."""
    global _last_blocks_found
    blocks_found = pool_stats.get("blocks_found", 0) or 0
    prev = _last_blocks_found.get(coin_key)
    _last_blocks_found[coin_key] = blocks_found
    if prev is not None and blocks_found > prev:
        event = {
            "coin": coin_key,
            "pool_name": pool_stats.get("pool_name"),
            "block_height": pool_stats.get("new_block_height"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        history.insert_block_found(coin_key, pool_stats.get("pool_name", ""), pool_stats.get("new_block_height"), None)
        logger.info("BLOCK FOUND for %s on %s! height=%s", coin_key, pool_stats.get("pool_name"), pool_stats.get("new_block_height"))
        return event
    return None


async def build_dashboard_payload():
    global _last_history_snapshot_ts
    running, stats = await get_mining_snapshot()
    gpu = get_gpu_stats()
    cpu = get_cpu_stats()
    system = get_system_stats()

    coin_key = active_coin or "XMR"
    wallet = get_wallet_for_coin(coin_key)

    # Pool + network + market data run concurrently — they're independent HTTP calls.
    pool_stats, network_stats = await asyncio.gather(
        fetch_pool_stats(coin_key, wallet),
        fetch_network_stats(coin_key, wallet),
    )
    market = get_cached_market_snapshot().get(coin_key, {})

    new_block_event = detect_new_block(coin_key, pool_stats) if running else None

    # Profitability — revenue only, per product decision (no power-cost / net-profit math yet).
    price_usd = market.get("price_usd")
    hashrate_1m = stats.get("hashrate_1m", 0) or 0
    revenue_usd_per_day = None
    coins_per_day_est = None
    if price_usd and network_stats.get("network_hashrate") and network_stats.get("block_reward"):
        # Only computable if we actually have network hashrate + block reward (rare given
        # pool API limitations) — otherwise we leave it None rather than fabricate it.
        pass  # left for future enrichment once a coin's network API exposes these reliably

    errors = []
    if running and stats.get("hashrate_1m", 0) == 0:
        errors.append("Miner is running but hashrate is zero — waiting for pool connection.")
    if gpu.get("warning"):
        errors.append(f"GPU temperature is high ({gpu['temp']}°C) — check your cooling!")
    if cpu.get("temp", 0) > 85:
        errors.append(f"CPU temperature is high ({cpu['temp']}°C) — check your cooling!")
    if running and not stats.get("connected"):
        errors.append("Miner is not connected to the pool — check your internet or pool config.")
    if running and pool_stats.get("error"):
        errors.append(f"Pool API issue ({pool_stats.get('pool_name')}): {pool_stats['error']}")
    if running and gpu.get("fan_speed", 0) == 0 and gpu.get("gpu_util", 0) > 50:
        errors.append("GPU fan speed reads 0% while the GPU is under load — check for fan failure.")
    if mining_process and not running and mining_pid:
        try:
            stderr_out = mining_process.stderr.read(512).decode("utf-8", errors="ignore")
            translated = translate_error(stderr_out)
            if translated:
                errors.append(f"Miner stopped unexpectedly: {translated}")
        except Exception:
            errors.append("Miner stopped unexpectedly.")

    # Persist a lightweight snapshot for history/analytics charts, throttled to ~1/min.
    now_mono = asyncio.get_event_loop().time()
    if now_mono - _last_history_snapshot_ts > HISTORY_SNAPSHOT_INTERVAL_SECONDS:
        _last_history_snapshot_ts = now_mono
        try:
            history.insert_snapshot(
                coin=coin_key,
                hashrate_1m=hashrate_1m,
                accepted=stats.get("accepted_shares", 0),
                rejected=stats.get("rejected_shares", 0),
                pool_connected=bool(stats.get("connected")),
                gpu_temp=gpu.get("temp", 0),
                gpu_hotspot_temp=gpu.get("hotspot_temp") or 0,
                gpu_power_draw=gpu.get("power_draw", 0),
                cpu_temp=cpu.get("temp", 0),
                cpu_usage_percent=cpu.get("usage_percent", 0),
                price_usd=price_usd,
                revenue_usd_per_day=revenue_usd_per_day,
            )
        except Exception:
            logger.exception("Failed to write history snapshot")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "running": running,
        "mining": running,
        "pid": mining_pid,
        "coin": coin_key,
        "coin_label": COIN_REGISTRY.get(coin_key, {}).get("label", ""),
        "algo": COIN_REGISTRY.get(coin_key, {}).get("algo", ""),
        "wallet": wallet,
        "xmrig": stats,
        "gpu": gpu,
        "cpu": cpu,
        "system": system,
        "pool": pool_stats,
        "network": network_stats,
        "market": market,
        "profitability": {
            "coins_per_day_est": coins_per_day_est,
            "revenue_usd_per_day": revenue_usd_per_day,
            "note": "Power-cost and net-profit math is intentionally not calculated yet.",
        },
        "new_block_event": new_block_event,
        "errors": errors,
        "available_coins": [
            {"key": k, "label": v["label"], "algo": v["algo"], "pool_provider": v["pool_provider"]}
            for k, v in COIN_REGISTRY.items()
        ],
    }



def relay_process_output(stream, prefix: str) -> None:
    if stream is None:
        return

    def _pump() -> None:
        try:
            for line in iter(stream.readline, ""):
                line = line.rstrip()
                if line:
                    logger.info("%s%s", prefix, line)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    threading.Thread(target=_pump, daemon=True).start()


# ── PERIODIC PLAIN-ENGLISH LOG ───────────────────────────────────────────────
def format_periodic_entry(coin_key: str, stats: dict, gpu: dict, cpu: dict) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not coin_key:
        return f"[{timestamp}] Miner idle — nothing is currently being mined."

    label = COIN_REGISTRY.get(coin_key, {}).get("label", coin_key)
    hashrate = stats.get("hashrate_1m", 0)
    connected = stats.get("connected", False)
    difficulty = stats.get("difficulty", 0)
    accepted = stats.get("accepted_shares", 0)
    rejected = stats.get("rejected_shares", 0)

    lines = [
        f"[{timestamp}] Coin: {label} ({coin_key})",
        f"  Hashrate: {hashrate:.2f} H/s",
        f"  Pool connection: {'connected' if connected else 'not connected'}",
        f"  Difficulty: {difficulty}",
        f"  Shares accepted: {accepted}, rejected: {rejected}",
        f"  GPU temp: {gpu.get('temp', 0)}°C, CPU temp: {cpu.get('temp', 0)}°C",
    ]
    return "\n".join(lines) + "\n"


async def periodic_logger():
    while True:
        await asyncio.sleep(PERIODIC_LOG_INTERVAL_SECONDS)
        try:
            running, stats = await get_mining_snapshot()
            gpu = get_gpu_stats()
            cpu = get_cpu_stats()
            entry = format_periodic_entry(active_coin if running else None, stats, gpu, cpu)
            with open(PERIODIC_LOG_PATH, "a") as f:
                f.write(entry + "\n")
            logger.info("Wrote periodic log entry")
        except Exception:
            logger.exception("Periodic logger failed")


@app.get("/tunnel/status")
async def tunnel_status():
    """Return the current Cloudflare tunnel URL (written by start.sh)."""
    url_file = Path("/tmp/tunnel_url")
    cf_log   = Path("/tmp/cf_tunnel.log")

    url = ""
    connected = False
    error = ""

    if url_file.exists():
        url = url_file.read_text().strip()
        connected = url.startswith("https://")

    if not connected and cf_log.exists():
        log_text = cf_log.read_text()
        import re
        match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', log_text)
        if match:
            url = match.group(0)
            connected = True
            # Update the cache file
            url_file.write_text(url + "\n")
        elif "ERR" in log_text or "error" in log_text.lower():
            # Grab last error line
            for line in reversed(log_text.splitlines()):
                if line.strip():
                    error = line.strip()
                    break

    return {"connected": connected, "url": url, "error": error}


@app.get("/logs")
async def get_logs(limit_entries: int = 20):
    """Return the most recent periodic log entries as plain text blocks."""
    if not PERIODIC_LOG_PATH.exists():
        return {"entries": []}
    raw = PERIODIC_LOG_PATH.read_text()
    blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
    return {"entries": blocks[-limit_entries:][::-1]}


async def log_mining_console() -> None:
    last_summary = None
    while True:
        await asyncio.sleep(10)
        if not is_mining():
            if last_summary != "idle":
                logger.info("[mine] idle")
                last_summary = "idle"
            continue
        stats = await get_engine_stats(active_coin)
        summary = (
            f"[mine] coin={active_coin} pid={mining_pid} "
            f"hashrate={stats.get('hashrate_1m', 0):.0f} H/s "
            f"accepted={stats.get('accepted_shares', 0)} "
            f"rejected={stats.get('rejected_shares', 0)} "
            f"pool={stats.get('pool', 'N/A')} "
            f"connected={stats.get('connected', False)}"
        )
        if summary != last_summary:
            logger.info(summary)
            last_summary = summary


async def periodic_market_refresh():
    """Refresh CoinGecko prices on a multi-minute cycle (rate-limit friendly)."""
    while True:
        try:
            await refresh_market_cache()
            logger.info("Refreshed market data cache")
        except Exception:
            logger.exception("Market data refresh failed")
        await asyncio.sleep(4 * 60)


@app.on_event("startup")
async def start_background_tasks():
    global console_log_task, periodic_log_task, market_refresh_task
    if console_log_task is None:
        logger.info("Starting background mining console logger")
        console_log_task = asyncio.create_task(log_mining_console())
    if periodic_log_task is None:
        logger.info("Starting periodic plain-English logger (every 30 min)")
        periodic_log_task = asyncio.create_task(periodic_logger())
    if market_refresh_task is None:
        logger.info("Starting periodic market data refresh (every 4 min)")
        market_refresh_task = asyncio.create_task(periodic_market_refresh())
        await refresh_market_cache(force=True)  # populate cache immediately on boot


def _stop_pid(pid: int, timeout_seconds: float = 5.0) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        logger.exception("Error sending SIGTERM to PID %s", pid)
        return

    waited = 0.0
    step = 0.25
    while waited < timeout_seconds:
        try:
            proc = psutil.Process(pid)
            if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                return
        except psutil.NoSuchProcess:
            return
        import time as _time
        _time.sleep(step)
        waited += step

    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


def _stop_all_known_miners(timeout_seconds: float = 5.0) -> list[tuple[str, int]]:
    stopped: list[tuple[str, int]] = []
    seen_pids: set[int] = set()
    for coin_key in COIN_REGISTRY:
        pid = find_mining_pid(coin_key)
        if pid and pid not in seen_pids:
            logger.info("Stopping existing %s miner process with PID %s", coin_key, pid)
            _stop_pid(pid, timeout_seconds=timeout_seconds)
            stopped.append((coin_key, pid))
            seen_pids.add(pid)
    return stopped


def _stop_current_process(timeout_seconds: float = 5.0) -> list[tuple[str, int]]:
    """Stop whatever miner is currently running and wait for it to fully exit."""
    global mining_process, mining_pid, active_coin
    sync_active_miner_from_processes()
    stopped = _stop_all_known_miners(timeout_seconds=timeout_seconds)

    mining_process = None
    mining_pid = None
    active_coin = None
    return stopped


@app.post("/mine/start")
async def start_mining(req: MineRequest = Body(...)):
    global mining_process, mining_pid, active_coin
    coin_key = req.coin.upper()
    logger.info("Start mining requested for coin: %s", coin_key)

    if coin_key not in COIN_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unsupported coin: {coin_key}")

    # If something is already mining, stop it first — this is the switch path.
    sync_active_miner_from_processes()
    if is_mining():
        if active_coin == coin_key:
            logger.info("Start mining skipped because %s is already running", coin_key)
            return {"status": "already_running", "message": f"{coin_key} is already mining."}
        logger.info("Switching from %s to %s — stopping current miner first", active_coin, coin_key)
        _stop_current_process()
        await asyncio.sleep(1)

    entry = COIN_REGISTRY[coin_key]
    binary_path = XMRIG_PATH if entry["engine"] == "xmrig" else TREX_PATH
    config_path = str(entry["config"])

    if not os.path.exists(binary_path):
        raise HTTPException(status_code=500, detail=f"Miner binary not found at {binary_path}. Run setup.sh first.")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=500, detail=f"Config file not found at {config_path}.")

    try:
        logger.info("Launching %s: %s --config %s", entry["engine"], binary_path, config_path)
        proc = subprocess.Popen(
            [binary_path, "--config", config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(BIN_DIR),
        )
        mining_process = proc
        mining_pid = proc.pid
        active_coin = coin_key
        logger.info("%s started with PID %s", coin_key, mining_pid)
        relay_process_output(proc.stdout, f"[{coin_key}] ")
        relay_process_output(proc.stderr, f"[{coin_key} err] ")
        await asyncio.sleep(3)
        if proc.poll() is not None and proc.returncode not in (None, 0):
            logger.error("%s exited immediately with code %s", coin_key, proc.returncode)
            active_coin = None
            mining_pid = None
            raise Exception(f"Miner exited immediately with code {proc.returncode}.")
        logger.info("Mining start completed successfully for %s", coin_key)
        return {"status": "started", "pid": mining_pid, "coin": coin_key, "message": f"Mining {coin_key} started."}
    except Exception as e:
        logger.exception("Mining start failed")
        active_coin = None
        mining_pid = None
        raise HTTPException(status_code=500, detail=translate_error(str(e)))


@app.post("/mine/stop")
async def stop_mining():
    logger.info("Stop mining requested")
    sync_active_miner_from_processes()
    if not is_mining():
        logger.info("Stop mining skipped because miner is not running")
        return {"status": "not_running", "message": "Miner is not running."}
    try:
        coin_key = active_coin
        stopped = _stop_current_process()
        logger.info("Mining stopped successfully")
        stopped_coins = ", ".join(c for c, _ in stopped) or coin_key
        return {"status": "stopped", "message": f"Stopped mining: {stopped_coins}."}
    except Exception as e:
        logger.exception("Mining stop failed")
        raise HTTPException(status_code=500, detail=translate_error(str(e)))


@app.get("/mine/status")
async def mine_status():
    payload = await build_dashboard_payload()
    logger.info("Mine status requested: running=%s pid=%s coin=%s", payload["running"], mining_pid, active_coin)
    return payload


@app.get("/history/snapshots")
async def history_snapshots(hours: float = 24.0):
    """Time-series data for the History/Analytics page charts."""
    hours = max(0.1, min(hours, 24 * 30))  # clamp to a sane range (up to 30 days)
    rows = history.get_snapshots_since(hours=hours)
    return {"hours": hours, "count": len(rows), "snapshots": rows}


@app.get("/history/blocks")
async def history_blocks(limit: int = 50):
    """All blocks our address has been credited with finding, most recent first."""
    rows = history.get_blocks_found(limit=limit)
    return {"blocks": rows}


@app.get("/market/snapshot")
async def market_snapshot():
    """Current cached coin price/market data for all tracked coins."""
    return {"coins": get_cached_market_snapshot(), "tracked": list(COINGECKO_IDS.keys())}


@app.get("/pool/status")
async def pool_status(coin: str = ""):
    """On-demand pool stats for a specific coin (defaults to the active coin)."""
    coin_key = (coin or active_coin or "XMR").upper()
    if coin_key not in COIN_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unsupported coin: {coin_key}")
    wallet = get_wallet_for_coin(coin_key)
    stats = await fetch_pool_stats(coin_key, wallet)
    return stats


@app.websocket("/ws/stats")
async def websocket_stats(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected from %s", websocket.client)
    try:
        while True:
            payload = await build_dashboard_payload()
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from %s", websocket.client)
    except Exception:
        logger.exception("WebSocket stats loop failed")
        try:
            await websocket.send_text(json.dumps({"error": "Connection to the mining rig was interrupted."}))
        except Exception:
            pass


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """Serve the built React dashboard from the same origin as the API."""
    index_path = FRONTEND_BUILD_DIR / "index.html"
    requested_path = FRONTEND_BUILD_DIR / full_path
    no_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    if requested_path.is_file():
        return FileResponse(requested_path)
    if index_path.is_file():
        return FileResponse(index_path, headers=no_cache_headers)
    raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build in frontend/.")
