#!/usr/bin/env python3
"""
Ave Accumulation Monitor
Detect pre-movement accumulation signals in crypto tokens
"""

import os
import sys
import json
import math
import time
import requests
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

# Get API key from environment variable
# Users must set: export AVE_API_KEY="your-api-key"
DEFAULT_API_KEY = os.getenv("AVE_API_KEY", "")
BASE_URL = "https://prod.ave-api.com"  # Original Ave API endpoint

# Popular token contract addresses for fallback (map token_symbol-chain to contract_address)
# Used when API doesn't return real addresses - ONLY verified addresses here!
TOKEN_ADDRESS_MAP = {
    # Solana - Verified contract addresses only
    "jup-solana": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "bonk-solana": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    # TODO: Add other tokens when verified
}

# Alert emojis
ALERT_LEVELS = {
    "green": "🟢",
    "yellow": "🟡",
    "orange": "🟠",
    "red": "🔴"
}


def _looks_like_address(value: Optional[str]) -> bool:
    if not value:
        return False
    v = str(value).strip()
    return len(v) >= 20 and " " not in v


def _normalize_token_for_chain(token: str, chain: str) -> str:
    """Accept both '<token>' and '<token>-<chain>' inputs."""
    token_raw = str(token or "").strip()
    chain_norm = str(chain or "").strip().lower()
    if not token_raw:
        return ""
    if "-" in token_raw and chain_norm:
        base, suffix = token_raw.rsplit("-", 1)
        if base.strip() and suffix.strip().lower() == chain_norm:
            return base.strip()
    return token_raw

@dataclass
class TokenData:
    symbol: str
    name: str
    address: str
    chain: str
    price: float
    price_change_24h: float
    volume_24h: float
    tvl: float
    holders: int
    market_cap: float
    risk_score: int
    
@dataclass
class WhaleData:
    address: str
    balance: float
    balance_ratio: float
    balance_change_24h: float
    is_new: bool

@dataclass
class AccumulationScore:
    total: int
    volume_divergence: int
    volume_momentum: int
    tvl_stability: int
    holder_distribution: int
    tvl_confidence: int
    whale_score: int
    anomaly_score: int
    pattern_match: int
    risk_adjusted: int
    confidence: int
    alert_level: str
    market_phase: str

