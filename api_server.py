#!/usr/bin/env python3
import os
import sys
import time
from typing import Any, Dict, List, Optional
import requests
import logging

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from ave_monitor import AveAccumulationMonitor
from alerts_manager import init_alerts_manager
from ave_api_service import get_ave_service

app = FastAPI(title="Ave Accumulation Monitor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize monitors
monitor = AveAccumulationMonitor()
alerts_manager = init_alerts_manager(os.getenv("TELEGRAM_BOT_TOKEN", ""))

SUPPORTED_CHAINS = [
    "solana",
    "ethereum",
    "bsc",
    "base",
    "arbitrum",
    "optimism",
    "polygon",
    "avalanche",
]

SUPPORTED_CATEGORIES = [
    "all",
    "trending",
    "meme",
    "defi",
    "gaming",
    "ai",
    "new",
]


# Request/Response Models
class AlertCreateRequest(BaseModel):
    user_id: int
    token: str
    chain: str
    alert_type: str  # price, risk, volume, whale, trend
    condition: str  # above, below, change
    threshold: float
    notify_telegram: bool = True
    notify_web: bool = True


class AlertResponse(BaseModel):
    id: str
    user_id: int
    token: str
    chain: str
    alert_type: str
    condition: str
    threshold: float
    enabled: bool
    created_at: str
    last_triggered: Optional[str] = None


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/chains")
def chains() -> Dict[str, List[str]]:
    return {"chains": SUPPORTED_CHAINS}


@app.get("/api/analyze")
def analyze(
    token: str = Query(..., min_length=1),
    chain: str = Query("solana", min_length=1),
) -> Dict[str, Any]:
    try:
        result = monitor.analyze_single_token(token.strip(), chain.strip().lower())
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analyze failed: {exc}")


@app.get("/api/prices/live")
def get_live_prices(
    tokens: str = Query(..., min_length=1, description="Comma-separated token symbols"),
    chain: str = Query("solana", min_length=1),
) -> Dict[str, Any]:
    """Get live prices for multiple tokens in one request."""
    try:
        chain_norm = chain.strip().lower()
        token_list = [
            tok.strip().lower()
            for tok in tokens.split(",")
            if tok and tok.strip()
        ]
        # Keep the endpoint light and predictable.
        token_list = list(dict.fromkeys(token_list))[:20]

        if not token_list:
            raise HTTPException(status_code=400, detail="No valid tokens provided")

        quotes: Dict[str, Dict[str, Any]] = {}
        for token in token_list:
            try:
                result = monitor.analyze_single_token(token, chain_norm)
                if not isinstance(result, dict) or "error" in result:
                    continue

                quotes[token] = {
                    "token": token,
                    "chain": chain_norm,
                    "price": _safe_float(result.get("price"), 0.0),
                    "price_change_24h": _safe_float(result.get("price_change_24h"), 0.0),
                    "timestamp": int(time.time()),
                }
            except Exception as exc:
                logger.warning(f"Live quote skipped for {token}-{chain_norm}: {exc}")

        return {
            "chain": chain_norm,
            "count": len(quotes),
            "quotes": quotes,
            "timestamp": int(time.time()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Live prices failed: {exc}")


@app.get("/api/sweep")
def sweep(
    category: str = Query("all", min_length=1),
    chain: str = Query("solana", min_length=1),
    top: int = Query(6, ge=1, le=20),
) -> Dict[str, Any]:
    try:
        result = monitor.sweep_scan(category.strip().lower(), chain.strip().lower(), top)
        return {"results": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sweep failed: {exc}")


def _parse_csv_list(raw: str) -> List[str]:
    vals = [x.strip().lower() for x in str(raw or "").split(",") if x and x.strip()]
    return list(dict.fromkeys(vals))


@app.get("/api/trends/category-network")
def category_network_trends(
    categories: str = Query("trending,meme,defi,gaming,ai", min_length=1),
    chains: str = Query(",".join(SUPPORTED_CHAINS), min_length=1),
    top: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    """Analyze trend tokens per category for each selected chain."""
    started = time.perf_counter()
    try:
        category_list = _parse_csv_list(categories)
        chain_list = _parse_csv_list(chains)

        if not category_list:
            raise HTTPException(status_code=400, detail="No categories provided")
        if not chain_list:
            raise HTTPException(status_code=400, detail="No chains provided")

        invalid_categories = [c for c in category_list if c not in SUPPORTED_CATEGORIES]
        if invalid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid categories: {', '.join(invalid_categories)}. Allowed: {', '.join(SUPPORTED_CATEGORIES)}",
            )

        invalid_chains = [c for c in chain_list if c not in SUPPORTED_CHAINS]
        if invalid_chains:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chains: {', '.join(invalid_chains)}. Allowed: {', '.join(SUPPORTED_CHAINS)}",
            )

        matrix = monitor.get_category_network_trend_matrix(category_list, chain_list, top)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        total_rows = 0
        for chain in matrix.values():
            for rows in chain.values():
                total_rows += len(rows)

        return {
            "categories": category_list,
            "chains": chain_list,
            "top": top,
            "rows": total_rows,
            "elapsed_ms": elapsed_ms,
            "matrix": matrix,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Category-network trend analysis failed: {exc}")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _looks_like_address(value: Optional[str]) -> bool:
    if not value:
        return False
    v = value.strip()
    return len(v) >= 20 and " " not in v


def _api_get_json(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Any:
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _fetch_token_search(api_key: str, keyword: str, chain: str, limit: int = 20) -> List[Dict[str, Any]]:
    """GET /v2/tokens?keyword=... and normalize to list."""
    headers = {"X-API-KEY": api_key}
    url = "https://prod.ave-api.com/v2/tokens"
    params = {"keyword": keyword, "chain": chain, "limit": limit}
    body = _api_get_json(url, headers, params)

    data = body.get("data", body) if isinstance(body, dict) else body
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):
        for key in ("items", "list", "tokens", "rows", "results"):
            items = data.get(key)
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
    return []


def _pick_best_token_item(items: List[Dict[str, Any]], token: str) -> Optional[Dict[str, Any]]:
    """Prefer exact symbol/token match, then highest market cap."""
    if not items:
        return None

    token_upper = token.upper()
    token_lower = token.lower()

    exact = [
        x for x in items
        if str(x.get("symbol", "")).upper() == token_upper
        or str(x.get("token", "")).lower() == token_lower
    ]
    pool = exact if exact else items
    pool.sort(key=lambda x: _safe_float(x.get("market_cap", 0)), reverse=True)
    return pool[0] if pool else None


def _fetch_token_detail(api_key: str, token_address: str, chain: str) -> Dict[str, Any]:
    """GET /v2/tokens/{token-id} and return data object."""
    headers = {"X-API-KEY": api_key}
    token_id = f"{token_address}-{chain}"
    url = f"https://prod.ave-api.com/v2/tokens/{token_id}"
    body = _api_get_json(url, headers)
    if isinstance(body, dict):
        return body.get("data", {}) if isinstance(body.get("data", {}), dict) else {}
    return {}


def _extract_pairs_from_token_detail(detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract pairs from token detail data.pairs[] list."""
    pairs = detail.get("pairs", []) if isinstance(detail, dict) else []
    if not isinstance(pairs, list):
        return []
    return [x for x in pairs if isinstance(x, dict) and isinstance(x.get("pair"), str)]


def _sort_pair_candidates(pairs: List[Dict[str, Any]]) -> List[str]:
    """Sort pair candidates by liquidity/activity then return pair ids."""
    def score(p: Dict[str, Any]) -> float:
        # Prefer active liquid pair.
        return (
            _safe_float(p.get("volume_u", 0))
            + _safe_float(p.get("tvl", 0))
            + _safe_float(p.get("tx_24h_count", 0))
        )

    pairs_sorted = sorted(pairs, key=score, reverse=True)
    out: List[str] = []
    for p in pairs_sorted:
        pair = str(p.get("pair", "")).strip()
        if pair and pair not in out:
            out.append(pair)
    return out


def _resolve_pair_candidates_from_ave(api_key: str, token: str, chain: str) -> List[str]:
    """Resolve pair candidates based on official flow: /v2/tokens -> /v2/tokens/{token-id}."""
    try:
        search_items = _fetch_token_search(api_key, token, chain)
        best_item = _pick_best_token_item(search_items, token)
        if not best_item:
            logger.warning(f"No token match from /v2/tokens for {token}-{chain}")
            return []

        token_address = str(best_item.get("token", "")).strip()
        if not token_address:
            logger.warning(f"Best token item has no token address for {token}-{chain}")
            return []

        detail = _fetch_token_detail(api_key, token_address, chain)
        pair_items = _extract_pairs_from_token_detail(detail)
        pair_candidates = _sort_pair_candidates(pair_items)

        logger.info(
            f"Resolved pair candidates for {token}-{chain} via token_id={token_address}-{chain}: {pair_candidates[:5]}"
        )
        return pair_candidates
    except Exception as exc:
        logger.warning(f"Failed resolving pair candidates for {token}-{chain}: {exc}")
        return []


def _request_ave_klines(api_key: str, pair_candidate: str, chain: str, interval: int, limit: int) -> Dict[str, Any]:
    """Call AVE klines API for a single pair candidate."""
    url = f"https://prod.ave-api.com/v2/klines/pair/{pair_candidate}-{chain.lower()}"
    headers = {"X-API-KEY": api_key}
    params = {
        "interval": interval,
        "limit": limit,
        "category": "u",
    }
    logger.info(f"Fetching klines URL: {url}")
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _request_ave_klines_token(api_key: str, token_candidate: str, chain: str, interval: int, limit: int) -> Dict[str, Any]:
    """Call AVE klines API using token-id endpoint as fallback."""
    url = f"https://prod.ave-api.com/v2/klines/token/{token_candidate}-{chain.lower()}"
    headers = {"X-API-KEY": api_key}
    params = {
        "interval": interval,
        "limit": limit,
    }
    logger.info(f"Fetching token klines URL: {url}")
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _extract_points_raw_from_ave_response(data: Any) -> List[Dict[str, Any]]:
    """Extract points list from AVE response shapes."""
    if isinstance(data, dict):
        if data.get("status") != 1:
            return []
        raw_data = data.get("data", [])
    elif isinstance(data, list):
        raw_data = data
    else:
        raw_data = []

    if isinstance(raw_data, dict):
        points_raw = raw_data.get("points", [])
    elif isinstance(raw_data, list):
        points_raw = raw_data
    else:
        points_raw = []

    return [p for p in points_raw if isinstance(p, dict)]


def _resolve_token_candidates_from_ave(api_key: str, token: str, chain: str) -> List[str]:
    """Resolve token-address candidates from /v2/tokens search results."""
    try:
        items = _fetch_token_search(api_key, token, chain)
        if not items:
            return []

        token_upper = token.upper()
        token_lower = token.lower()
        exact = [
            x
            for x in items
            if str(x.get("symbol", "")).upper() == token_upper
            or str(x.get("token", "")).lower() == token_lower
        ]
        pool = exact if exact else items
        pool = sorted(pool, key=lambda x: _safe_float(x.get("market_cap", 0)), reverse=True)

        out: List[str] = []
        for item in pool:
            cand = str(item.get("token", "")).strip()
            if cand and cand not in out:
                out.append(cand)
            if len(out) >= 8:
                break

        return out
    except Exception as exc:
        logger.warning(f"Failed resolving token candidates for {token}-{chain}: {exc}")
        return []


@app.get("/api/klines")
def get_klines(
    token: str = Query(..., min_length=1),
    chain: str = Query("solana", min_length=1),
    days: int = Query(7, ge=1, le=90),
    interval: int = Query(60, description="Interval in minutes (1, 5, 15, 30, 60, 120, 240, 1440)"),
    pair_address: Optional[str] = Query(None, description="Explicit AVE pair address override"),
    token_address: Optional[str] = Query(None, description="Explicit AVE token address override (CA)"),
    strict_live: bool = Query(True, description="If true, fail instead of falling back to mock data"),
) -> Dict[str, Any]:
    """
    Fetch historical candlestick data from AVE Cloud
    
    Args:
        token: Token symbol or pair address
        chain: Blockchain name
        days: Number of days of history
        interval: Candlestick interval in minutes
    
    Returns:
        Historical candlestick data in OHLCV format
    """
    try:
        api_key = os.getenv("AVE_API_KEY", "")

        logger.info(f"AVE_API_KEY exists: {bool(api_key)}")

        if not api_key:
            if strict_live:
                raise HTTPException(status_code=500, detail="AVE_API_KEY is missing while strict_live=true")
            logger.warning("⚠️ AVE_API_KEY not set, using mock data")
            return generate_mock_klines(token, days, interval)

        # Get BONK pair address for testing
        # In production, would resolve token symbol to pair address
        pair_map = {
            "bonk-solana": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
            "bonk": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263-solana": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"
        }

        resolved_token_address = token_address.strip() if token_address else ""
        if not resolved_token_address and _looks_like_address(token):
            resolved_token_address = token.strip()

        explicit_pair_requested = bool(pair_address and pair_address.strip())
        explicit_token_requested = bool(token_address and token_address.strip())
        prefer_token_mode = explicit_token_requested and not explicit_pair_requested

        resolved_pair_address = pair_address.strip() if pair_address else None
        if not resolved_pair_address and not prefer_token_mode:
            resolved_pair_address = pair_map.get(f"{token.lower()}-{chain.lower()}")
        if not resolved_pair_address and not prefer_token_mode:
            resolved_pair_address = pair_map.get(token.lower())

        resolved_token_candidates = _resolve_token_candidates_from_ave(api_key, token, chain)
        if resolved_token_address and resolved_token_address not in resolved_token_candidates:
            resolved_token_candidates.insert(0, resolved_token_address)
        if not resolved_token_address and resolved_token_candidates:
            resolved_token_address = resolved_token_candidates[0]

        limit = min(1000, int(days * 1440 / interval))

        # Build candidate list: explicit input -> static map -> pair resolved from official token flow.
        candidate_pairs: List[str] = []
        for cand in (resolved_pair_address,):
            if isinstance(cand, str) and cand and cand not in candidate_pairs:
                candidate_pairs.append(cand)

        if not prefer_token_mode:
            resolved_from_search = _resolve_pair_candidates_from_ave(api_key, token, chain)
            for cand in resolved_from_search:
                if cand not in candidate_pairs:
                    candidate_pairs.append(cand)

        logger.info(f"Pair candidates for {token}-{chain}: {candidate_pairs}")

        data: Any = None
        used_pair: Optional[str] = None
        used_token_address: Optional[str] = resolved_token_address or None
        used_mode: str = "pair"
        last_error: Optional[Exception] = None
        best_partial_data: Any = None
        best_partial_count: int = 0
        best_partial_pair: Optional[str] = None
        best_partial_token: Optional[str] = used_token_address
        best_partial_mode: str = "pair"

        min_points_for_primary = 2

        for cand in candidate_pairs:
            try:
                response_data = _request_ave_klines(api_key, cand, chain, interval, limit)
                logger.info(f"AVE pair response: {response_data}")

                # If AVE responds with status!=1, keep trying next candidate.
                if isinstance(response_data, dict) and response_data.get("status") != 1:
                    logger.warning(
                        f"Pair candidate {cand} returned status={response_data.get('status')} msg={response_data.get('msg')}"
                    )
                    continue

                points_raw = _extract_points_raw_from_ave_response(response_data)
                if not points_raw:
                    logger.warning(f"Pair candidate {cand} returned empty points")
                    continue

                if len(points_raw) < min_points_for_primary:
                    logger.warning(f"Pair candidate {cand} returned only {len(points_raw)} candle(s), trying next candidate")
                    if len(points_raw) > best_partial_count:
                        best_partial_data = response_data
                        best_partial_count = len(points_raw)
                        best_partial_pair = cand
                        best_partial_mode = "pair"
                    continue

                data = response_data
                used_pair = cand
                used_mode = "pair"
                break
            except Exception as exc:
                last_error = exc
                logger.warning(f"Klines candidate failed ({cand}): {exc}")

        if data is None:
            token_candidates: List[str] = []
            if isinstance(resolved_token_address, str) and resolved_token_address and resolved_token_address not in token_candidates:
                token_candidates.append(resolved_token_address)

            for cand in resolved_token_candidates:
                if cand not in token_candidates:
                    token_candidates.append(cand)

            if isinstance(resolved_pair_address, str) and resolved_pair_address and resolved_pair_address not in token_candidates:
                token_candidates.append(resolved_pair_address)

            if _looks_like_address(token) and token not in token_candidates:
                token_candidates.append(token)

            logger.info(f"Token candidates for fallback {token}-{chain}: {token_candidates}")

            for cand in token_candidates:
                try:
                    response_data = _request_ave_klines_token(api_key, cand, chain, interval, limit)
                    logger.info(f"AVE token response: {response_data}")

                    if isinstance(response_data, dict) and response_data.get("status") != 1:
                        logger.warning(
                            f"Token candidate {cand} returned status={response_data.get('status')} msg={response_data.get('msg')}"
                        )
                        continue

                    points_raw = _extract_points_raw_from_ave_response(response_data)
                    if not points_raw:
                        logger.warning(f"Token candidate {cand} returned empty points")
                        continue

                    if len(points_raw) < min_points_for_primary:
                        logger.warning(f"Token candidate {cand} returned only {len(points_raw)} candle(s), trying next candidate")
                        if len(points_raw) > best_partial_count:
                            best_partial_data = response_data
                            best_partial_count = len(points_raw)
                            best_partial_pair = cand
                            best_partial_token = cand
                            best_partial_mode = "token"
                        continue

                    data = response_data
                    used_pair = cand
                    used_token_address = cand
                    used_mode = "token"
                    break
                except Exception as exc:
                    last_error = exc
                    logger.warning(f"Klines token fallback failed ({cand}): {exc}")

        if data is None and best_partial_data is not None:
            logger.warning(
                f"Using partial klines result with {best_partial_count} candle(s) for {token}-{chain} after exhausting candidates"
            )
            data = best_partial_data
            used_pair = best_partial_pair
            used_token_address = best_partial_token
            used_mode = best_partial_mode

        if data is None:
            if strict_live:
                raise HTTPException(status_code=502, detail=f"AVE request failed for all pair candidates: {last_error}")
            return generate_mock_klines(token, days, interval)

        # AVE response can be dict or list depending on endpoint/version
        if isinstance(data, dict):
            if data.get("status") != 1:
                msg = data.get("msg", "Unknown error")
                if strict_live:
                    raise HTTPException(status_code=502, detail=f"AVE API error: {msg}")
                logger.warning(f"⚠️ AVE API error: {msg}")
                return generate_mock_klines(token, days, interval)
            raw_data = data.get("data", [])
        elif isinstance(data, list):
            raw_data = data
        else:
            raw_data = []

        if isinstance(raw_data, dict):
            points_raw = raw_data.get("points", [])
        elif isinstance(raw_data, list):
            points_raw = raw_data
        else:
            points_raw = []

        def _to_num(v: Any, default: float = 0.0) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        def _to_time(v: Any) -> int:
            try:
                t = int(float(v))
            except (TypeError, ValueError):
                return 0
            # Convert ms to seconds if needed
            return t // 1000 if t > 10_000_000_000 else t

        points: List[Dict[str, Any]] = []
        for p in points_raw:
            if not isinstance(p, dict):
                continue

            # Preferred direct shape
            if all(k in p for k in ("time", "open", "high", "low", "close")):
                point = {
                    "time": _to_time(p.get("time")),
                    "open": _to_num(p.get("open")),
                    "high": _to_num(p.get("high")),
                    "low": _to_num(p.get("low")),
                    "close": _to_num(p.get("close")),
                    "volume": _to_num(p.get("volume", 0)),
                }
            else:
                # AVE kline stream/object shape: {"usd": {"time","open","high","low","close","volume"}}
                usd = p.get("usd", {}) if isinstance(p.get("usd", {}), dict) else {}
                point = {
                    "time": _to_time(usd.get("time", p.get("time"))),
                    "open": _to_num(usd.get("open", p.get("open"))),
                    "high": _to_num(usd.get("high", p.get("high"))),
                    "low": _to_num(usd.get("low", p.get("low"))),
                    "close": _to_num(usd.get("close", p.get("close"))),
                    "volume": _to_num(usd.get("volume", p.get("volume", 0))),
                }

            if point["time"] > 0 and point["high"] >= point["low"]:
                points.append(point)

        points.sort(key=lambda x: x["time"])
        logger.info(f"Klines count: {len(points)}")

        if not points and strict_live:
            raise HTTPException(status_code=502, detail="AVE returned empty klines")

        pair_for_response = (used_pair or resolved_pair_address) if used_mode == "pair" else ""
        token_address_for_response = str(used_token_address or resolved_token_address or "").strip()
        chain_suffix = f"-{chain.lower()}"
        if token_address_for_response.lower().endswith(chain_suffix):
            token_address_for_response = token_address_for_response[: -len(chain_suffix)]
        if not _looks_like_address(token_address_for_response):
            token_address_for_response = ""
        token_id_for_response = f"{token_address_for_response}-{chain.lower()}" if token_address_for_response else ""

        return {
            "token": token,
            "chain": chain,
            "pair_address": pair_for_response,
            "token_address": token_address_for_response,
            "token_id": token_id_for_response,
            "realtime_price_supported": bool(token_id_for_response or pair_for_response),
            "realtime_candle_supported": bool(pair_for_response),
            "interval": interval,
            "source": f"ave-cloud-{used_mode}",
            "points": points,
            "count": len(points)
        }

    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ AVE Cloud request failed: {e}")
        if strict_live:
            raise HTTPException(status_code=502, detail=f"AVE request failed: {e}")
        return generate_mock_klines(token, days, interval)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Klines error: {e}")
        raise HTTPException(status_code=500, detail=f"Klines failed: {e}")


def generate_mock_klines(token: str, days: int, interval: int) -> Dict[str, Any]:
    """Generate realistic mock candlestick data for fallback"""
    import random
    from datetime import datetime, timedelta
    
    points = []
    base_price = 100.0
    current_time = int(datetime.now().timestamp())
    interval_seconds = interval * 60
    
    # Calculate number of candles
    num_candles = int(days * 1440 / interval)
    
    for i in range(num_candles, 0, -1):
        timestamp = current_time - (i * interval_seconds)
        base_price *= (1 + random.uniform(-0.05, 0.08))
        
        open_price = base_price
        close_price = base_price * (1 + random.uniform(-0.02, 0.02))
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.03))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.03))
        volume = random.uniform(100000, 5000000)
        
        points.append({
            "time": timestamp,
            "open": round(open_price, 6),
            "high": round(high_price, 6),
            "low": round(low_price, 6),
            "close": round(close_price, 6),
            "volume": round(volume, 2)
        })
        
        base_price = close_price
    
    logger.info(f"📊 Generated {len(points)} mock candles for {token}")
    
    return {
        "token": token,
        "chain": "unknown",
        "pair_address": "",
        "token_address": "",
        "token_id": "",
        "realtime_price_supported": False,
        "realtime_candle_supported": False,
        "interval": interval,
        "source": "mock",
        "points": points,
        "count": len(points)
    }


@app.get("/api/chart")
def chart(
    token: str = Query(..., min_length=1),
    chain: str = Query("solana", min_length=1),
    days: int = Query(30, ge=3, le=120),
) -> Dict[str, Any]:
    """
    Get chart data (DEPRECATED - use /api/klines instead)
    Maintained for backward compatibility
    """
    return get_klines(token=token, chain=chain, days=days, interval=60)


# ============ AVE API INTEGRATION ENDPOINTS ============


@app.get("/api/ave/token/{ca}")
def get_ave_token(ca: str, chain: str = Query("bsc")) -> Dict[str, Any]:
    """Get token info from Ave API"""
    try:
        ave_service = get_ave_service()
        token_data = ave_service.get_token_info(ca, chain)
        
        if not token_data:
            raise HTTPException(status_code=404, detail=f"Token {ca} not found on {chain}")
        
        return {"success": True, "data": token_data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave API error: {exc}")


@app.get("/api/ave/tokens")
def get_ave_tokens(chain: str = Query("bsc"), limit: int = Query(50, ge=1, le=100)) -> Dict[str, Any]:
    """Get trending tokens from Ave API"""
    try:
        ave_service = get_ave_service()
        tokens = ave_service.get_tokens_by_chain(chain, limit)
        
        return {
            "success": True,
            "chain": chain,
            "count": len(tokens),
            "data": tokens
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave tokens error: {exc}")


@app.get("/api/ave/whales/{ca}")
def get_ave_whales(ca: str, chain: str = Query("bsc")) -> Dict[str, Any]:
    """Get whale movements from Ave API"""
    try:
        ave_service = get_ave_service()
        whales = ave_service.get_whale_movements(ca, chain)
        
        return {
            "success": True,
            "ca": ca,
            "chain": chain,
            "whales": whales
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave whales error: {exc}")


@app.get("/api/ave/holders/{ca}")
def get_ave_holders(ca: str, chain: str = Query("bsc")) -> Dict[str, Any]:
    """Get holder distribution from Ave API"""
    try:
        ave_service = get_ave_service()
        holders = ave_service.get_holder_distribution(ca, chain)
        
        return {
            "success": True,
            "ca": ca,
            "chain": chain,
            "distribution": holders
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave holders error: {exc}")


@app.post("/api/alerts/create")
def create_alert(req: AlertCreateRequest) -> Dict[str, Any]:
    """Create a new alert"""
    try:
        alert = alerts_manager.create_alert(
            user_id=req.user_id,
            token=req.token,
            chain=req.chain,
            alert_type=req.alert_type,
            condition=req.condition,
            threshold=req.threshold,
        )
        return {
            "success": True,
            "alert": {
                "id": alert.id,
                "token": alert.token,
                "chain": alert.chain,
                "alert_type": alert.alert_type,
                "condition": alert.condition,
                "threshold": alert.threshold,
                "enabled": alert.enabled,
                "created_at": alert.created_at,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Create alert failed: {exc}")


@app.get("/api/alerts/user/{user_id}")
def get_user_alerts(user_id: int) -> Dict[str, Any]:
    """Get all alerts for a user"""
    try:
        alerts = alerts_manager.get_user_alerts(user_id)
        return {
            "user_id": user_id,
            "alerts": [
                {
                    "id": a.id,
                    "token": a.token,
                    "chain": a.chain,
                    "alert_type": a.alert_type,
                    "condition": a.condition,
                    "threshold": a.threshold,
                    "enabled": a.enabled,
                    "created_at": a.created_at,
                    "last_triggered": a.last_triggered,
                }
                for a in alerts
            ],
            "count": len(alerts),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Get alerts failed: {exc}")


@app.get("/api/alerts/token/{token}")
def get_token_alerts(token: str, chain: str = Query("solana")) -> Dict[str, Any]:
    """Get all alerts for a token"""
    try:
        alerts = alerts_manager.get_alerts_for_token(token, chain)
        return {
            "token": token,
            "chain": chain,
            "alerts": [
                {
                    "id": a.id,
                    "condition": a.condition,
                    "threshold": a.threshold,
                    "enabled": a.enabled,
                    "alert_type": a.alert_type,
                }
                for a in alerts
            ],
            "count": len(alerts),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Get token alerts failed: {exc}")


@app.delete("/api/alerts/{alert_id}")
def delete_alert(alert_id: str) -> Dict[str, Any]:
    """Delete an alert"""
    try:
        success = alerts_manager.delete_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"success": True, "alert_id": alert_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delete alert failed: {exc}")


@app.put("/api/alerts/{alert_id}/toggle")
def toggle_alert(alert_id: str, enabled: bool = Body(...)) -> Dict[str, Any]:
    """Enable/disable an alert"""
    try:
        success = alerts_manager.update_alert_enabled(alert_id, enabled)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"success": True, "alert_id": alert_id, "enabled": enabled}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Toggle alert failed: {exc}")


@app.get("/api/alerts/stats")
def get_alerts_stats() -> Dict[str, Any]:
    """Get global alerts statistics"""
    try:
        total_alerts = len(alerts_manager.alerts)
        enabled = sum(1 for a in alerts_manager.alerts.values() if a.enabled)
        by_type = {}
        for alert in alerts_manager.alerts.values():
            by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1

        return {
            "total": total_alerts,
            "enabled": enabled,
            "disabled": total_alerts - enabled,
            "by_type": by_type,
            "monitored_tokens": len(set(a.token for a in alerts_manager.alerts.values())),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stats failed: {exc}")



    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
