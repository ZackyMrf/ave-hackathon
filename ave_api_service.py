#!/usr/bin/env python3
"""
Ave API Integration Service
Connects to https://api.agacve.com/v3/tokens for live token monitoring
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

class AveApiService:
    """Service untuk mengakses Ave API"""
    
    BASE_URL = "https://api.agacve.com/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.cookie = os.getenv("AVE_COOKIE", "8df7699da1955497d3b08f7b724aa5691739944167617719326")
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Ave-Monitor/1.0"
        })
    
    def get_token_info(self, ca: str, chain: str = "bsc") -> Optional[Dict]:
        """
        Ambil info token dari Ave API
        
        Args:
            ca: Contract address token
            chain: Blockchain (bsc, solana, ethereum, etc)
        
        Returns:
            Token info dict atau None jika error
        """
        try:
            # Format URL sesuai Ave API
            url = f"{self.BASE_URL}/api/v3/tokens/{ca}-{chain}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok") or data.get("code") == "200":
                return self._parse_token_data(data.get("data", data), chain)
            
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Ave API Error: {e}")
            return None
    
    def get_tokens_by_chain(self, chain: str = "bsc", limit: int = 50) -> List[Dict]:
        """
        Ambil daftar token trending dari chain tertentu
        
        Args:
            chain: Blockchain name
            limit: Jumlah token (max 100)
        
        Returns:
            List of token info
        """
        try:
            url = f"{self.BASE_URL}/api/v3/tokens"
            params = {
                "chain": chain,
                "limit": min(limit, 100),
                "sort": "trending"
            }
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            tokens = data.get("data", [])
            if isinstance(tokens, list):
                return [self._parse_token_data(t, chain) for t in tokens]
            
            return []
        except requests.exceptions.RequestException as e:
            print(f"❌ Ave API Error (tokens): {e}")
            return []
    
    def get_whale_movements(self, ca: str, chain: str = "bsc") -> List[Dict]:
        """
        Ambil whale transaction movements
        
        Args:
            ca: Contract address
            chain: Blockchain
        
        Returns:
            List of whale transactions
        """
        try:
            url = f"{self.BASE_URL}/api/v3/tokens/{ca}-{chain}/whales"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return data.get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Whale API Error: {e}")
            return []
    
    def get_holder_distribution(self, ca: str, chain: str = "bsc") -> Dict:
        """
        Ambil distribusi holder token
        
        Args:
            ca: Contract address
            chain: Blockchain
        
        Returns:
            Holder distribution data
        """
        try:
            url = f"{self.BASE_URL}/api/v3/tokens/{ca}-{chain}/holders"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return data.get("data", {})
        except requests.exceptions.RequestException as e:
            print(f"❌ Holder API Error: {e}")
            return {}
    
    def _parse_token_data(self, raw_data: Dict, chain: str) -> Dict:
        """Parse raw Ave API response into standardized format"""
        return {
            "token": raw_data.get("symbol", raw_data.get("name", "UNKNOWN")),
            "ca": raw_data.get("address", raw_data.get("ca", "")),
            "chain": chain,
            "price": float(raw_data.get("price", 0)),
            "price_change_24h": float(raw_data.get("price_change_24h", 0)),
            "price_change_1h": float(raw_data.get("price_change_1h", 0)),
            "price_change_7d": float(raw_data.get("price_change_7d", 0)),
            "volume_24h": float(raw_data.get("volume_24h", 0)),
            "volume_24h_change": float(raw_data.get("volume_24h_change", 0)),
            "market_cap": float(raw_data.get("market_cap", 0)),
            "burned_percentage": float(raw_data.get("burned", 0)),
            "holder_count": int(raw_data.get("holder", 0)),
            "holder_change_24h": float(raw_data.get("holder_change", 0)),
            "total_supply": float(raw_data.get("total_supply", 0)),
            "liquidity": float(raw_data.get("liquidity", 0)),
            "liquidity_lock_percentage": float(raw_data.get("liquidity_lock", 0)),
            "risk_level": raw_data.get("risk", "medium"),
            "last_updated": datetime.now().isoformat(),
            "raw": raw_data
        }


# Singleton instance
_ave_service: Optional[AveApiService] = None

def get_ave_service() -> AveApiService:
    """Get atau create Ave API service instance"""
    global _ave_service
    if _ave_service is None:
        _ave_service = AveApiService()
    return _ave_service
