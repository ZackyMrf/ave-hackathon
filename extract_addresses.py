#!/usr/bin/env python3
"""Test API responses to extract real contract addresses"""

import requests
import json

API_BASE = "http://localhost:8000"

tokens_to_test = [
    ("BONK", "solana"),
    ("WIF", "solana"),
    ("PEPE", "solana"),
    ("SHIB", "solana"),
    ("TRUMP", "solana"),
    ("DOGE", "solana"),
]

print("\n" + "="*70)
print("EXTRACTING CONTRACT ADDRESSES FROM API")
print("="*70)

for token, chain in tokens_to_test:
    try:
        url = f"{API_BASE}/api/analyze?token={token}&chain={chain}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if "error" not in data:
            # Extract all possible address fields
            address = data.get("address", "")
            ca = data.get("ca", "")
            
            # Look deeper in response for address
            token_obj = data.get("token", {})
            if isinstance(token_obj, dict):
                deep_address = token_obj.get("address", "")
            else:
                deep_address = ""
            
            print(f"\n{'='*70}")
            print(f"Token: {token.upper()} ({chain})")
            print(f"API Response Keys: {list(data.keys())}")
            print(f"\nAddress fields in response:")
            print(f'  "address": {address or "❌ EMPTY"}')
            print(f'  "ca": {ca or "❌ EMPTY"}')
            if deep_address:
                print(f'  "token.address": {deep_address}')
            
            # Check all string fields that might be address
            print(f"\nAll fields in response:")
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 20:  # Likely a contract address
                    print(f'  {key}: {value}')
        else:
            print(f"\n❌ {token} ({chain}): {data.get('error')}")
            
    except requests.exceptions.Timeout:
        print(f"\n⏱️ {token} ({chain}): Timeout")
    except Exception as e:
        print(f"\n❌ {token} ({chain}): {str(e)}")

print("\n" + "="*70)
print("Test complete!")
print("="*70)
