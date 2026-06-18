"""
Network-level stats and "did we find a block" detection.

These read from the same pool APIs as pool_clients.py, but hit the
pool-wide /stats or /blocks endpoints (not the per-address endpoint),
since that's where network height/difficulty and the pool's recent
blocks list live.

Field availability differs across the three pool families and is not
fully documented publicly, so every accessor here is defensive: it
tries several plausible key names, logs what it actually got back on
its first miss per process lifetime (so misalignment is debuggable),
and never raises — it always returns a best-effort dict with explicit
None/0 defaults rather than guessing a wrong number.
"""
import logging
import httpx

logger = logging.getLogger("isfcr-mining-console.network")

HTTP_TIMEOUT = 8.0
_warned_shapes: set[str] = set()


def _warn_once(key: str, msg: str):
    if key not in _warned_shapes:
        logger.warning(msg)
        _warned_shapes.add(key)


def _empty_network_stats() -> dict:
    return {
        "network_hashrate": None,
        "network_difficulty": None,
        "block_height": None,
        "block_reward": None,
        "block_time_seconds": None,
        "pool_hashrate_total": None,
        "miners_count": None,
    }


async def fetch_2miners_network_stats(coin_subdomain: str) -> dict:
    url = f"https://{coin_subdomain}.2miners.com/api/stats"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("2Miners network stats unreachable for %s: %s", coin_subdomain, e)
        return _empty_network_stats()

    network = data.get("network", {}) if isinstance(data.get("network"), dict) else {}
    if not network:
        _warn_once(f"2miners-network-{coin_subdomain}", f"2Miners /api/stats for {coin_subdomain} has no 'network' key — got top-level keys: {list(data.keys())}")

    pool = data.get("pool", {}) if isinstance(data.get("pool"), dict) else {}

    result = _empty_network_stats()
    result.update({
        "network_hashrate": network.get("difficulty") and None,  # placeholder, replaced below if present
        "network_difficulty": network.get("difficulty"),
        "block_height": network.get("height"),
        "pool_hashrate_total": pool.get("hashrate"),
        "miners_count": pool.get("miners"),
    })
    # 2Miners sometimes reports network hashrate directly
    if "hashrate" in network:
        result["network_hashrate"] = network.get("hashrate")
    return result


async def fetch_herominers_network_stats(coin_subdomain: str, wallet: str) -> dict:
    """HeroMiners doesn't have a no-address /stats endpoint that's documented;
    we reuse stats_address (any valid-looking address) which includes networkHeight."""
    url = f"https://{coin_subdomain}.herominers.com/api/stats_address"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(url, params={"address": wallet})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("HeroMiners network stats unreachable for %s: %s", coin_subdomain, e)
        return _empty_network_stats()

    s = data.get("stats", {}) or {}
    result = _empty_network_stats()
    result.update({
        "block_height": s.get("networkHeight"),
        "pool_hashrate_total": s.get("poolRoundHashes"),
    })
    return result


async def fetch_moneroocean_network_stats() -> dict:
    """MoneroOcean's per-miner endpoint doesn't expose XMR network difficulty/height.
    Returning empty rather than guessing; the UI shows 'unavailable' for this pool."""
    return _empty_network_stats()


NETWORK_DISPATCH = {
    "XMR":  {"family": "moneroocean"},
    "ALPH": {"family": "herominers", "subdomain": "alephium"},
    "ETC":  {"family": "2miners", "subdomain": "etc"},
    "RVN":  {"family": "2miners", "subdomain": "rvn"},
    "ERG":  {"family": "2miners", "subdomain": "erg"},
}


async def fetch_network_stats(coin_key: str, wallet: str = "") -> dict:
    entry = NETWORK_DISPATCH.get(coin_key)
    if not entry:
        return _empty_network_stats()
    family = entry["family"]
    if family == "moneroocean":
        return await fetch_moneroocean_network_stats()
    elif family == "herominers":
        return await fetch_herominers_network_stats(entry["subdomain"], wallet)
    elif family == "2miners":
        return await fetch_2miners_network_stats(entry["subdomain"])
    return _empty_network_stats()
