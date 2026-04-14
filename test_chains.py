import os
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

from ave_monitor import AveAccumulationMonitor
monitor = AveAccumulationMonitor()

for ch in ["avalanche", "avax", "polygon", "matic", "arbitrum", "base", "optimism"]:
    try:
        res = monitor._fetch_chain_token_candidates(ch, 1)
        print(f"{ch} -> {'OK' if res else 'EMPTY'}")
    except Exception as e:
        print(f"{ch} -> FAIL: {e}")
