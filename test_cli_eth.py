import os

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

import ave_monitor
import sys

if __name__ == "__main__":
    sys.argv = ["ave_monitor.py", "--mode", "sweep", "--chain", "ethereum", "--top", "5"]
    ave_monitor.main()
