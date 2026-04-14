import sys
import logging
from ave_api_service import get_ave_service

logging.basicConfig(level=logging.DEBUG)

def test_api():
    service = get_ave_service()
    
    print("\n--- Testing ave_api_service (bsc) ---")
    tokens_bsc = service.get_tokens_by_chain("bsc", limit=5)
    print(f"Tokens found using 'bsc': {len(tokens_bsc)}")

    print("\n--- Testing ave_api_service (solana) ---")
    tokens_solana = service.get_tokens_by_chain("solana", limit=5)
    print(f"Tokens found using 'solana': {len(tokens_solana)}")

if __name__ == "__main__":
    test_api()
