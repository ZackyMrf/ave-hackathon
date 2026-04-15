import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_server import _pick_ave_token_from_chain_list

def test_picker():
    mock_tokens = [
        {
            "symbol": "UNI",
            "name": "Uniswap Fake",
            "address": "0xFAKE",
            "liquidity": 0.0,
            "market_cap": 1000000.0,
            "holder": 1
        },
        {
            "symbol": "UNI",
            "name": "Uniswap Real",
            "address": "0xREAL",
            "liquidity": 5000000.0,
            "market_cap": 1000000000.0,
            "holder": 500000
        },
        {
            "symbol": "UNII",
            "name": "Uniswap III",
            "address": "0xOTHER",
            "liquidity": 10000.0,
            "market_cap": 100000.0,
            "holder": 100
        }
    ]
    
    print("Testing picker with Mock Data containing multiple UNI symbols...")
    picked = _pick_ave_token_from_chain_list(mock_tokens, "UNI")
    
    if picked:
        print(f"Picked: {picked.get('name')} ({picked.get('address')})")
        print(f"Liquidity: {picked.get('liquidity')}")
        if picked.get('address') == "0xREAL":
            print("✅ SUCCESS: Correct token picked!")
        else:
            print("❌ FAILURE: Wrong token picked!")
    else:
        print("❌ FAILURE: No token picked!")

if __name__ == "__main__":
    test_picker()
