"""
Pool API clients for ISFCR Mining Console.

Each coin reports to a different pool family:
  XMR  -> MoneroOcean   (api.moneroocean.stream)
  ALPH -> HeroMiners     (alephium.herominers.com/api)
  ETC  -> 2Miners        (etc.2miners.com/api)
  RVN  -> 2Miners        (rvn.2miners.com/api)
  ERG  -> 2Miners        (erg.2miners.com/api)

All three families expose different JSON shapes. This module fetches from
whichever family a coin uses and normalizes the result into a single
PoolStats-shaped dict so the rest of the backend (and the frontend) never
has to know which pool API is behind a given coin.

Normalized shape (all fields always present, defaults applied on failure):
{
    "pool_name": str,
    "reachable": bool,            # did the HTTP call succeed at all
    "pool_hashrate": float,       # H/s as reported for this worker/address by the pool
    "effective_hashrate": float,  # average over the pool's own short window
    "workers_online": int,
    "worker_status": "online" | "offline" | "unknown",
    "pending_balance": float,     # coin units
    "immature_balance": float,
    "paid_total": float,
    "last_payout_ts": int | None, # unix seconds
    "pool_difficulty": float,
    "pool_luck_percent": float | None,
    "pool_fee_percent": float | None,
    "latency_ms": float | None,
    "blocks_found": int,          # blocks this address/worker has found, all-time (from pool data, best-effort)
    "new_block_height": int | None,   # most recent block height the pool told us about (for block-found detection)
    "raw": dict,                  # original response, for debugging / advanced fields
    "error": str | None,
}
"""
import time
import logging
import httpx

logger = logging.getLogger("isfcr-mining-console.pools")

HTTP_TIMEOUT = 8.0


def _empty_pool_stats(pool_name: str, error: str | None = None) -> dict:
    return {
        "pool_name": pool_name,
        "reachable": False,
        "pool_hashrate": 0.0,
        "effective_hashrate": 0.0,
        "workers_online": 0,
        "worker_status": "unknown",
        "pending_balance": 0.0,
        "immature_balance": 0.0,
        "paid_total": 0.0,
        "last_payout_ts": None,
        "pool_difficulty": 0.0,
        "pool_luck_percent": None,
        "pool_fee_percent": None,
        "latency_ms": None,
        "blocks_found": 0,
        "new_block_height": None,
        "raw": {},
        "error": error,
    }


async def _timed_get(client: httpx.AsyncClient, url: str, **kwargs):
    start = time.monotonic()
    resp = await client.get(url, **kwargs)
    elapsed_ms = (time.monotonic() - start) * 1000.0
    return resp, elapsed_ms


