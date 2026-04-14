import sys
import os
import logging

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

from api_server import analyze

logging.basicConfig(level=logging.ERROR)

def test_api():
    print(f"API KEY LOADED: {os.getenv('AVE_API_KEY')[:5]}...")
    
    print("\n--- Testing API Route logic for UNI on ethereum ---")
    try:
        res = analyze(token="UNI", chain="ethereum")
        print("API Response:", res)
    except Exception as e:
        print("API exception:", e)

if __name__ == "__main__":
    test_api()
