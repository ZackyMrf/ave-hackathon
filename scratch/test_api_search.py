import os
import requests
import json

BASE_URL = "https://api.agacve.com/v1"
COOKIE = "8df7699da1955497d3b08f7b724aa5691739944167617719326"

def get_tokens_by_chain(chain: str = "eth", limit: int = 50):
    url = f"{BASE_URL}/api/v3/tokens"
    params = {
        "chain": chain,
        "limit": limit,
        "sort": "trending"
    }
    headers = {
        "User-Agent": "Ave-Monitor/1.0",
        "Cookie": COOKIE
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"Status: {response.status_code}")
    return response.json()

if __name__ == "__main__":
    data = get_tokens_by_chain("eth", 100)
    tokens = data.get("data", [])
    
    print(f"Found {len(tokens)} tokens")
    
    uni_tokens = [t for t in tokens if t.get("symbol") == "UNI"]
    print(f"Tokens with symbol UNI: {len(uni_tokens)}")
    for t in uni_tokens:
        print(f"CA: {t.get('address')}, MC: {t.get('market_cap')}, Liquidity: {t.get('liquidity')}, Holder: {t.get('holder')}")
