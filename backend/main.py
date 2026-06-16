import asyncio
import json
import logging
import subprocess
import threading
import psutil
import httpx
import os
import signal
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("xmr-dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

XMRIG_PATH = "/home/isfcr/crypto_mining/monero/xmrig"
XMRIG_CONFIG = "/home/isfcr/crypto_mining/monero/config.json"
XMRIG_API = "http://127.0.0.1:4048"

class MineRequest(BaseModel):
    coin: str = "XMR"

COIN_CONFIGS = {
    "XMR": {"algo": "rx/0", "url": "gulf.moneroocean.stream:10128", "label": "Monero"},
    "ETC": {"algo": "etchash", "url": "etc.2miners.com:1010", "label": "Ethereum Classic"},
    "ALPH": {"algo": "blake3", "url": "pool.woolypooly.com:3106", "label": "Alephium"},
    "RVN": {"algo": "kawpow", "url": "rvn.2miners.com:6060", "label": "Ravencoin"},
    "ERG": {"algo": "autolykos2", "url": "erg.2miners.com:8888", "label": "Ergo"},
}

def patch_config_for_coin(coin_key: str):
    coin_key = coin_key.upper()
    if coin_key not in COIN_CONFIGS:
        raise ValueError(f"Unsupported coin: {coin_key}")
    
    with open(XMRIG_CONFIG, "r") as f:
        config = json.load(f)
    
    target = COIN_CONFIGS[coin_key]
    if "pools" in config and config["pools"]:
        config["pools"][0]["algo"] = target["algo"]
        config["pools"][0]["url"] = target["url"]
    
    with open(XMRIG_CONFIG, "w") as f:
        json.dump(config, f, indent=4)


mining_process = None
mining_pid = None
console_log_task = None


def find_mining_pid():
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if not cmdline:
                continue
            if XMRIG_PATH in cmdline[0] and XMRIG_CONFIG in cmdline:
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def get_current_coin_from_config():
    try:
        with open(XMRIG_CONFIG, "r") as f:
            config = json.load(f)
        url = config["pools"][0]["url"]
        for k, v in COIN_CONFIGS.items():
            if v["url"] == url: return k
    except: pass
    return "XMR"


def translate_error(raw: str) -> str:
    raw_lower = raw.lower()
    if "connection refused" in raw_lower or "connect" in raw_lower:
        return "Cannot reach the mining pool — check your internet connection."
    if "invalid" in raw_lower and "share" in raw_lower:
        return "Submitted a share but the pool rejected it — this is sometimes normal."
    if "no active pool" in raw_lower:
        return "No mining pool configured — check your config.json."
    if "permission denied" in raw_lower:
        return "XMRig doesn't have permission to run — try: chmod +x xmrig"
    if "huge pages" in raw_lower:
        return "Huge pages not enabled — mining will work but at lower efficiency."
    if "cuda" in raw_lower or "opencl" in raw_lower:
        return "GPU driver issue detected — check your Nvidia drivers."
    if "killed" in raw_lower or "signal 9" in raw_lower:
        return "Miner was force-stopped."
    if raw.strip():
        return f"Miner error: {raw.strip()}"
    return ""


def empty_xmrig_stats() -> dict:
    return {
        "hashrate_1m": 0,
        "hashrate_10m": 0,
        "hashrate_1h": 0,
        "accepted_shares": 0,
        "rejected_shares": 0,
        "pool": "N/A",
        "uptime": 0,
        "difficulty": 0,
        "connected": False,
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


async def get_xmrig_stats():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            logger.info("Querying XMRig stats from %s", XMRIG_API)
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
        return empty_xmrig_stats()
    except Exception as e:
        logger.exception("XMRig API error")
        return empty_xmrig_stats()
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
    global mining_pid
    if mining_pid is None:
        mining_pid = find_mining_pid()
        if mining_pid is None:
            return False
    try:
        proc = psutil.Process(mining_pid)
        if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
            return True
        mining_pid = find_mining_pid()
        return mining_pid is not None
    except psutil.NoSuchProcess:
        mining_pid = find_mining_pid()
        return mining_pid is not None


async def get_mining_snapshot():
    xmrig_stats = await get_xmrig_stats()
    running = is_mining()

    if xmrig_stats.get("uptime", 0) > 0 or xmrig_stats.get("connected"):
        running = True
        global mining_pid
        if mining_pid is None:
            mining_pid = find_mining_pid()

    return running, xmrig_stats


async def build_dashboard_payload():
    running, xmrig = await get_mining_snapshot()
    gpu = get_gpu_stats()
    cpu = get_cpu_stats()

    errors = []
    if running and xmrig.get("hashrate_1m", 0) == 0:
        errors.append("Miner is running but hashrate is zero — waiting for pool connection.")
    if gpu.get("warning"):
        errors.append(f"GPU temperature is high ({gpu['temp']}°C) — check your cooling!")
    if cpu.get("temp", 0) > 85:
        errors.append(f"CPU temperature is high ({cpu['temp']}°C) — check your cooling!")
    if running and not xmrig.get("connected"):
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
        "xmrig": xmrig,
        "gpu": gpu,
        "cpu": cpu,
        "coin": get_current_coin_from_config(),
        "errors": errors,
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


async def log_mining_console() -> None:
    last_summary = None
    while True:
        await asyncio.sleep(10)
        if not is_mining():
            if last_summary != "idle":
                logger.info("[mine] idle")
                last_summary = "idle"
            continue

        xmrig = await get_xmrig_stats()
        summary = (
            f"[mine] pid={mining_pid} "
            f"hashrate={xmrig.get('hashrate_1m', 0):.0f} H/s "
            f"accepted={xmrig.get('accepted_shares', 0)} "
            f"rejected={xmrig.get('rejected_shares', 0)} "
            f"pool={xmrig.get('pool', 'N/A')} "
            f"connected={xmrig.get('connected', False)}"
        )
        if summary != last_summary:
            logger.info(summary)
            last_summary = summary


@app.on_event("startup")
async def start_console_logger():
    global console_log_task
    if console_log_task is None:
        logger.info("Starting background mining console logger")
        console_log_task = asyncio.create_task(log_mining_console())


@app.post("/mine/start")
async def start_mining(req: MineRequest = Body(...)):
    global mining_process, mining_pid
    logger.info("Start mining requested for coin: %s", req.coin)
    if is_mining():
        logger.info("Start mining skipped because miner is already running")
        return {"status": "already_running", "message": "Miner is already running."}
    try:
        logger.info("Patching config for %s", req.coin)
        patch_config_for_coin(req.coin)
        
        logger.info("Launching XMRig: %s --config %s", XMRIG_PATH, XMRIG_CONFIG)
        proc = subprocess.Popen(
            [XMRIG_PATH, "--config", XMRIG_CONFIG],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd="/home/isfcr/crypto_mining/monero"
        )
        mining_process = proc
        mining_pid = proc.pid
        logger.info("XMRig started with PID %s", mining_pid)
        relay_process_output(proc.stdout, "[XMRig] ")
        relay_process_output(proc.stderr, "[XMRig err] ")
        await asyncio.sleep(2)
        if proc.poll() is not None and proc.returncode not in (None, 0):
            logger.error("XMRig exited immediately with code %s", proc.returncode)
            raise Exception(f"XMRig exited immediately with code {proc.returncode}.")
        if not is_mining():
            logger.error("XMRig is not running after startup delay")
            raise Exception("XMRig exited immediately after starting.")
        logger.info("Mining start completed successfully")
        return {"status": "started", "pid": mining_pid, "message": "Mining started."}
    except Exception as e:
        logger.exception("Mining start failed")
        raise HTTPException(status_code=500, detail=translate_error(str(e)))


@app.post("/mine/stop")
async def stop_mining():
    global mining_process, mining_pid
    logger.info("Stop mining requested")
    if not is_mining():
        logger.info("Stop mining skipped because miner is not running")
        return {"status": "not_running", "message": "Miner is not running."}
    try:
        logger.info("Sending SIGTERM to PID %s", mining_pid)
        os.kill(mining_pid, signal.SIGTERM)
        await asyncio.sleep(2)
        if is_mining():
            logger.warning("Miner still running after SIGTERM; sending SIGKILL to PID %s", mining_pid)
            os.kill(mining_pid, signal.SIGKILL)
        mining_pid = None
        mining_process = None
        logger.info("Mining stopped successfully")
        return {"status": "stopped", "message": "Mining stopped."}
    except Exception as e:
        logger.exception("Mining stop failed")
        raise HTTPException(status_code=500, detail=translate_error(str(e)))


@app.get("/mine/status")
async def mine_status():
    payload = await build_dashboard_payload()
    running = payload["running"]
    logger.info("Mine status requested: running=%s pid=%s", running, mining_pid)
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
    except Exception as e:
        logger.exception("WebSocket stats loop failed")
        try:
            await websocket.send_text(json.dumps({"error": translate_error(str(e))}))
        except Exception:
            pass
