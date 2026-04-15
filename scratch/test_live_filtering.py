import os
import sys
import requests
import json

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_server import _pick_ave_token_from_chain_list, get_ave_service

def test_live_search(symbol, chain):
    print(f"\n--- Testing Live Filtering for {symbol} on {chain} ---")
    
    ave_service = get_ave_service()
    
    # Simulate the fallback mechanism: get top 100 trending tokens
    token_items = ave_service.get_tokens_by_chain(chain, limit=100)
    print(f"Fetched {len(token_items)} trending tokens from {chain}")
    
    # Test the picker
    picked = _pick_ave_token_from_chain_list(token_items, symbol)
    
    if picked:
        print(f"✅ Success: Picked {picked.get('token')} ({picked.get('ca')})")
        print(f"   Name: {picked.get('raw', {}).get('name') or 'N/A'}")
        print(f"   Liquidity: ${picked.get('liquidity'):,.2f}")
        print(f"   Market Cap: ${picked.get('market_cap'):,.2f}")
        print(f"   Holders: {picked.get('holder_count')}")
    else:
        # Check if any UNI tokens exist but were filtered out or not in top 100
        matches = [t for t in token_items if t.get('token') == symbol]
        if matches:
            print(f"⚠️ Found {len(matches)} tokens with symbol {symbol}, but none were picked.")
            for i, m in enumerate(matches, 1):
                print(f"   [{i}] CA: {m.get('ca')}, Liq: ${m.get('liquidity'):,.2f}, MC: ${m.get('market_cap'):,.2f}")
        else:
            print(f"❌ Error: No tokens with symbol {symbol} found in top 100 trending.")

if __name__ == "__main__":
    # Test 1: UNI on Ethereum
    test_live_search("UNI", "ethereum")
    
    # Test 2: PEPE on Ethereum
    test_live_search("PEPE", "ethereum")
    
    # Test 3: W on Solana
    # Note: Use 'solana' for chain
    test_live_search("W", "solana")
