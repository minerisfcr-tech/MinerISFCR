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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
    "XMR":  {"engine": "xmrig", "config": CONFIGS_DIR / "xmr.json",  "label": "Monero",            "api": XMRIG_API, "api_kind": "xmrig"},
    "ETC":  {"engine": "trex",  "config": CONFIGS_DIR / "etc.json",  "label": "Ethereum Classic",   "api": TREX_API,  "api_kind": "trex"},
    "RVN":  {"engine": "trex",  "config": CONFIGS_DIR / "rvn.json",  "label": "Ravencoin",          "api": TREX_API,  "api_kind": "trex"},
    "ALPH": {"engine": "trex",  "config": CONFIGS_DIR / "alph.json", "label": "Alephium",           "api": TREX_API,  "api_kind": "trex"},
    "ERG":  {"engine": "trex",  "config": CONFIGS_DIR / "erg.json",  "label": "Ergo",               "api": TREX_API,  "api_kind": "trex"},
}

# ── PROCESS STATE ────────────────────────────────────────────────────────────
mining_process = None
mining_pid = None
active_coin = None
console_log_task = None
periodic_log_task = None


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
            if binary_path in cmdline[0] and config_path in cmdline:
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


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
            "--query-gpu=temperature.gpu,utilization.gpu,utilization.memory,power.draw,power.limit,memory.used,memory.total,fan.speed,clocks.current.graphics",
            "--format=csv,noheader,nounits"
        ], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            def safe_float(val, default=0):
                try:
                    return float(val)
                except Exception:
                    return default
            temp = safe_float(parts[0])
            return {
                "temp": temp,
                "gpu_util": safe_float(parts[1]),
                "mem_util": safe_float(parts[2]),
                "power_draw": safe_float(parts[3]),
                "power_limit": safe_float(parts[4]),
                "mem_used": safe_float(parts[5]),
                "mem_total": safe_float(parts[6]),
                "fan_speed": safe_float(parts[7]),
                "clock_mhz": safe_float(parts[8]),
                "warning": temp > 82,
            }
    except Exception:
        pass
    return {
        "temp": 0, "gpu_util": 0, "mem_util": 0, "power_draw": 0,
        "power_limit": 0, "mem_used": 0, "mem_total": 0,
        "fan_speed": 0, "clock_mhz": 0, "warning": False,
    }


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


def is_mining() -> bool:
    global mining_pid, active_coin
    if mining_pid is None or active_coin is None:
        return False
    try:
        proc = psutil.Process(mining_pid)
        if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
            return True
        mining_pid = None
        return False
    except psutil.NoSuchProcess:
        mining_pid = None
        return False


async def get_mining_snapshot():
    if not active_coin:
        return False, empty_stats()
    stats = await get_engine_stats(active_coin)
    running = is_mining()
    if stats.get("uptime", 0) > 0 or stats.get("connected"):
        running = True
    return running, stats


async def build_dashboard_payload():
    running, stats = await get_mining_snapshot()
    gpu = get_gpu_stats()
    cpu = get_cpu_stats()

    errors = []
    if running and stats.get("hashrate_1m", 0) == 0:
        errors.append("Miner is running but hashrate is zero — waiting for pool connection.")
    if gpu.get("warning"):
        errors.append(f"GPU temperature is high ({gpu['temp']}°C) — check your cooling!")
    if cpu.get("temp", 0) > 85:
        errors.append(f"CPU temperature is high ({cpu['temp']}°C) — check your cooling!")
    if running and not stats.get("connected"):
        errors.append("Miner is not connected to the pool — check your internet or pool config.")
    if mining_process and not running and mining_pid:
        try:
            stderr_out = mining_process.stderr.read(512).decode("utf-8", errors="ignore")
            translated = translate_error(stderr_out)
            if translated:
                errors.append(f"Miner stopped unexpectedly: {translated}")
        except Exception:
            errors.append("Miner stopped unexpectedly.")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "running": running,
        "mining": running,
        "pid": mining_pid,
        "coin": active_coin or "XMR",
        "coin_label": COIN_REGISTRY.get(active_coin, {}).get("label", "") if active_coin else "",
        "xmrig": stats,
        "gpu": gpu,
        "cpu": cpu,
        "errors": errors,
        "available_coins": [
            {"key": k, "label": v["label"]} for k, v in COIN_REGISTRY.items()
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


@app.on_event("startup")
async def start_background_tasks():
    global console_log_task, periodic_log_task
    if console_log_task is None:
        logger.info("Starting background mining console logger")
        console_log_task = asyncio.create_task(log_mining_console())
    if periodic_log_task is None:
        logger.info("Starting periodic plain-English logger (every 30 min)")
        periodic_log_task = asyncio.create_task(periodic_logger())


def _stop_current_process(timeout_seconds: float = 5.0) -> None:
    """Stop whatever miner is currently running and wait for it to fully exit."""
    global mining_process, mining_pid, active_coin
    if mining_pid is None:
        return
    try:
        os.kill(mining_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except Exception:
        logger.exception("Error sending SIGTERM to PID %s", mining_pid)

    waited = 0.0
    step = 0.25
    while waited < timeout_seconds:
        try:
            proc = psutil.Process(mining_pid)
            if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        import time as _time
        _time.sleep(step)
        waited += step
    else:
        try:
            os.kill(mining_pid, signal.SIGKILL)
        except Exception:
            pass

    mining_process = None
    mining_pid = None
    active_coin = None


@app.post("/mine/start")
async def start_mining(req: MineRequest = Body(...)):
    global mining_process, mining_pid, active_coin
    coin_key = req.coin.upper()
    logger.info("Start mining requested for coin: %s", coin_key)

    if coin_key not in COIN_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unsupported coin: {coin_key}")

    # If something is already mining, stop it first — this is the switch path.
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
    if not is_mining():
        logger.info("Stop mining skipped because miner is not running")
        return {"status": "not_running", "message": "Miner is not running."}
    try:
        coin_key = active_coin
        _stop_current_process()
        logger.info("Mining stopped successfully")
        return {"status": "stopped", "message": f"Mining {coin_key} stopped."}
    except Exception as e:
        logger.exception("Mining stop failed")
        raise HTTPException(status_code=500, detail=translate_error(str(e)))


@app.get("/mine/status")
async def mine_status():
    payload = await build_dashboard_payload()
    logger.info("Mine status requested: running=%s pid=%s coin=%s", payload["running"], mining_pid, active_coin)
    return payload


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


# ── FRONTEND (must be mounted LAST) ──────────────────────────────────────────
# This serves the built React dashboard from the same port/origin as the API
# above (so the relative fetch('/mine/status') calls in App.js, and the
# "proxy" setting in package.json, resolve correctly once deployed). It has
# to be registered after every @app.get/@app.post/@app.websocket route —
# FastAPI matches routes in the order they were added, and a mount at "/"
# would otherwise swallow every request, including the API ones, before they
# ever reached the handlers above.
if FRONTEND_BUILD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD_DIR), html=True), name="frontend")
    logger.info("Serving frontend build from %s", FRONTEND_BUILD_DIR)
else:
    logger.warning(
        "Frontend build not found at %s — run `npm run build` in frontend/ before starting the backend, "
        "otherwise the site root will 404.",
        FRONTEND_BUILD_DIR,
    )