class AveAccumulationMonitor:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("AVE_API_KEY", DEFAULT_API_KEY)
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        })
        
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request with error handling"""
        url = f"{BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            # Ave API wraps response in {status, msg, data}
            if isinstance(result, dict) and "data" in result:
                return result["data"]
            return result
        except requests.exceptions.RequestException as e:
            print(f"❌ API Error: {e}")
            return {}

    def _normalize_token_items(self, payload: object) -> List[Dict]:
        """Normalize /v2/tokens response shapes into list[dict]."""
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            for key in ("items", "list", "tokens", "rows", "results", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
        return []

    def _pick_best_token_candidate(self, items: List[Dict], token: str) -> Optional[Dict]:
        """Pick best token candidate by exact symbol/name/address match first."""
        if not items:
            return None

        query = str(token or "").strip()
        query_lower = query.lower()
        query_upper = query.upper()
        query_is_address = _looks_like_address(query)

        ranked: List[Tuple[int, float, Dict]] = []
        for item in items:
            symbol = str(item.get("symbol", "")).strip()
            name = str(item.get("name", "")).strip()
            token_addr = str(item.get("token", "")).strip()

            symbol_lower = symbol.lower()
            name_lower = name.lower()
            token_lower = token_addr.lower()

            score = 0
            matched = False

            if query_is_address:
                if token_lower == query_lower:
                    score += 5000
                    matched = True
            else:
                if symbol == query_upper:
                    score += 3000
                    matched = True
                elif symbol_lower.startswith(query_lower):
                    score += 1000
                    matched = True
                elif query_lower in symbol_lower:
                    score += 600
                    matched = True

                if name_lower == query_lower:
                    score += 1500
                    matched = True
                elif query_lower in name_lower and len(query_lower) >= 3:
                    score += 400
                    matched = True

            market_cap = 0.0
            try:
                market_cap = float(item.get("market_cap", 0) or 0)
            except (TypeError, ValueError):
                market_cap = 0.0

            if matched:
                ranked.append((score, market_cap, item))

        if not ranked:
            return None

        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return ranked[0][2]

    def _dedupe_candidate_items(self, items: List[Dict], limit: int) -> List[Dict]:
        """Normalize and dedupe candidate items by symbol/address, keeping stronger market caps."""
        best_by_symbol: Dict[str, Dict] = {}
        best_by_address: Dict[str, Dict] = {}

        def pick_float(src: Dict, keys: Tuple[str, ...], default: float = 0.0) -> float:
            for key in keys:
                if key not in src:
                    continue
                try:
                    return float(src.get(key) or 0)
                except (TypeError, ValueError):
                    continue
            return default

        def pick_int(src: Dict, keys: Tuple[str, ...], default: int = 0) -> int:
            for key in keys:
                if key not in src:
                    continue
                try:
                    return int(float(src.get(key) or 0))
                except (TypeError, ValueError):
                    continue
            return default

        for item in items:
            if not isinstance(item, dict):
                continue

            symbol = str(item.get("symbol", "")).strip().upper()
            name = str(item.get("name", "")).strip()
            address = str(item.get("token", item.get("address", ""))).strip()

            if not symbol and not _looks_like_address(address):
                continue

            try:
                market_cap = float(item.get("market_cap", 0) or 0)
            except (TypeError, ValueError):
                market_cap = 0.0

            price = pick_float(item, ("current_price_usd", "price", "price_usd"), 0.0)
            price_change_24h = pick_float(item, ("price_change_24h", "change_24h", "price_change"), 0.0)
            volume_24h = pick_float(item, ("tx_volume_u_24h", "volume_24h", "volume"), 0.0)
            tvl = pick_float(item, ("tvl",), 0.0)
            holders = pick_int(item, ("holders",), 0)
            risk_score = pick_int(item, ("riskScore", "risk_score"), 50)

            tags_flat = ""
            for key in ("tags", "categories", "sectors"):
                raw = item.get(key)
                if isinstance(raw, list):
                    tags_flat += " " + " ".join(str(x) for x in raw)
                elif isinstance(raw, str):
                    tags_flat += f" {raw}"

            candidate = {
                "symbol": symbol,
                "name": name,
                "address": address,
                "market_cap": market_cap,
                "price": price,
                "price_change_24h": price_change_24h,
                "volume_24h": volume_24h,
                "tvl": tvl,
                "holders": holders,
                "risk_score": risk_score,
                "search_text": f"{symbol.lower()} {name.lower()} {tags_flat.lower()}".strip(),
            }

            if symbol:
                prev = best_by_symbol.get(symbol)
                if not prev or market_cap > float(prev.get("market_cap", 0) or 0):
                    best_by_symbol[symbol] = candidate

            if _looks_like_address(address):
                addr_key = address.lower()
                prev = best_by_address.get(addr_key)
                if not prev or market_cap > float(prev.get("market_cap", 0) or 0):
                    best_by_address[addr_key] = candidate

        out: List[Dict] = list(best_by_symbol.values())
        for addr_key, cand in best_by_address.items():
            if addr_key not in {str(x.get("address", "")).strip().lower() for x in out}:
                out.append(cand)

        out.sort(key=lambda x: float(x.get("market_cap", 0) or 0), reverse=True)
        return out[: max(10, min(limit, 160))]

    def _fetch_chain_token_candidates(self, chain: str, limit: int = 80) -> List[Dict]:
        """Fetch chain-wide candidate pool (network-first)."""
        page_size = max(30, min(limit, 100))

        payload = self._make_request(
            "/v2/tokens/trending",
            {
                "chain": chain,
                "page_size": page_size,
            },
        )
        items = self._normalize_token_items(payload)
        if items:
            return self._dedupe_candidate_items(items, limit)

        # Fallback only when trending endpoint is unavailable.
        fallback_keywords = [
            "sol", "eth", "btc", "usdc", "jup", "ray", "bonk", "wif", "pepe", "uni", "aave", "rndr"
        ]
        collected: List[Dict] = []
        for kw in fallback_keywords:
            payload = self._make_request(
                "/v2/tokens",
                {
                    "keyword": kw,
                    "chain": chain,
                    "limit": 20,
                },
            )
            items = self._normalize_token_items(payload)
            if items:
                collected.extend(items)
            time.sleep(0.08)

        return self._dedupe_candidate_items(collected, limit)

    def _filter_candidates_by_category(self, candidates: List[Dict], category: str) -> List[Dict]:
        """Apply soft category filtering on a chain-wide candidate list."""
        cat = str(category or "all").strip().lower()
        if cat in {"", "all", "any", "network", "network-wide", "chain", "*"}:
            return candidates

        category_keywords = {
            "trending": ["trending", "hot", "viral"],
            "meme": ["meme", "doge", "shib", "pepe", "bonk", "wif", "floki", "mog", "cat", "pump"],
            "defi": ["defi", "dex", "lending", "yield", "uni", "aave", "mkr", "crv", "ldo", "pendle"],
            "gaming": ["game", "gaming", "metaverse", "nft", "imx", "gala", "sand", "mana", "axs"],
            "ai": ["ai", "agent", "fet", "agix", "ocean", "rndr", "tao", "nmr", "arkm"],
            "new": ["new", "launch", "fresh", "pump"],
        }

        keywords = category_keywords.get(cat)
        if not keywords:
            return candidates

        filtered = [
            c for c in candidates
            if any(k in str(c.get("search_text", "")) for k in keywords)
        ]

        # Keep scanner productive even if metadata is sparse.
        return filtered if filtered else candidates

    def _fetch_sweep_candidates(self, category: str, chain: str, limit: int = 40) -> List[Dict]:
        """Fetch sweep candidates chain-first, then apply optional category filter."""
        pool_limit = max(24, min(limit * 3, 160))
        chain_candidates = self._fetch_chain_token_candidates(chain, pool_limit)
        if not chain_candidates:
            return []

        filtered = self._filter_candidates_by_category(chain_candidates, category)
        return filtered[: max(10, min(limit, 100))]

    def _trend_strength_score(self, candidate: Dict) -> float:
        """Compute lightweight trend strength from market activity fields."""
        volume = max(0.0, float(candidate.get("volume_24h", 0) or 0))
        tvl = max(0.0, float(candidate.get("tvl", 0) or 0))
        market_cap = max(0.0, float(candidate.get("market_cap", 0) or 0))
        price_change = float(candidate.get("price_change_24h", 0) or 0)
        risk_score = float(candidate.get("risk_score", 50) or 50)

        # Emphasize turnover/liquidity first, then directional momentum and risk penalty.
        raw = (
            math.log10(volume + 1.0) * 34.0
            + math.log10(tvl + 1.0) * 24.0
            + math.log10(market_cap + 1.0) * 14.0
            + max(-20.0, min(20.0, price_change)) * 0.9
            - max(0.0, risk_score - 70.0) * 0.6
        )
        return raw

    def _rank_trend_candidates(self, candidates: List[Dict], chain: str, category: str, top_n: int) -> List[Dict]:
        """Rank already-filtered candidates and return compact trend rows."""
        if not candidates:
            return []

        scored: List[Tuple[float, Dict]] = []
        for cand in candidates:
            scored.append((self._trend_strength_score(cand), cand))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[: max(1, top_n)]

        min_raw = min(x[0] for x in best)
        max_raw = max(x[0] for x in best)

        rows: List[Dict] = []
        for raw_score, cand in best:
            if max_raw == min_raw:
                trend_score = 100.0
            else:
                trend_score = ((raw_score - min_raw) / (max_raw - min_raw)) * 100.0

            token = str(cand.get("symbol") or cand.get("name") or "").strip() or str(cand.get("address", ""))[:10]
            rows.append(
                {
                    "token": token,
                    "address": str(cand.get("address", "")),
                    "chain": chain,
                    "category": category,
                    "trend_score": round(float(trend_score), 2),
                    "price": float(cand.get("price", 0) or 0),
                    "price_change_24h": float(cand.get("price_change_24h", 0) or 0),
                    "volume_24h": float(cand.get("volume_24h", 0) or 0),
                    "tvl": float(cand.get("tvl", 0) or 0),
                    "market_cap": float(cand.get("market_cap", 0) or 0),
                    "holders": int(cand.get("holders", 0) or 0),
                    "risk_score": int(cand.get("risk_score", 50) or 50),
                }
            )
        return rows

    def get_category_chain_trends(self, category: str, chain: str, top_n: int = 5) -> List[Dict]:
        """Get lightweight trend ranking for one category on one chain."""
        chain_norm = "eth" if str(chain).strip().lower() == "ethereum" else str(chain).strip().lower()
        category_norm = str(category or "all").strip().lower()
        pool_limit = max(24, min(top_n * 8, 160))

        chain_candidates = self._fetch_chain_token_candidates(chain_norm, pool_limit)
        filtered = self._filter_candidates_by_category(chain_candidates, category_norm)
        return self._rank_trend_candidates(filtered, chain_norm, category_norm, top_n)

    def get_category_network_trend_matrix(self, categories: List[str], chains: List[str], top_n: int = 5) -> Dict[str, Dict[str, List[Dict]]]:
        """Get trend matrix across categories x chains with shared candidate pools per chain."""
        matrix: Dict[str, Dict[str, List[Dict]]] = {}
        top_n = max(1, min(int(top_n), 20))

        category_list = [str(c).strip().lower() for c in categories if str(c).strip()]
        chain_list = [str(c).strip().lower() for c in chains if str(c).strip()]

        for chain in chain_list:
            chain_candidates = self._fetch_chain_token_candidates(chain, max(24, min(top_n * 10, 180)))
            matrix[chain] = {}
            for category in category_list:
                filtered = self._filter_candidates_by_category(chain_candidates, category)
                matrix[chain][category] = self._rank_trend_candidates(filtered, chain, category, top_n)

        return matrix
    
    def _search_token(self, token: str, chain: str) -> Optional[Dict]:
        """Search for token by keyword to get address"""
        params = {"keyword": token, "chain": chain, "limit": 20}
        results = self._make_request("/v2/tokens", params)
        items = self._normalize_token_items(results)

        item = self._pick_best_token_candidate(items, token)
        if item:
            # Extract contract address and cache it
            contract_addr = item.get("token")
            lookup_key = f"{token.lower()}-{chain.lower()}"
            # Cache to TOKEN_ADDRESS_MAP for future use
            if _looks_like_address(contract_addr) and lookup_key not in TOKEN_ADDRESS_MAP:
                TOKEN_ADDRESS_MAP[lookup_key] = str(contract_addr)
                print(f"✅ Cached: {lookup_key} → {contract_addr}")
            return item
        return None

    def _resolve_token_address(self, token_input: str, chain: str) -> Tuple[str, Optional[Dict]]:
        """Resolve a contract address for token-id endpoints; never return symbol-only values."""
        lookup_key = f"{token_input.lower()}-{chain.lower()}"

        if _looks_like_address(token_input):
            return token_input, None

        if lookup_key in TOKEN_ADDRESS_MAP and _looks_like_address(TOKEN_ADDRESS_MAP[lookup_key]):
            return TOKEN_ADDRESS_MAP[lookup_key], None

        search_data = self._search_token(token_input, chain)
        if isinstance(search_data, dict):
            candidate = str(search_data.get("token") or search_data.get("address") or "").strip()
            if _looks_like_address(candidate):
                return candidate, search_data

        return "", search_data
    
    def get_token_data(self, token: str, chain: str) -> Optional[TokenData]:
        """Fetch token data from Ave API"""
        token_input = _normalize_token_for_chain(token, chain)

        lookup_key = f"{token_input.lower()}-{chain.lower()}"
        token_address, search_data = self._resolve_token_address(token_input, chain)

        # If we cannot resolve a contract address, avoid invalid /v2/tokens/<symbol>-<chain> calls.
        if not token_address:
            if not isinstance(search_data, dict):
                return None

            return TokenData(
                symbol=str(search_data.get("symbol") or token_input).upper(),
                name=str(search_data.get("name") or search_data.get("symbol") or token_input).strip(),
                address=str(search_data.get("token") or search_data.get("address") or token_input),
                chain=chain,
                price=float(search_data.get("current_price_usd") or search_data.get("price") or 0),
                price_change_24h=float(search_data.get("price_change_24h") or 0),
                volume_24h=float(search_data.get("tx_volume_u_24h") or search_data.get("volume_24h") or 0),
                tvl=float(search_data.get("tvl") or 0),
                holders=int(search_data.get("holders") or 0),
                market_cap=float(search_data.get("market_cap") or 0),
                risk_score=int(search_data.get("riskScore") or search_data.get("risk_score") or 50),
            )

        token_id = f"{token_address}-{chain}"
        data = self._make_request(f"/v2/tokens/{token_id}")

        # Handle list response from API
        if isinstance(data, list):
            if len(data) == 0:
                return None
            data = data[0]
        
        if not data:
            return None
        
        # Extract address from multiple possible locations in response
        extracted_address = (
            search_data.get("token") if isinstance(search_data, dict) else None or
            data.get("address") or  # Direct address field
            data.get("token", {}).get("address") or  # Nested in token object
            data.get("ca") or  # Alternative field name
            TOKEN_ADDRESS_MAP.get(lookup_key) or  # Fallback to known token mapping
            token_address or  # Use what we found during search
            token_input  # Final fallback to token symbol
        )
        
        return TokenData(
            symbol=data["token"].get("symbol", token_input.upper()) if isinstance(data.get("token"), dict) else token_input.upper(),
            name=(
                str(data.get("name") or "").strip()
                or str(data.get("token", {}).get("name") or "").strip()
                or str(search_data.get("name") if isinstance(search_data, dict) else "").strip()
                or str(token_input).strip()
            ),
            address=extracted_address,
            chain=chain,
            price=float(data.get("current_price_usd") or data.get("token", {}).get("current_price_usd") or 0),
            price_change_24h=float(data.get("price_change_24h") or data.get("token", {}).get("price_change_24h") or 0),
            volume_24h=float(data.get("tx_volume_u_24h") or data.get("token", {}).get("tx_volume_u_24h") or 0),
            tvl=float(data.get("tvl") or data.get("token", {}).get("tvl") or 0),
            holders=int(data.get("holders") or data.get("token", {}).get("holders") or 0),
            market_cap=float(data.get("market_cap") or data.get("token", {}).get("market_cap") or 0),
            risk_score=int(data.get("riskScore") or data.get("token", {}).get("riskScore") or 50)
        )
    
    def get_whale_data(self, token: str, chain: str) -> List[WhaleData]:
        """Fetch top 25 holders from Ave API"""
        token_input = _normalize_token_for_chain(token, chain)
        token_address, _ = self._resolve_token_address(token_input, chain)
        if not token_address:
            return []

        token_id = f"{token_address}-{chain}"
        data = self._make_request(f"/v2/tokens/top100/{token_id}")
        
        whales = []
        # API returns list directly or dict with holders key
        if isinstance(data, list):
            holders = data[:25]  # Top 25
        elif isinstance(data, dict):
            holders = data.get("data", [])[:25]
        else:
            holders = []
        
        for holder in holders:
            whales.append(WhaleData(
                address=holder.get("holder", ""),
                balance=float(holder.get("balance", 0)),
                balance_ratio=float(holder.get("balance_ratio", 0)) * 100,
                balance_change_24h=float(holder.get("balance_change_24h", 0)),
                is_new=holder.get("is_new", False)
            ))
            
        return whales
    
    def get_price_history(self, token: str, chain: str, days: int = 30) -> List[Dict]:
        """Fetch historical price/volume data from klines"""
        token_input = _normalize_token_for_chain(token, chain)
        token_address, _ = self._resolve_token_address(token_input, chain)
        if not token_address:
            return []

        token_id = f"{token_address}-{chain}"
        
        # Use klines endpoint - interval 1440 = 1 day
        params = {"interval": 1440, "limit": days}
        data = self._make_request(f"/v2/klines/token/{token_id}", params)
        
        if not data:
            return []
        
        # Convert kline points to history format
        points = data.get("points", [])
        history = []
        for point in points:
            history.append({
                "price": float(point.get("close", 0)),
                "volume": float(point.get("volume", 0)),
                "time": point.get("time", 0)
            })
        return history
    
    def detect_market_phase(self, price_change_24h: float) -> str:
        """Detect market phase based on price action"""
        if price_change_24h > 5:
            return "bull"
        elif price_change_24h < -5:
            return "bear"
        return "consolidation"
    
    def get_dynamic_weights(self, phase: str) -> Dict[str, float]:
        """Get signal weights based on market phase"""
        weights = {
            "bull": {
                "volume_divergence": 0.35,
                "volume_momentum": 0.25,
                "tvl_stability": 0.15,
                "holder_distribution": 0.10,
                "tvl_confidence": 0.10
            },
            "consolidation": {
                "volume_divergence": 0.25,
                "volume_momentum": 0.20,
                "tvl_stability": 0.30,
                "holder_distribution": 0.20,
                "tvl_confidence": 0.10
            },
            "bear": {
                "volume_divergence": 0.20,
                "volume_momentum": 0.15,
                "tvl_stability": 0.20,
                "holder_distribution": 0.30,
                "tvl_confidence": 0.10
            }
        }
        return weights.get(phase, weights["consolidation"])
    
    def calculate_volume_divergence(self, token: TokenData, history: List[Dict]) -> int:
        """
        Signal 1: Volume/Price Divergence (0-30 pts)
        High volume but flat price = smart money absorbing sells
        """
        if not history or len(history) < 7:
            return 15  # Neutral
            
        # Calculate average volume (last 30 days)
        volumes = [h.get("volume", 0) for h in history]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        
        if avg_volume == 0:
            return 15
            
        # Volume ratio
        volume_ratio = token.volume_24h / avg_volume
        
        # Price change
        price_change = abs(token.price_change_24h)
        
        # Score: High volume + low price movement = high divergence
        if volume_ratio > 4 and price_change < 3:
            return 30  # Strong divergence
        elif volume_ratio > 3 and price_change < 5:
            return 26
        elif volume_ratio > 2.5 and price_change < 5:
            return 24
        elif volume_ratio > 2 and price_change < 8:
            return 20
        elif volume_ratio > 1.5:
            return 15
        elif volume_ratio > 1:
            return 10
        return 5
    
    def calculate_volume_momentum(self, token: TokenData, history: List[Dict]) -> int:
        """
        Signal 2: Volume Momentum Velocity (0-25 pts)
        Accelerating volume = increasing buying pressure
        """
        if not history or len(history) < 2:
            return 12  # Neutral
            
        # Get recent volumes
        recent = history[-7:]  # Last 7 days
        if len(recent) < 2:
            return 12
            
        volumes = [h.get("volume", 0) for h in recent]
        
        # Check if volume is accelerating
        if len(volumes) >= 3:
            # Compare recent 3 days vs previous
            recent_avg = sum(volumes[-3:]) / 3
            previous_avg = sum(volumes[-6:-3]) / 3 if len(volumes) >= 6 else volumes[0]
            
            if previous_avg > 0:
                momentum = recent_avg / previous_avg
                
                if momentum > 3:
                    return 25  # Extreme acceleration
                elif momentum > 2.5:
                    return 22
                elif momentum > 2:
                    return 19
                elif momentum > 1.5:
                    return 15
                elif momentum > 1.2:
                    return 12
                elif momentum > 1:
                    return 8
        
        return 5
    
    def calculate_tvl_stability(self, token: TokenData, history: List[Dict]) -> int:
        """
        Signal 3: TVL Stability (0-20 pts)
        LPs holding positions = confidence in continued demand
        """
        if token.tvl <= 0:
            return 5
            
        # Deep liquidity score
        if token.tvl > 10000000:  # $10M+
            tvl_score = 20
        elif token.tvl > 5000000:  # $5M+
            tvl_score = 18
        elif token.tvl > 2000000:  # $2M+
            tvl_score = 16
        elif token.tvl > 1000000:  # $1M+
            tvl_score = 14
        elif token.tvl > 500000:
            tvl_score = 12
        elif token.tvl > 200000:
            tvl_score = 10
        else:
            tvl_score = 5
            
        # Check TVL trend if history available
        if history and len(history) >= 7:
            recent_tvl = history[-1].get("tvl", token.tvl)
            old_tvl = history[-7].get("tvl", token.tvl)
            
            if old_tvl > 0:
                tvl_change = (recent_tvl - old_tvl) / old_tvl * 100
                
                # TVL growing or stable = good
                if tvl_change > 10:
                    tvl_score = min(20, tvl_score + 2)
                elif tvl_change < -10:
                    tvl_score = max(0, tvl_score - 5)
                    
        return tvl_score
    
    def calculate_holder_distribution(self, token: TokenData, history: List[Dict]) -> int:
        """
        Signal 4: Holder Distribution (0-15 pts)
        Growing holders = whales distributing to community
        """
        if not history or len(history) < 2:
            return 7  # Neutral
            
        # Calculate holder growth
        recent_holders = history[-1].get("holders", token.holders)
        old_holders = history[-7].get("holders", token.holders) if len(history) >= 7 else history[0].get("holders", token.holders)
        
        if old_holders > 0:
            growth = (recent_holders - old_holders) / old_holders * 100
            
            if growth > 15:
                return 15  # Excellent growth
            elif growth > 10:
                return 13
            elif growth > 8:
                return 12
            elif growth > 5:
                return 10
            elif growth > 3:
                return 8
            elif growth > 0:
                return 6
            elif growth > -3:
                return 4
            else:
                return 2  # Declining holders
                
        return 7
    
    def calculate_tvl_confidence(self, token: TokenData) -> int:
        """
        Signal 5: TVL Confidence (0-10 pts)
        Absolute TVL depth for large moves
        """
        if token.tvl > 50000000:  # $50M+
            return 10
        elif token.tvl > 20000000:  # $20M+
            return 9
        elif token.tvl > 10000000:  # $10M+
            return 8
        elif token.tvl > 5000000:
            return 7
        elif token.tvl > 2000000:
            return 6
        elif token.tvl > 1000000:
            return 5
        elif token.tvl > 500000:
            return 4
        return 2
    
    def calculate_whale_score(self, whales: List[WhaleData]) -> Tuple[int, str]:
        """
        Advanced Feature: Whale Accumulation Detector
        Returns score and description
        """
        score = 0
        descriptions = []
        
        new_whales = 0
        accumulating_whales = 0
        distributing_whales = 0
        
        for whale in whales:
            # New whale entry
            if whale.is_new and whale.balance_ratio >= 2:
                new_whales += 1
                score += 20
                descriptions.append(f"🐋 New whale: {whale.address[:6]}...{whale.address[-4:]} ({whale.balance_ratio:.1f}%)")
            
            # Whale accumulating (5%+ supply and growing)
            elif whale.balance_ratio >= 5 and whale.balance_change_24h > 10:
                accumulating_whales += 1
                score += 15
                descriptions.append(f"📈 Whale accumulating: {whale.address[:6]}... ({whale.balance_change_24h:+.1f}%)")
            
            # Whale distributing
            elif whale.balance_ratio >= 3 and whale.balance_change_24h < -5:
                distributing_whales += 1
                score -= 10
                descriptions.append(f"⚠️ Whale selling: {whale.address[:6]}... ({whale.balance_change_24h:+.1f}%)")
        
        # Cap whale score at 40
        score = min(40, max(0, score))
        
        desc = f"{new_whales} new, {accumulating_whales} accumulating, {distributing_whales} distributing"
        if descriptions:
            desc += "\n   " + "\n   ".join(descriptions[:3])  # Show top 3
            
        return score, desc
    
    def calculate_anomaly_score(self, token: TokenData, history: List[Dict]) -> Tuple[int, str]:
        """
        Advanced Feature: Anomaly Detection (Z-Score Based)
        """
        if not history or len(history) < 7:
            return 0, "No historical data"
            
        volumes = [h.get("volume", 0) for h in history if h.get("volume", 0) > 0]
        
        if len(volumes) < 7:
            return 0, "Insufficient volume data"
            
        # Calculate Z-score
        avg_vol = sum(volumes) / len(volumes)
        variance = sum((v - avg_vol) ** 2 for v in volumes) / len(volumes)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0, "No volume variance"
            
        z_score = (token.volume_24h - avg_vol) / std_dev
        
        # Price compression check
        recent_prices = [h.get("price", token.price) for h in history[-7:]]
        if len(recent_prices) >= 2:
            price_range = max(recent_prices) - min(recent_prices)
            price_compression = (price_range / max(recent_prices)) * 100 if max(recent_prices) > 0 else 0
        else:
            price_compression = 0
        
        score = 0
        desc_parts = []
        
        # Volume anomaly
        if z_score > 3.0:
            score += 12
            desc_parts.append(f"🔥 Extreme volume anomaly (Z={z_score:.1f})")
        elif z_score > 2.5:
            score += 10
            desc_parts.append(f"📊 High volume anomaly (Z={z_score:.1f})")
        elif z_score > 2.0:
            score += 8
            desc_parts.append(f"📈 Unusual volume (Z={z_score:.1f})")
        
        # Price compression with volume
        if price_compression < 5 and z_score > 1.5:
            score += 15
            desc_parts.append(f"🎯 Price compression ({price_compression:.1f}%) + volume = classic accumulation")
        
        return score, " | ".join(desc_parts) if desc_parts else "Normal activity"
    
    def match_historical_pattern(self, token: TokenData, history: List[Dict], 
                                  whales: List[WhaleData]) -> Tuple[int, str]:
        """
        Advanced Feature: Historical Pattern Matching
        Compare against known pre-pump signatures
        """
        if not history or len(history) < 7:
            return 0, "Insufficient data"
            
        # Calculate metrics
        volumes = [h.get("volume", 0) for h in history[-30:]]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        volume_ratio = token.volume_24h / avg_volume if avg_volume > 0 else 1
        
        price_change = abs(token.price_change_24h)
        
        # Holder growth
        recent_holders = token.holders
        old_holders = history[0].get("holders", token.holders)
        holder_growth = ((recent_holders - old_holders) / old_holders * 100) if old_holders > 0 else 0
        
        # Whale activity
        new_whales = sum(1 for w in whales if w.is_new and w.balance_ratio >= 2)
        
        # Pattern A: "Silent Bludge" (3-7 days before 50x)
        pattern_a_matches = 0
        pattern_a_checks = [
            (2.5 <= volume_ratio <= 4.5, "Volume 2.5-4.5x"),
            (2 <= price_change <= 8, "Price compression 2-8%"),
            (holder_growth >= 5, "Holder growth 5%+"),
            (new_whales >= 1, "New whale entry"),
            (token.tvl > 1000000, "TVL > $1M")
        ]
        pattern_a_matches = sum(1 for match, _ in pattern_a_checks if match)
        pattern_a_pct = (pattern_a_matches / len(pattern_a_checks)) * 100
        
        # Pattern B: "Slow Burn" (7-14 days before 20x)
        pattern_b_checks = [
            (1.5 <= volume_ratio <= 2.5, "Volume 1.5-2.5x"),
            (price_change < 5, "Price steady"),
            (holder_growth >= 3, "Holder linear growth"),
            (token.tvl > 500000, "TVL climbing"),
            (new_whales == 0, "Low whale activity (organic)")
        ]
        pattern_b_matches = sum(1 for match, _ in pattern_b_checks if match)
        pattern_b_pct = (pattern_b_matches / len(pattern_b_checks)) * 100
        
        # Pattern C: "Pump &..." (24-48 hours before 100x+)
        pattern_c_checks = [
            (volume_ratio > 4, "Volume spiking 4x+"),
            (price_change < 3, "Tight price compression"),
            (new_whales >= 2, "Multiple whales"),
            (token.tvl > 2000000, "Deep liquidity")
        ]
        pattern_c_matches = sum(1 for match, _ in pattern_c_checks if match)
        pattern_c_pct = (pattern_c_matches / len(pattern_c_checks)) * 100
        
        # Find best match
        patterns = [
            ("Silent Bludge", pattern_a_pct, "3-7 days before 50x"),
            ("Slow Burn", pattern_b_pct, "7-14 days before 20x"),
            ("Pump &...", pattern_c_pct, "24-48 hours before 100x+")
        ]
        
        best_match = max(patterns, key=lambda x: x[1])
        
        if best_match[1] >= 75:
            return 8, f"📚 {best_match[1]:.0f}% match '{best_match[0]}' ({best_match[2]})"
        elif best_match[1] >= 50:
            return 4, f"📖 {best_match[1]:.0f}% partial match '{best_match[0]}'"
        
        return 0, f"No significant pattern match ({best_match[1]:.0f}% best)"
    
    def calculate_accumulation_score(self, token: TokenData, history: List[Dict], 
                                     whales: List[WhaleData]) -> AccumulationScore:
        """Calculate full accumulation score with all signals"""
        
        # Detect market phase
        phase = self.detect_market_phase(token.price_change_24h)
        weights = self.get_dynamic_weights(phase)
        
        # Calculate base signals
        vol_div = self.calculate_volume_divergence(token, history)
        vol_mom = self.calculate_volume_momentum(token, history)
        tvl_stab = self.calculate_tvl_stability(token, history)
        holder_dist = self.calculate_holder_distribution(token, history)
        tvl_conf = self.calculate_tvl_confidence(token)
        
        # Calculate advanced signals
        whale_score, _ = self.calculate_whale_score(whales)
        anomaly_score, _ = self.calculate_anomaly_score(token, history)
        pattern_score, _ = self.match_historical_pattern(token, history, whales)
        
        # Apply dynamic weights to base signals
        weighted_base = (
            vol_div * weights["volume_divergence"] +
            vol_mom * weights["volume_momentum"] +
            tvl_stab * weights["tvl_stability"] +
            holder_dist * weights["holder_distribution"] +
            tvl_conf * weights["tvl_confidence"]
        )
        
        # Add advanced signals
        total = int(weighted_base + whale_score + anomaly_score + pattern_score)
        total = min(100, total)  # Cap at 100
        
        # Risk adjustment
        risk_multiplier = self.get_risk_multiplier(token.risk_score)
        risk_adjusted = int(total * risk_multiplier)
        
        # Confidence calculation
        confidence = int(risk_adjusted * 0.95)  # Slight uncertainty buffer
        
        # Alert level
        alert_level = self.get_alert_level(risk_adjusted)
        
        return AccumulationScore(
            total=total,
            volume_divergence=vol_div,
            volume_momentum=vol_mom,
            tvl_stability=tvl_stab,
            holder_distribution=holder_dist,
            tvl_confidence=tvl_conf,
            whale_score=whale_score,
            anomaly_score=anomaly_score,
            pattern_match=pattern_score,
            risk_adjusted=risk_adjusted,
            confidence=confidence,
            alert_level=alert_level,
            market_phase=phase
        )
    
    def get_risk_multiplier(self, risk_score: int) -> float:
        """Get risk adjustment multiplier"""
        if risk_score <= 30:
            return 0.92
        elif risk_score <= 60:
            return 0.84
        elif risk_score <= 85:
            return 0.70
        return 0.60
    
    def get_alert_level(self, score: int) -> str:
        """Determine alert level from score"""
        if score >= 75:
            return "red"
        elif score >= 55:
            return "orange"
        elif score >= 35:
            return "yellow"
        return "green"
    
    def format_number(self, num: float, suffix: str = "") -> str:
        """Format large numbers"""
        if num >= 1e9:
            return f"${num/1e9:.2f}B{suffix}"
        elif num >= 1e6:
            return f"${num/1e6:.2f}M{suffix}"
        elif num >= 1e3:
            return f"${num/1e3:.2f}K{suffix}"
        return f"${num:.2f}{suffix}"
    
    def analyze_single_token(self, token: str, chain: str) -> Dict:
        """Mode A: Deep analysis on single token"""
        chain = "eth" if str(chain).strip().lower() == "ethereum" else str(chain).strip().lower()
        print(f"🔍 Analyzing {token.upper()} on {chain}...")
        
        # Fetch data
        token_data = self.get_token_data(token, chain)
        if not token_data:
            return {"error": f"Could not fetch data for {token} on {chain}"}
        
        whales = self.get_whale_data(token, chain)
        history = self.get_price_history(token, chain, days=30)
        
        # Calculate score
        score = self.calculate_accumulation_score(token_data, history, whales)
        
        # Get detailed signal descriptions
        _, whale_desc = self.calculate_whale_score(whales)
        _, anomaly_desc = self.calculate_anomaly_score(token_data, history)
        _, pattern_desc = self.match_historical_pattern(token_data, history, whales)
        
        # Build report
        report = {
            "token": token_data.symbol,
            "name": token_data.name,
            "chain": chain,
            "address": token_data.address,
            "price": token_data.price,
            "price_change_24h": token_data.price_change_24h,
            "volume_24h": token_data.volume_24h,
            "tvl": token_data.tvl,
            "holders": token_data.holders,
            "market_cap": token_data.market_cap,
            "risk_score": token_data.risk_score,
            "score": {
                "total": score.total,
                "risk_adjusted": score.risk_adjusted,
                "confidence": score.confidence,
                "alert_level": score.alert_level,
                "market_phase": score.market_phase
            },
            "signals": {
                "volume_divergence": score.volume_divergence,
                "volume_momentum": score.volume_momentum,
                "tvl_stability": score.tvl_stability,
                "holder_distribution": score.holder_distribution,
                "tvl_confidence": score.tvl_confidence,
                "whale_score": score.whale_score,
                "anomaly_score": score.anomaly_score,
                "pattern_match": score.pattern_match
            },
            "descriptions": {
                "whale": whale_desc,
                "anomaly": anomaly_desc,
                "pattern": pattern_desc
            },
            "whales": [
                {
                    "address": w.address,
                    "balance_ratio": w.balance_ratio,
                    "change_24h": w.balance_change_24h,
                    "is_new": w.is_new
                }
                for w in whales[:10]  # Top 10
            ]
        }
        
        return report
    
    def print_single_report(self, report: Dict):
        """Print formatted single token report"""
        if "error" in report:
            print(f"❌ {report['error']}")
            return
            
        s = report["score"]
        sig = report["signals"]
        
        alert_emoji = ALERT_LEVELS.get(s["alert_level"], "⚪")
        phase_emoji = {"bull": "🐂", "bear": "🐻", "consolidation": "➡️"}.get(s["market_phase"], "➡️")
        
        print("\n" + "=" * 55)
        print(f" AVE ACCUMULATION MONITOR — {report['token'].upper()}")
        print("=" * 55)
        print(f"Chain: {report['chain']} | Contract: {report['address'][:20]}...")
        print(f"Price: ${report['price']:.4f} | 24h: {report['price_change_24h']:+.1f}% | TVL: {self.format_number(report['tvl'])}")
        print()
        print(f"ACCUMULATION SCORE: {s['total']}/100 [{alert_emoji} {s['alert_level'].upper()}]")
        print(f"Risk-Adjusted: {s['risk_adjusted']}/100 | Confidence: {s['confidence']}%")
        print(f"Market Phase: {phase_emoji} {s['market_phase'].upper()}")
        print()
        print("SIGNAL BREAKDOWN:")
        print(f" Volume/Price Divergence: {sig['volume_divergence']}/30 ⚡")
        print(f" Volume Momentum Velocity: {sig['volume_momentum']}/25 📈")
        print(f" TVL Stability: {sig['tvl_stability']}/20 🏦")
        print(f" Holder Distribution: {sig['holder_distribution']}/15 👥")
        print(f" TVL Confidence: {sig['tvl_confidence']}/10 💰")
        print()
        print("ADVANCED SIGNALS:")
        print(f" 🐋 Whale Activity: {sig['whale_score']}/40")
        print(f"    {report['descriptions']['whale']}")
        print(f" 📊 Anomaly: {report['descriptions']['anomaly']}")
        print(f" 📚 Pattern: {report['descriptions']['pattern']}")
        print()
        
        if report["whales"]:
            print("TOP WHALES:")
            for w in report["whales"][:5]:
                new_flag = " 🆕" if w["is_new"] else ""
                change = f"({w['change_24h']:+.1f}%)" if w["change_24h"] != 0 else ""
                print(f"  {w['address'][:8]}...{w['address'][-4:]}: {w['balance_ratio']:.2f}% {change}{new_flag}")
            print()
        
        # Next actions based on score
        print("NEXT ACTIONS:")
        if s["risk_adjusted"] >= 75:
            print("  🔴 STRONG CONVICTION — Multiple signals firing")
            print("  1. Monitor in real-time for confirmation")
            print("  2. Watch for volume breakout above 4x baseline")
            print("  3. Track whale follow-through in next 2-4 hours")
        elif s["risk_adjusted"] >= 55:
            print("  🟠 HIGH PROBABILITY WINDOW")
            print("  1. Check again in 2 hours for signal persistence")
            print("  2. Monitor whale activity for continued entry")
            print("  3. Watch for holder growth acceleration")
        elif s["risk_adjusted"] >= 35:
            print("  🟡 ACTIVE WATCH")
            print("  1. Monitor daily for signal development")
            print("  2. Wait for additional confirmation signals")
        else:
            print("  🟢 BACKGROUND WATCH")
            print("  1. No actionable pattern yet")
            print("  2. Check back in 24-48 hours")
        
        print("=" * 55)
    
    def sweep_scan(self, category: str, chain: str, top_n: int = 5) -> List[Dict]:
        """Mode B: Sweep scan across a chain with optional category filter."""
        chain = "eth" if str(chain).strip().lower() == "ethereum" else str(chain).strip().lower()
        top_n = max(1, min(int(top_n), 20))
        category_norm = str(category or "all").strip().lower()
        is_network_wide = category_norm in {"", "all", "any", "network", "network-wide", "chain", "*"}
        scope_text = "network-wide" if is_network_wide else f"{category_norm} filter"
        print(f"🔍 Scanning {scope_text} on {chain}...")

        chain_fallback_tokens = {
            "solana": ["SOL", "JUP", "RAY", "BONK", "WIF", "PYTH", "JTO", "RNDR", "JTO", "WEN", "POPCAT", "BOME"],
            "eth": ["ETH", "UNI", "AAVE", "MKR", "LDO", "PEPE", "LINK", "ARB", "OP", "CRV", "SNX", "MATIC"],
            "bsc": ["BNB", "CAKE", "XVS", "BAKE", "TWT", "DOGE", "SHIB", "FLOKI", "XRP", "ETH", "BTC", "USDT"],
            "base": ["ETH", "AERO", "DEGEN", "BRETT", "USDC", "BALD", "TOSHI", "KEYCAT", "PRIME", "AAVE", "LINK", "UNI"],
            "arbitrum": ["ARB", "GMX", "RDNT", "MAGIC", "GRAIL", "ETH", "LINK", "AAVE", "UNI", "USDC", "PENDLE", "WBTC"],
            "optimism": ["OP", "VELO", "SNX", "LYRA", "ETH", "USDC", "AAVE", "LINK", "UNI", "WBTC", "PERP", "SUSD"],
            "polygon": ["POL", "AAVE", "QUICK", "SUSHI", "GHST", "USDC", "WETH", "WBTC", "LINK", "CRV", "MKR", "BAL"],
            "avalanche": ["AVAX", "JOE", "PNG", "QI", "GMX", "USDC", "WETH", "WBTC", "LINK", "AAVE", "UNI", "MIM"],
        }

        candidates = self._fetch_sweep_candidates(category_norm, chain, limit=max(60, top_n * 18))

        if len(candidates) < max(top_n * 3, 30):
            extra_candidates = self._fetch_chain_token_candidates(chain, limit=max(80, top_n * 24))
            merged = []
            seen_candidate_keys = set()
            for cand in (candidates + extra_candidates):
                symbol = str(cand.get("symbol", "")).strip().upper()
                address = str(cand.get("address", "")).strip().lower()
                key = address if _looks_like_address(address) else f"sym:{symbol}"
                if not key or key in seen_candidate_keys:
                    continue
                seen_candidate_keys.add(key)
                merged.append(cand)
            candidates = merged

        if candidates:
            tokens = candidates
        else:
            fallback_symbols = chain_fallback_tokens.get(chain.lower(), chain_fallback_tokens["solana"])
            tokens = [{"symbol": t, "address": "", "search_text": t.lower()} for t in fallback_symbols]

        # Analyze a rotating window so sweep results are not always the same.
        max_scan = max(24, min(len(tokens), max(top_n * 10, top_n + 24)))
        if tokens and len(tokens) > max_scan:
            rotate_by = int(time.time() // 300) % len(tokens)
            tokens = tokens[rotate_by:] + tokens[:rotate_by]
            tokens = tokens[:max_scan]
        
        results = []
        scanned_queries = set()
        seen_result_keys = set()

        def build_heuristic_report(candidate: Dict, idx: int) -> Dict:
            symbol = str(candidate.get("symbol") or candidate.get("name") or f"TOK{idx+1}").strip().upper()
            address = str(candidate.get("address") or symbol).strip()
            price = float(candidate.get("price", 0.0) or 0.0)
            change_24h = float(candidate.get("price_change_24h", 0.0) or 0.0)
            volume_24h = float(candidate.get("volume_24h", 0.0) or 0.0)
            tvl = float(candidate.get("tvl", 0.0) or 0.0)
            holders = int(candidate.get("holders", 0) or 0)
            market_cap = float(candidate.get("market_cap", 0.0) or 0.0)
            risk_raw = float(candidate.get("risk_score", 50) or 50)
            risk_adjusted = max(5, min(95, int(100 - risk_raw)))
            alert_level = "red" if risk_adjusted >= 75 else "orange" if risk_adjusted >= 55 else "yellow" if risk_adjusted >= 35 else "green"
            phase = "bull" if change_24h > 2 else "bear" if change_24h < -2 else "consolidation"
            vol_div = max(0, min(30, int(abs(change_24h) * 1.2 + (12 if volume_24h > 0 else 4))))
            vol_mom = max(0, min(25, int(abs(change_24h) * 0.8 + 5)))
            whale_score = max(0, min(40, int(20 + (50 - risk_raw) * 0.4)))

            return {
                "token": symbol,
                "chain": chain,
                "address": address,
                "price": price,
                "price_change_24h": change_24h,
                "volume_24h": volume_24h,
                "tvl": tvl,
                "holders": holders,
                "market_cap": market_cap,
                "risk_score": int(risk_raw),
                "score": {
                    "total": risk_adjusted,
                    "risk_adjusted": risk_adjusted,
                    "confidence": 20,
                    "alert_level": alert_level,
                    "market_phase": phase,
                },
                "signals": {
                    "volume_divergence": vol_div,
                    "volume_momentum": vol_mom,
                    "tvl_stability": max(0, min(20, int(10 + (tvl > 0) * 6))),
                    "holder_distribution": max(0, min(15, int(6 + (holders > 0) * 4))),
                    "tvl_confidence": max(0, min(10, int(3 + (tvl > 0) * 4))),
                    "whale_score": whale_score,
                    "anomaly_score": max(0, min(27, int(abs(change_24h) * 0.6 + 4))),
                    "pattern_match": max(0, min(8, int(abs(change_24h) * 0.15 + 2))),
                },
                "descriptions": {
                    "whale": "Heuristic fallback (API unavailable)",
                    "anomaly": "Heuristic fallback (API unavailable)",
                    "pattern": "Heuristic fallback (API unavailable)",
                },
                "whales": [],
            }

        def append_report_if_unique(report: Dict) -> bool:
            symbol_key = str(report.get("token", "")).strip().upper()
            address_key = str(report.get("address", "")).strip().lower()
            dedupe_key = address_key if _looks_like_address(address_key) else f"sym:{symbol_key}"
            if not dedupe_key or dedupe_key in seen_result_keys:
                return False
            seen_result_keys.add(dedupe_key)
            results.append(report)
            return True

        for item in tokens:
            try:
                symbol = str(item.get("symbol", "")).strip().upper()
                address = str(item.get("address", "")).strip()
                token_query = address if _looks_like_address(address) else symbol
                if not token_query:
                    continue

                query_key = token_query.strip().lower()
                if query_key in scanned_queries:
                    continue
                scanned_queries.add(query_key)

                report = self.analyze_single_token(token_query, chain)
                if "error" not in report:
                    if append_report_if_unique(report) and len(results) >= top_n:
                        break

                time.sleep(0.25)  # Rate limiting
            except Exception as e:
                print(f"  ⚠️ Error analyzing {item}: {e}")
                continue

        if len(results) < top_n:
            fallback_symbols = chain_fallback_tokens.get(chain.lower(), chain_fallback_tokens["solana"])
            for symbol in fallback_symbols:
                if len(results) >= top_n:
                    break
                query_key = symbol.strip().lower()
                if query_key in scanned_queries:
                    continue
                scanned_queries.add(query_key)
                try:
                    report = self.analyze_single_token(symbol, chain)
                    if "error" in report:
                        continue

                    append_report_if_unique(report)
                except Exception as e:
                    print(f"  ⚠️ Fallback analyze error {symbol}: {e}")
                time.sleep(0.2)

        # Final recovery pass: try remaining candidate symbols regardless of previous query ordering.
        if len(results) < top_n:
            for item in tokens:
                if len(results) >= top_n:
                    break
                symbol = str(item.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                query_key = f"sym-retry:{symbol.lower()}"
                if query_key in scanned_queries:
                    continue
                scanned_queries.add(query_key)
                try:
                    report = self.analyze_single_token(symbol, chain)
                    if "error" in report:
                        continue
                    append_report_if_unique(report)
                except Exception:
                    continue
                time.sleep(0.12)

        # Strict-top fallback: synthesize rows from candidate pool if API still doesn't provide enough reports.
        if len(results) < top_n:
            for idx, item in enumerate(tokens):
                if len(results) >= top_n:
                    break
                if not isinstance(item, dict):
                    continue
                try:
                    heuristic = build_heuristic_report(item, idx)
                    append_report_if_unique(heuristic)
                except Exception:
                    continue
        
        # Sort by risk-adjusted score
        results.sort(key=lambda x: x["score"]["risk_adjusted"], reverse=True)
        
        return results[:top_n]
    
    def print_sweep_report(self, results: List[Dict], category: str, chain: str):
        """Print formatted sweep scan report"""
        category_norm = str(category or "all").strip().lower()
        is_network_wide = category_norm in {"", "all", "any", "network", "network-wide", "chain", "*"}
        scope_label = "NETWORK-WIDE" if is_network_wide else f"{category_norm.upper()} FILTER"

        print("\n" + "=" * 55)
        print(f" AVE ACCUMULATION SWEEP — {scope_label}")
        print(f" Chain: {chain} | Top {len(results)} results")
        print("=" * 55)
        print()
        
        for i, r in enumerate(results, 1):
            s = r["score"]
            sig = r.get("signals", {})
            alert_emoji = ALERT_LEVELS.get(s["alert_level"], "⚪")
            
            print(f"#{i}. {r['token'].upper()} [{r['chain']}] | Score: {s['total']}/100 | {alert_emoji} {s['alert_level'].upper()}")
            print(f"   Price: ${r['price']:.4f} | TVL: {self.format_number(r['tvl'])} | Vol 24h: {self.format_number(r['volume_24h'])}")
            
            # Multi-signal summary
            signals_firing = []
            if sig.get("whale_score", 0) >= 20:
                signals_firing.append("🐋 Whale")
            if sig.get("anomaly_score", 0) >= 8:
                signals_firing.append("📊 Anomaly")
            if sig.get("pattern_match", 0) >= 8:
                signals_firing.append("📚 Pattern")
            if sig.get("volume_divergence", 0) >= 20:
                signals_firing.append("⚡ Volume")
            
            if signals_firing:
                print(f"   🔥 Multi-signal: {' + '.join(signals_firing)}")
            print()
        
        # Market sentiment
        avg_score = sum(r["score"]["risk_adjusted"] for r in results) / len(results) if results else 0
        high_signals = sum(1 for r in results if r["score"]["alert_level"] in ["orange", "red"])
        
        print("📈 MARKET SENTIMENT:")
        if avg_score >= 60:
            print(f"   Strong accumulation signals detected. {high_signals} tokens showing high probability.")
        elif avg_score >= 40:
            print(f"   Mixed signals. {high_signals} tokens warrant close monitoring.")
        else:
            print("   Weak accumulation patterns. No immediate opportunities.")
        
        print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        description="Ave Accumulation Monitor - Detect smart money accumulation before price moves",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single token analysis
  python ave_monitor.py --mode single --token TRUMP --chain solana

    # Sweep scan network-wide by chain
    python ave_monitor.py --mode sweep --category all --chain solana --top 5

  # Output JSON for automation
  python ave_monitor.py --mode single --token PEPE --chain ethereum --json

For detailed help: python help.py
        """
    )
    parser.add_argument("--mode", choices=["single", "sweep"],
                       help="Analysis mode: single token or sweep scan")
    parser.add_argument("--token", help="Token symbol or address (for single mode)")
    parser.add_argument("--chain", default="solana",
                       help="Blockchain: solana, ethereum, bsc, base, arbitrum, optimism, polygon, avalanche (default: solana)")
    parser.add_argument("--category", default="all",
                       help="Optional sweep filter: all, trending, meme, defi, gaming, ai, new (default: all)")
    parser.add_argument("--top", type=int, default=5,
                       help="Number of top results for sweep mode (default: 5)")
    parser.add_argument("--json", action="store_true",
                       help="Output as JSON instead of formatted text")
    parser.add_argument("--help-full", action="store_true",
                       help="Show comprehensive help guide")
    
    args = parser.parse_args()
    
    if args.help_full or args.mode is None:
        import os
        help_path = os.path.join(os.path.dirname(__file__), "help.py")
        if os.path.exists(help_path):
            os.system(f"python3 {help_path}")
        else:
            print("Full help not available. Use --mode single or --mode sweep")
        sys.exit(0)
    
    monitor = AveAccumulationMonitor()
    
    if args.mode == "single":
        if not args.token:
            print("❌ --token required for single mode")
            sys.exit(1)
        
        report = monitor.analyze_single_token(args.token, args.chain)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            monitor.print_single_report(report)
    
    elif args.mode == "sweep":
        results = monitor.sweep_scan(args.category, args.chain, args.top)
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            monitor.print_sweep_report(results, args.category, args.chain)


if __name__ == "__main__":
    main()
