import os
import sys
import json
import time

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ave_monitor import AveAccumulationMonitor

def verify_token(symbol, chain, expected_ca=None):
    print(f"\n--- Verifying {symbol} on {chain} ---")
    monitor = AveAccumulationMonitor()
    
    # 1. Resolve address
    addr, search_data = monitor._resolve_token_address(symbol, chain)
    print(f"Resolved Address: {addr}")
    
    if search_data:
        tvl = search_data.get('tvl', search_data.get('liquidity', 0))
        holders = search_data.get('holders', search_data.get('holder', 0))
        print(f"TVL/Liquidity: ${float(tvl or 0):,.2f}")
        print(f"Holders: {int(float(holders or 0)):,}")
    
    if expected_ca:
        if addr.lower() == expected_ca.lower():
            print("✅ SUCCESS: Matches expected contract!")
        else:
            print(f"❌ FAILURE: Expected {expected_ca}, got {addr}")
            
    # 2. Analyze
    report = monitor.analyze_single_token(symbol, chain)
    if "error" in report:
        print(f"❌ Analysis Error: {report['error']}")
    else:
        print(f"✅ Analysis OK: {report['token']} ({report['name']})")
        print(f"Final TVL in report: ${report['tvl']:,.2f}")

if __name__ == "__main__":
    # Test cases
    # UNI on Ethereum
    verify_token("UNI", "ethereum", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984")
    
    # PEPE on Ethereum
    verify_token("PEPE", "ethereum", "0x6982508145454Ce325dDbE47a25d4ec3d2311933")
    
    # W (Wormhole) on Solana
    # Real W: 85VBFQXZotebC9yYj5L4YmN7qQJ25VvVceQ75X67L3gn
    verify_token("W", "solana", "85VBFQXZotebC9yYj5L4YmN7qQJ25VvVceQ75X67L3gn")
