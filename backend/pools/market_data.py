"""
Coin market data (price, market cap, 24h volume) via CoinGecko's free public API.

Per product decision: refreshed on a multi-minute cycle (not on every request)
to stay well within CoinGecko's free-tier rate limits. The FastAPI app calls
get_market_snapshot() from a background task on a timer; everything else reads
the cached result instantly.
"""
import time
import logging
import httpx

logger = logging.getLogger("isfcr-mining-console.market")

HTTP_TIMEOUT = 8.0
CACHE_TTL_SECONDS = 4 * 60  # refresh at most every 4 minutes

# CoinGecko coin IDs for each ticker we mine
COINGECKO_IDS = {
    "XMR": "monero",
    "ALPH": "alephium",
    "ETC": "ethereum-classic",
    "RVN": "ravencoin",
    "ERG": "ergo",
}

_cache: dict = {}
_cache_ts: float = 0.0


def _empty_market_entry() -> dict:
    return {
        "price_usd": None,
        "market_cap_usd": None,
        "volume_24h_usd": None,
        "change_24h_percent": None,
    }


async def _fetch_coingecko_prices(ids: list[str]) -> dict:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(ids),
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as e:
        logger.warning("CoinGecko unreachable: %s", e)
        return {}
    except Exception as e:
        logger.warning("CoinGecko error: %s", e)
        return {}


async def refresh_market_cache(force: bool = False) -> dict:
    """Fetch fresh prices for all tracked coins if the cache is stale."""
    global _cache, _cache_ts
    now = time.monotonic()
    if not force and _cache and (now - _cache_ts) < CACHE_TTL_SECONDS:
        return _cache

    raw = await _fetch_coingecko_prices(list(COINGECKO_IDS.values()))
    new_cache = {}
    for coin_key, gecko_id in COINGECKO_IDS.items():
        entry = raw.get(gecko_id)
        if not entry:
            new_cache[coin_key] = _empty_market_entry()
            continue
        new_cache[coin_key] = {
            "price_usd": entry.get("usd"),
            "market_cap_usd": entry.get("usd_market_cap"),
            "volume_24h_usd": entry.get("usd_24h_vol"),
            "change_24h_percent": entry.get("usd_24h_change"),
        }

    if raw:
        # Only replace the cache (and bump timestamp) if we actually got data;
        # on a failed fetch we keep serving the last good snapshot.
        _cache = new_cache
        _cache_ts = now
    elif not _cache:
        _cache = new_cache

    return _cache


def get_cached_market_snapshot() -> dict:
    """Synchronous read of whatever is currently cached (may be empty on first boot)."""
    if not _cache:
        return {k: _empty_market_entry() for k in COINGECKO_IDS}
    return _cache
