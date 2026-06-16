#!/usr/bin/env python3
"""
Patches the user's existing XMRig config.json to enable the HTTP API on port 4048
and point mining at MoneroOcean.
Run once during setup. Safe to re-run.
"""
import json, sys, shutil, os

CONFIG_PATH = "/home/isfcr/crypto_mining/monero/config.json"
BACKUP_PATH = CONFIG_PATH + ".bak"
WALLET_ADDRESS = "43becXiNcCeNAui6QGu4hvJBK2QxBqrt3PN5wYFMDJsyHHhbciXUM6h1QpWaQFtHxvKraQxCZtNfNB4Qvm12CDVJGvHL4VA"
POOL_URL = "gulf.moneroocean.stream:10128"
SAFE_THREAD_COUNT = 28

if not os.path.exists(CONFIG_PATH):
    print(f"ERROR: config.json not found at {CONFIG_PATH}")
    sys.exit(1)

shutil.copy2(CONFIG_PATH, BACKUP_PATH)
print(f"Backed up original config to {BACKUP_PATH}")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

safe_threads = list(range(SAFE_THREAD_COUNT))

pool_entry = {
    "algo": None,
    "coin": None,
    "url": POOL_URL,
    "user": WALLET_ADDRESS,
    "pass": "x",
    "rig-id": None,
    "nicehash": False,
    "keepalive": False,
    "enabled": True,
    "tls": False,
    "sni": False,
    "tls-fingerprint": None,
    "daemon": False,
    "socks5": None,
    "self-select": None,
    "submit-to-origin": False,
}

if isinstance(config.get("pools"), list) and config["pools"]:
    config["pools"][0].update(pool_entry)
else:
    config["pools"] = [pool_entry]

cpu_config = config.setdefault("cpu", {})
for key in ["rx", "rx/wow"]:
    cpu_config[key] = safe_threads.copy()

config["http"] = {
    "enabled": True,
    "host": "127.0.0.1",
    "port": 4048,
    "restricted": True
}

with open(CONFIG_PATH, "w") as f:
    json.dump(config, f, indent=4)

print(f"XMRig pool set to MoneroOcean at {POOL_URL} for wallet {WALLET_ADDRESS}")
print(f"XMRig thread cap set to {SAFE_THREAD_COUNT} logical threads")
print("XMRig HTTP API enabled on port 4048 without authentication")
print("Done. Your original config is backed up as config.json.bak")
