import sys
import os
import logging
import json

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

from ave_monitor import AveAccumulationMonitor
monitor = AveAccumulationMonitor()

try:
    candidates_eth = monitor._make_request("/v2/tokens/trending", {"chain": "eth", "page_size": 2})
    print("RAW ETH payload:")
    print(json.dumps(candidates_eth, indent=2))
except Exception as e:
    print(f"Error fetching candidates for 'eth': {e}")