# ── MoneroOcean (XMR) ─────────────────────────────────────────────────────
# Docs / community-confirmed endpoint: https://api.moneroocean.stream/miner/<wallet>/stats
async def fetch_moneroocean_stats(wallet: str) -> dict:
    pool_name = "MoneroOcean"
    if not wallet:
        return _empty_pool_stats(pool_name, "No wallet configured")
    url = f"https://api.moneroocean.stream/miner/{wallet}/stats"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp, latency_ms = await _timed_get(client, url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as e:
        logger.warning("MoneroOcean API unreachable: %s", e)
        return _empty_pool_stats(pool_name, f"Pool unreachable: {e}")
    except Exception as e:
        logger.warning("MoneroOcean API error: %s", e)
        return _empty_pool_stats(pool_name, f"Pool error: {e}")

    # MoneroOcean's miner/stats response carries fields under varying keys
    # across pool-software versions; we defensively probe several names.
    amt_due = data.get("amtDue", 0) or 0
    amt_paid = data.get("amtPaid", 0) or 0
    hashrate = data.get("hash", data.get("hashrate", 0)) or 0
    hashrate2 = data.get("hash2", hashrate) or hashrate
    last_share_ts = data.get("lastShare")
    workers = data.get("workers", [])
    workers_online = len(workers) if isinstance(workers, list) else (1 if hashrate else 0)

    # amounts on MoneroOcean/cryptonote-pool-style stacks are usually in
    # piconero (1e-12 XMR) — convert defensively only if values look huge.
    def to_xmr(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return v / 1e12 if v > 1e6 else v

    stats = _empty_pool_stats(pool_name)
    stats.update({
        "reachable": True,
        "pool_hashrate": float(hashrate),
        "effective_hashrate": float(hashrate2),
        "workers_online": workers_online,
        "worker_status": "online" if hashrate and hashrate > 0 else ("offline" if last_share_ts else "unknown"),
        "pending_balance": to_xmr(amt_due),
        "paid_total": to_xmr(amt_paid),
        "last_payout_ts": data.get("lastPayment") or None,
        "raw": data,
        "error": None,
    })
    return stats


# ── HeroMiners (ALPH) ────────────────────────────────────────────────────
# Confirmed shape via live fetch: https://<coin>.herominers.com/api/stats_address?address=<wallet>
async def fetch_herominers_stats(coin_subdomain: str, wallet: str) -> dict:
    pool_name = "HeroMiners"
    if not wallet:
        return _empty_pool_stats(pool_name, "No wallet configured")
    url = f"https://{coin_subdomain}.herominers.com/api/stats_address"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp, latency_ms = await _timed_get(client, url, params={"address": wallet, "longpoll": "false"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as e:
        logger.warning("HeroMiners API unreachable: %s", e)
        return _empty_pool_stats(pool_name, f"Pool unreachable: {e}")
    except Exception as e:
        logger.warning("HeroMiners API error: %s", e)
        return _empty_pool_stats(pool_name, f"Pool error: {e}")

    s = data.get("stats", {}) or {}
    workers = data.get("workers", []) or []
    blocks_found_pool_addr = s.get("blocksFoundPool", 0) or 0
    network_height = s.get("networkHeight")

    pool_hashrate = s.get("hashrate", 0) or 0
    round_hashes = s.get("roundHashes", 0) or 0
    shares_good = s.get("shares_good", 0) or 0
    shares_invalid = s.get("shares_invalid", 0) or 0
    shares_stale = s.get("shares_stale", 0) or 0

    stats = _empty_pool_stats(pool_name)
    stats.update({
        "reachable": True,
        "pool_hashrate": float(pool_hashrate),
        "effective_hashrate": float(pool_hashrate),
        "workers_online": len(workers),
        "worker_status": "online" if pool_hashrate and pool_hashrate > 0 else ("offline" if workers is not None else "unknown"),
        "pending_balance": 0.0,  # HeroMiners stats_address doesn't expose a pending balance field directly
        "paid_total": sum(p.get("amount", 0) for p in (data.get("payments") or []) if isinstance(p, dict)) / 1e9
            if data.get("payments") else 0.0,
        "blocks_found": blocks_found_pool_addr,
        "new_block_height": network_height,
        "raw": data,
        "error": None,
        "_shares_good": shares_good,
        "_shares_invalid": shares_invalid,
        "_shares_stale": shares_stale,
    })
    return stats


# ── 2Miners (ETC / RVN / ERG) ────────────────────────────────────────────
# Confirmed via official docs: GET https://<coin>.2miners.com/api/accounts/<wallet>
async def fetch_2miners_stats(coin_subdomain: str, wallet: str) -> dict:
    pool_name = "2Miners"
    if not wallet:
        return _empty_pool_stats(pool_name, "No wallet configured")
    url = f"https://{coin_subdomain}.2miners.com/api/accounts/{wallet}"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp, latency_ms = await _timed_get(client, url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as e:
        logger.warning("2Miners API unreachable: %s", e)
        return _empty_pool_stats(pool_name, f"Pool unreachable: {e}")
    except Exception as e:
        logger.warning("2Miners API error: %s", e)
        return _empty_pool_stats(pool_name, f"Pool error: {e}")

    current_hashrate = data.get("currentHashrate", 0) or 0
    hashrate_avg = data.get("hashrate", current_hashrate) or current_hashrate
    workers = data.get("workers", {}) or {}
    workers_online = 0
    if isinstance(workers, dict):
        for w in workers.values():
            if isinstance(w, dict) and (w.get("hashrate", 0) or 0) > 0:
                workers_online += 1

    stats = _empty_pool_stats(pool_name)
    stats.update({
        "reachable": True,
        "pool_hashrate": float(current_hashrate),
        "effective_hashrate": float(hashrate_avg),
        "workers_online": workers_online if workers else (1 if current_hashrate else 0),
        "worker_status": "online" if current_hashrate and current_hashrate > 0 else "offline",
        "pending_balance": float(data.get("stats", {}).get("balance", 0) or 0) / 1e9 if isinstance(data.get("stats"), dict) else 0.0,
        "immature_balance": float(data.get("stats", {}).get("immature", 0) or 0) / 1e9 if isinstance(data.get("stats"), dict) else 0.0,
        "paid_total": float(data.get("stats", {}).get("paid", 0) or 0) / 1e9 if isinstance(data.get("stats"), dict) else 0.0,
        "raw": data,
        "error": None,
    })
    return stats


# ── Coin -> pool dispatcher ───────────────────────────────────────────────
# Maps each coin to the pool family + subdomain needed for the API calls.
# Wallets are read out of each coin's miner config file by the caller and
# passed in here, so this module has zero hardcoded wallet addresses.
POOL_DISPATCH = {
    "XMR":  {"family": "moneroocean", "subdomain": None},
    "ALPH": {"family": "herominers",  "subdomain": "alephium"},
    "ETC":  {"family": "2miners",     "subdomain": "etc"},
    "RVN":  {"family": "2miners",     "subdomain": "rvn"},
    "ERG":  {"family": "2miners",     "subdomain": "erg"},
}


async def fetch_pool_stats(coin_key: str, wallet: str) -> dict:
    """Single entrypoint: fetch normalized pool stats for any supported coin."""
    entry = POOL_DISPATCH.get(coin_key)
    if not entry:
        return _empty_pool_stats("unknown", f"No pool mapping for coin {coin_key}")

    family = entry["family"]
    try:
        if family == "moneroocean":
            return await fetch_moneroocean_stats(wallet)
        elif family == "herominers":
            return await fetch_herominers_stats(entry["subdomain"], wallet)
        elif family == "2miners":
            return await fetch_2miners_stats(entry["subdomain"], wallet)
    except Exception as e:
        logger.exception("Unexpected error fetching pool stats for %s", coin_key)
        return _empty_pool_stats(family, f"Unexpected error: {e}")

    return _empty_pool_stats(family, "Unhandled pool family")
