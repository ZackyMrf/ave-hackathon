#!/usr/bin/env python3
"""Query Ave API directly to get REAL contract addresses"""

import requests
import os

API_KEY = os.getenv("AVE_API_KEY", "")
if not API_KEY:
    print("❌ AVE_API_KEY not set!")
    exit(1)

BASE_URL = "https://prod.ave-api.com"

tokens_to_search = ["BONK", "WIF", "PEPE", "SHIB", "TRUMP", "DOGE"]
chain = "solana"

print("\n" + "="*70)
print("QUERYING AVE API FOR REAL CONTRACT ADDRESSES")
print("="*70)

session = requests.Session()
session.headers.update({
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
})

for token_symbol in tokens_to_search:
    try:
        url = f"{BASE_URL}/v2/tokens?keyword={token_symbol}&chain={chain}&limit=1"
        print(f"\n🔍 Searching: {token_symbol}")
        print(f"   URL: {url}")
        
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"   Status: {response.status_code}")
        
        if isinstance(data, list) and len(data) > 0:
            result = data[0]
            contract_addr = result.get("token", "")
            symbol = result.get("symbol", "")
            name = result.get("name", "")
            
            print(f"\n   ✅ Found: {name} ({symbol})")
            print(f"   Contract: {contract_addr}")
            print(f"   Entry: \"{token_symbol.lower()}-{chain}\": \"{contract_addr}\",")
        else:
            print(f"   ❌ No results found")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "="*70)
