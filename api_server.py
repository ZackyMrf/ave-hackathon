#!/usr/bin/env python3
import asyncio
import os
import random
import secrets
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import requests
import logging

from fastapi import FastAPI, HTTPException, Query, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _clean_env_value(raw: str) -> str:
    value = str(raw or "").strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        value = value[1:-1].strip()
    return value


def _load_local_env_file_defaults():
    """Populate missing env vars from local .env when server is started manually."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                os.environ[key] = _clean_env_value(value)
    except Exception:
        # Keep startup resilient even if .env parsing fails.
        pass


_load_local_env_file_defaults()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from ave_monitor import AveAccumulationMonitor
from alerts_manager import init_alerts_manager
from ave_api_service import get_ave_service
from ave_live_buysell_feed import AveLiveBuySellFeed

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


def _resolve_telegram_token() -> str:
    """Resolve Telegram token from manager/env and keep manager in sync."""
    env_token = _clean_env_value(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    manager_token = _clean_env_value(getattr(alerts_manager, "telegram_token", ""))
    token = env_token or manager_token

    if token and token != manager_token:
        alerts_manager.set_telegram_token(token)

    return token


TELEGRAM_DEEPLINK_TTL_SECONDS = 600
TELEGRAM_DEEPLINK_RETENTION_SECONDS = 3600
telegram_deeplink_sessions: Dict[str, Dict[str, Any]] = {}
telegram_deeplink_lock = threading.Lock()


def _prune_telegram_deeplink_sessions(now_ts: Optional[int] = None):
    ts = int(now_ts or time.time())
    expired_codes: List[str] = []

    for code, session in telegram_deeplink_sessions.items():
        expires_at = int(session.get("expires_at", 0) or 0)
        created_at = int(session.get("created_at", 0) or 0)

        if expires_at and ts > expires_at + TELEGRAM_DEEPLINK_RETENTION_SECONDS:
            expired_codes.append(code)
            continue
        if not expires_at and created_at and ts > created_at + TELEGRAM_DEEPLINK_RETENTION_SECONDS:
            expired_codes.append(code)

    for code in expired_codes:
        telegram_deeplink_sessions.pop(code, None)


def _get_telegram_bot_username() -> str:
    """Return bot username if Telegram token is valid and bot is reachable."""
    token = _resolve_telegram_token()
    if not token:
        return ""

    try:
        resp = requests.get(f"{alerts_manager.telegram_base_url}/getMe", timeout=5)
        payload = resp.json() if resp.content else {}
    except Exception:
        return ""

    if not (isinstance(payload, dict) and payload.get("ok")):
        return ""

    result = payload.get("result", {})
    return str(result.get("username") or "")


def _resolve_telegram_file_url(file_id: str) -> str:
    """Resolve Telegram file_id to downloadable file URL."""
    file_id_norm = str(file_id or "").strip()
    if not file_id_norm:
        return ""

    token = _resolve_telegram_token()
    if not token:
        return ""

    try:
        resp = requests.get(
            f"{alerts_manager.telegram_base_url}/getFile",
            params={"file_id": file_id_norm},
            timeout=8,
        )
        payload = resp.json() if resp.content else {}
        if not (isinstance(payload, dict) and payload.get("ok")):
            return ""

        file_path = str((payload.get("result") or {}).get("file_path") or "").strip()
        if not file_path:
            return ""

        return f"https://api.telegram.org/file/bot{token}/{file_path}"
    except Exception:
        return ""

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

CHAIN_ALIASES = {
    "ethereum": "eth",
}

SUPPORTED_CATEGORIES = [
    "all",
    "trending",
    "meme",
    "defi",
    "gaming",
    "ai",
    "new",
]

DEFAULT_LIVE_FEED_TOKENS: List[Dict[str, str]] = [
    # solana
    {
        "symbol": "WIF",
        "token_address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "chain": "solana",
    },
    {
        "symbol": "TRUMP",
        "token_address": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",
        "chain": "solana",
    },
    {
        "symbol": "JUP",
        "token_address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "chain": "solana",
    },
    {
        "symbol": "BONK",
        "token_address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "chain": "solana",
    },
    # ethereum
    {
        "symbol": "WETH",
        "token_address": "0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2",
        "chain": "ethereum",
    },
    {
        "symbol": "USDC",
        "token_address": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "chain": "ethereum",
    },
    {
        "symbol": "UNI",
        "token_address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "chain": "ethereum",
    },
    {
        "symbol": "PEPE",
        "token_address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        "chain": "ethereum",
    },
    # bsc
    {
        "symbol": "WBNB",
        "token_address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "chain": "bsc",
    },
    {
        "symbol": "USDT",
        "token_address": "0x55d398326f99059fF775485246999027B3197955",
        "chain": "bsc",
    },
    {
        "symbol": "CAKE",
        "token_address": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        "chain": "bsc",
    },
    {
        "symbol": "XVS",
        "token_address": "0xcf6bb5389c92bdda8a3747ddb454cb7a64626c63",
        "chain": "bsc",
    },
    # base
    {
        "symbol": "WETH",
        "token_address": "0x4200000000000000000000000000000000000006",
        "chain": "base",
    },
    {
        "symbol": "USDC",
        "token_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bDa02913",
        "chain": "base",
    },
    {
        "symbol": "cbBTC",
        "token_address": "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf",
        "chain": "base",
    },
    {
        "symbol": "DAI",
        "token_address": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        "chain": "base",
    },
    # arbitrum
    {
        "symbol": "WETH",
        "token_address": "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
        "chain": "arbitrum",
    },
    {
        "symbol": "USDC",
        "token_address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "chain": "arbitrum",
    },
    {
        "symbol": "ARB",
        "token_address": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "chain": "arbitrum",
    },
    {
        "symbol": "LINK",
        "token_address": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4",
        "chain": "arbitrum",
    },
    # optimism
    {
        "symbol": "WETH",
        "token_address": "0x4200000000000000000000000000000000000006",
        "chain": "optimism",
    },
    {
        "symbol": "USDC",
        "token_address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "chain": "optimism",
    },
    {
        "symbol": "OP",
        "token_address": "0x4200000000000000000000000000000000000042",
        "chain": "optimism",
    },
    {
        "symbol": "SNX",
        "token_address": "0x8700dAec35aF8Ff88c16BDF0413C4A4104C9Ede6",
        "chain": "optimism",
    },
    # polygon
    {
        "symbol": "WETH",
        "token_address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "chain": "polygon",
    },
    {
        "symbol": "USDC",
        "token_address": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
        "chain": "polygon",
    },
    {
        "symbol": "AAVE",
        "token_address": "0xD6DF932A45C0f255f85145f286EA0B292B21C90B",
        "chain": "polygon",
    },
    {
        "symbol": "LINK",
        "token_address": "0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39",
        "chain": "polygon",
    },
    # avalanche
    {
        "symbol": "WAVAX",
        "token_address": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
        "chain": "avalanche",
    },
    {
        "symbol": "USDC",
        "token_address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        "chain": "avalanche",
    },
    {
        "symbol": "WETH",
        "token_address": "0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB",
        "chain": "avalanche",
    },
    {
        "symbol": "WBTC",
        "token_address": "0x50b7545627a5162F82A992c33b87aDc75187B218",
        "chain": "avalanche",
    },
]


def _parse_token_with_optional_chain(token: str, default_chain: str) -> tuple[str, str]:
    """Support token inputs like <token> or <token>-<chain>."""
    token_raw = str(token or "").strip()
    chain_norm = _normalize_chain(default_chain)

    if not token_raw:
        return "", chain_norm

    if "-" in token_raw:
        base, suffix = token_raw.rsplit("-", 1)
        suffix_norm = _normalize_chain(suffix)
        if base.strip() and suffix_norm in SUPPORTED_CHAINS:
            return base.strip(), suffix_norm

    return token_raw, chain_norm


def _normalize_chain(chain: str) -> str:
    chain_norm = str(chain or "solana").strip().lower()
    return CHAIN_ALIASES.get(chain_norm, chain_norm)


def _read_env_value_from_dotenv(key: str) -> str:
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(dotenv_path):
        return ""

    key_prefix = f"{key}="
    try:
        with open(dotenv_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if not line.startswith(key_prefix):
                    continue
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return ""

    return ""


def _resolve_ave_api_key() -> str:
    key = str(os.getenv("AVE_API_KEY", "")).strip()
    if key:
        return key
    return _read_env_value_from_dotenv("AVE_API_KEY")


def _parse_live_tokens_arg(tokens_arg: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for raw in str(tokens_arg or "").split(","):
        item = raw.strip()
        if not item:
            continue
        parts = [x.strip() for x in item.split(":")]
        if len(parts) < 3:
            continue

        symbol = parts[0].upper()
        token_address = parts[1]
        chain = _normalize_chain(parts[2])
        pair_address = parts[3] if len(parts) > 3 else ""
        key = f"{token_address.lower()}:{chain}"
        if not symbol or not token_address or not chain or key in seen:
            continue

        seen.add(key)
        out.append(
            {
                "symbol": symbol,
                "token_address": token_address,
                "chain": chain,
                "pair_address": pair_address,
            }
        )

    return out


def _select_live_feed_tokens(tokens_arg: str, chain_filter: str, sample_size: int) -> List[Dict[str, str]]:
    explicit = _parse_live_tokens_arg(tokens_arg)
    if explicit:
        return explicit

    chain_norm = str(chain_filter or "all").strip().lower()
    per_chain_size = max(1, int(sample_size or 4))

    if chain_norm != "all":
        pool = [
            t
            for t in DEFAULT_LIVE_FEED_TOKENS
            if _normalize_chain(t.get("chain", "")) == chain_norm
        ]
        if not pool:
            pool = list(DEFAULT_LIVE_FEED_TOKENS)

        size = min(per_chain_size, len(pool))
        if size >= len(pool):
            return pool
        return random.sample(pool, k=size)

    selected: List[Dict[str, str]] = []
    for chain_name in SUPPORTED_CHAINS:
        chain_pool = [
            t
            for t in DEFAULT_LIVE_FEED_TOKENS
            if _normalize_chain(t.get("chain", "")) == chain_name
        ]
        if not chain_pool:
            continue

        size = min(per_chain_size, len(chain_pool))
        if size >= len(chain_pool):
            selected.extend(chain_pool)
        else:
            selected.extend(random.sample(chain_pool, k=size))

    return selected if selected else list(DEFAULT_LIVE_FEED_TOKENS)


def _build_fallback_report_from_ave(token_data: Dict[str, Any], chain: str, token_input: str) -> Dict[str, Any]:
    """Build a monitor-compatible payload from Ave direct token endpoint."""
    symbol = str(token_data.get("token") or token_input).strip()
    name = str(token_data.get("name") or symbol or token_input).strip()
    address = str(token_data.get("ca") or token_input).strip()
    whales_raw = token_data.get("_whales_raw") if isinstance(token_data, dict) else None
    whales_norm = _normalize_ave_whales(whales_raw)

    # --- FILTER PALSU ---
    MIN_TVL = 100_000   # $100k
    MIN_MARKETCAP = 1_000_000  # $1M
    native_tokens = {"ETH", "SOL", "BNB", "MATIC", "AVAX", "ARB", "OP"}
    is_native = symbol.upper() in native_tokens
    tvl = _safe_float(token_data.get("liquidity"), 0.0)
    market_cap = _safe_float(token_data.get("market_cap"), 0.0)
    if not is_native:
        if (tvl < MIN_TVL) or (market_cap < MIN_MARKETCAP):
            raise HTTPException(status_code=400, detail=f"Token {symbol} kemungkinan token palsu (TVL/MarketCap terlalu kecil).")

    new_whales = sum(1 for w in whales_norm if w.get("is_new") and _safe_float(w.get("balance_ratio"), 0.0) >= 1.5)
    accumulating = sum(1 for w in whales_norm if _safe_float(w.get("change_24h"), 0.0) > 5)
    distributing = sum(1 for w in whales_norm if _safe_float(w.get("change_24h"), 0.0) < -5)
    whale_score = max(0, min(40, int(new_whales * 12 + accumulating * 8 - distributing * 4)))
    whale_desc = f"{new_whales} new, {accumulating} accumulating, {distributing} distributing (v3 fallback)"

    return {
        "token": symbol,
        "name": name,
        "chain": chain,
        "address": address,
        "price": _safe_float(token_data.get("price"), 0.0),
        "price_change_24h": _safe_float(token_data.get("price_change_24h"), 0.0),
        "volume_24h": _safe_float(token_data.get("volume_24h"), 0.0),
        "tvl": tvl,
        "holders": int(token_data.get("holder_count") or 0),
        "market_cap": market_cap,
        "risk_score": 50,
        "score": {
            "total": 0,
            "risk_adjusted": 0,
            "confidence": 0,
            "alert_level": "green",
            "market_phase": "consolidation",
        },
        "signals": {
            "volume_divergence": 0,
            "volume_momentum": 0,
            "tvl_stability": 0,
            "holder_distribution": 0,
            "tvl_confidence": 0,
            "whale_score": whale_score,
            "anomaly_score": 0,
            "pattern_match": 0,
        },
        "descriptions": {
            "whale": whale_desc,
            "anomaly": "",
            "pattern": "",
        },
        "whales": whales_norm,
    }


def _normalize_ave_whales(raw_items: Any) -> List[Dict[str, Any]]:
    rows = raw_items if isinstance(raw_items, list) else []
    out: List[Dict[str, Any]] = []
    for item in rows[:50]:
        if not isinstance(item, dict):
            continue

        address = str(
            item.get("holder")
            or item.get("address")
            or item.get("wallet")
            or item.get("owner")
            or ""
        ).strip()
        if not address:
            continue

        ratio = _safe_float(
            item.get("balance_ratio", item.get("share", item.get("ratio", item.get("holding_percent", 0)))),
            0.0,
        )
        if 0 < ratio <= 1:
            ratio *= 100

        change_24h = _safe_float(
            item.get("change_24h", item.get("balance_change_24h", item.get("delta_24h", 0))),
            0.0,
        )
        is_new = bool(item.get("is_new") or item.get("new") or False)

        out.append(
            {
                "address": address,
                "balance_ratio": ratio,
                "change_24h": change_24h,
                "is_new": is_new,
            }
        )

    return out[:10]


def _pick_ave_token_from_chain_list(token_items: List[Dict[str, Any]], token_input: str) -> Optional[Dict[str, Any]]:
    query = str(token_input or "").strip()
    if not query:
        return None

    q_lower = query.lower()
    q_upper = query.upper()
    is_address = _looks_like_address(query)

    best: Optional[Dict[str, Any]] = None
    best_rank = -1
    best_liq = -1.0
    best_cap = -1.0

    for item in token_items:
        if not isinstance(item, dict):
            continue

        symbol = str(item.get("token") or item.get("symbol") or "").strip()
        name = str(item.get("name") or item.get("raw", {}).get("name") or "").strip()
        ca = str(item.get("ca") or item.get("address") or "").strip()

        rank = 0
        if is_address and ca.lower() == q_lower:
            rank = 100
        elif symbol.upper() == q_upper:
            rank = 95
        elif symbol.lower() == q_lower:
            rank = 90
        elif name and name.lower() == q_lower:
            rank = 85
        elif symbol.lower().startswith(q_lower):
            rank = 70
        elif q_lower in symbol.lower() and len(q_lower) >= 2:
            rank = 60
        elif name and q_lower in name.lower() and len(q_lower) >= 3:
            rank = 50

        if rank <= 0:
            continue

        # Legitimacy signals: TVL/liquidity is more reliable than market cap
        liq = _safe_float(item.get("liquidity", item.get("tvl")), 0.0)
        cap = _safe_float(item.get("market_cap"), 0.0)
        holders = int(_safe_float(item.get("holder_count", item.get("holder")), 0))

        # Penalise fake/scam tokens: exact symbol match but near-zero liquidity and holders
        if symbol.upper() == q_upper and liq < 1.0 and holders < 5 and not is_address:
            rank -= 50

        # Selection: rank > liquidity > market_cap
        if rank > best_rank:
            better = True
        elif rank == best_rank:
            better = liq > best_liq or (liq == best_liq and cap > best_cap)
        else:
            better = False

        if better:
            best = item
            best_rank = rank
            best_liq = liq
            best_cap = cap

    return best


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


class TelegramTestRequest(BaseModel):
    chat_id: int
    text: Optional[str] = None


class TelegramDeepLinkClaimRequest(BaseModel):
    code: str
    chat_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None


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
        parsed_token, parsed_chain = _parse_token_with_optional_chain(token, chain)
        result = monitor.analyze_single_token(parsed_token, parsed_chain)
        if "error" in result:
            # --- PATCH: Coba cari token asli jika error filter palsu ---
            ave_service = get_ave_service()
            token_items = ave_service.get_tokens_by_chain(parsed_chain, limit=100)
            # Cari token dengan symbol sama dan TVL/market cap terbesar
            candidates = [
                t for t in token_items
                if str(t.get("token", "")).strip().lower() == parsed_token.lower()
            ]
            if candidates:
                # Urutkan by TVL/market cap
                candidates.sort(key=lambda t: float(t.get("liquidity", 0)) + float(t.get("market_cap", 0)), reverse=True)
                picked = candidates[0]
                picked_ca = str(picked.get("ca") or "").strip()
                if picked_ca and picked_ca.lower() != parsed_token.lower():
                    # Ulangi analisa dengan address
                    return analyze(token=picked_ca, chain=parsed_chain)
            # --- END PATCH ---
            # Fallback lama
            ave_token = None
            if _looks_like_address(parsed_token):
                ave_token = ave_service.get_token_info(parsed_token, parsed_chain)
            else:
                token_items = ave_service.get_tokens_by_chain(parsed_chain, limit=100)
                picked = _pick_ave_token_from_chain_list(token_items, parsed_token)
                if picked:
                    picked_ca = str(picked.get("ca") or "").strip()
                    ave_token = ave_service.get_token_info(picked_ca, parsed_chain) if picked_ca else dict(picked)

            if ave_token:
                ca_for_whales = str(ave_token.get("ca") or parsed_token).strip()
                whales = ave_service.get_whale_movements(ca_for_whales, parsed_chain) if ca_for_whales else []
                ave_token["_whales_raw"] = whales
                return _build_fallback_report_from_ave(ave_token, parsed_chain, parsed_token)
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
        chain_norm = _normalize_chain(chain)
        raw_tokens = [tok.strip() for tok in tokens.split(",") if tok and tok.strip()]
        token_list: List[str] = []
        seen = set()
        for tok in raw_tokens:
            dedupe_key = tok.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            token_list.append(tok)
        # Keep the endpoint light and predictable.
        token_list = token_list[:20]

        if not token_list:
            raise HTTPException(status_code=400, detail="No valid tokens provided")

        quotes: Dict[str, Dict[str, Any]] = {}
        for token_input in token_list:
            try:
                parsed_token, parsed_chain = _parse_token_with_optional_chain(token_input, chain_norm)
                result = monitor.analyze_single_token(parsed_token, parsed_chain)
                if not isinstance(result, dict) or "error" in result:
                    continue

                quote_key = token_input
                quotes[quote_key] = {
                    "token": parsed_token,
                    "chain": parsed_chain,
                    "price": _safe_float(result.get("price"), 0.0),
                    "price_change_24h": _safe_float(result.get("price_change_24h"), 0.0),
                    "timestamp": int(time.time()),
                }
            except Exception as exc:
                logger.warning(f"Live quote skipped for {token_input}-{chain_norm}: {exc}")

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


def _build_fallback_sweep_rows(chain: str, top: int, existing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chain_norm = _normalize_chain(chain)
    fallback_tokens = {
        "solana": ["SOL", "JUP", "RAY", "BONK", "WIF", "PYTH", "JTO", "RNDR", "POPCAT", "BOME", "WEN", "JUPITER"],
        "ethereum": ["ETH", "UNI", "AAVE", "LINK", "CRV", "MKR", "SNX", "LDO", "ARB", "OP", "PEPE", "PENDLE"],
        "bsc": ["BNB", "CAKE", "XVS", "BAKE", "TWT", "DOGE", "SHIB", "FLOKI", "XRP", "ETH", "BTC", "USDT"],
        "base": ["ETH", "AERO", "DEGEN", "BRETT", "USDC", "BALD", "TOSHI", "KEYCAT", "PRIME", "AAVE", "LINK", "UNI"],
        "arbitrum": ["ARB", "GMX", "RDNT", "MAGIC", "GRAIL", "ETH", "LINK", "AAVE", "UNI", "USDC", "PENDLE", "WBTC"],
        "optimism": ["OP", "VELO", "SNX", "LYRA", "ETH", "USDC", "AAVE", "LINK", "UNI", "WBTC", "PERP", "SUSD"],
        "polygon": ["POL", "AAVE", "QUICK", "SUSHI", "GHST", "USDC", "WETH", "WBTC", "LINK", "CRV", "MKR", "BAL"],
        "avalanche": ["AVAX", "JOE", "PNG", "QI", "GMX", "USDC", "WETH", "WBTC", "LINK", "AAVE", "UNI", "MIM"],
    }

    out: List[Dict[str, Any]] = list(existing or [])
    seen = {
        str(row.get("address", "")).strip().lower() or f"sym:{str(row.get('token', '')).strip().upper()}"
        for row in out
    }

    tokens = fallback_tokens.get(chain_norm, fallback_tokens["solana"])
    idx = 0
    while len(out) < top:
        symbol = tokens[idx % len(tokens)]
        idx += 1
        key = f"sym:{symbol}"
        if key in seen:
            if idx > len(tokens) * 2:
                key = f"sym:{symbol}-{idx}"
            else:
                continue
        seen.add(key)

        out.append(
            {
                "token": symbol,
                "chain": chain_norm,
                "address": symbol,
                "price": 0.0,
                "price_change_24h": 0.0,
                "volume_24h": 0.0,
                "tvl": 0.0,
                "holders": 0,
                "market_cap": 0.0,
                "risk_score": 50,
                "score": {
                    "total": 0,
                    "risk_adjusted": 0,
                    "confidence": 0,
                    "alert_level": "green",
                    "market_phase": "consolidation",
                },
                "signals": {
                    "volume_divergence": 0,
                    "volume_momentum": 0,
                    "tvl_stability": 0,
                    "holder_distribution": 0,
                    "tvl_confidence": 0,
                    "whale_score": 0,
                    "anomaly_score": 0,
                    "pattern_match": 0,
                },
                "descriptions": {
                    "whale": "Fallback row (data unavailable)",
                    "anomaly": "Fallback row (data unavailable)",
                    "pattern": "Fallback row (data unavailable)",
                },
                "whales": [],
                "is_fallback": True,
            }
        )

    return out[:top]


@app.get("/api/sweep")
def sweep(
    category: str = Query("all", min_length=1),
    chain: str = Query("solana", min_length=1),
    top: int = Query(6, ge=1, le=20),
) -> Dict[str, Any]:
    try:
        chain_norm = _normalize_chain(chain)
        result = monitor.sweep_scan(category.strip().lower(), chain_norm, top)
        normalized = result if isinstance(result, list) else []
        padded = _build_fallback_sweep_rows(chain_norm, top, normalized)
        return {
            "results": padded,
            "requested_top": top,
            "count": len(padded),
            "fallback_used": max(0, len(padded) - len(normalized)),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sweep failed: {exc}")


def _parse_csv_list(raw: str) -> List[str]:
    vals = [x.strip().lower() for x in str(raw or "").split(",") if x and x.strip()]
    return list(dict.fromkeys(vals))


def _parse_chain_csv_list(raw: str) -> List[str]:
    vals = [_normalize_chain(x) for x in str(raw or "").split(",") if x and x.strip()]
    vals = [x for x in vals if x]
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
        chain_list = _parse_chain_csv_list(chains)

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
    """Call AVE klines API using token-id endpoint as fallback.
    
    Validates that token_candidate is in proper format before making request.
    Expected format: address or address-chain or valid token_id.
    Rejects short symbol names like 'AAVE' as those cause 400 Bad Request.
    """
    token_candidate = str(token_candidate or "").strip()
    
    # Reject candidates that are clearly just symbol names (too short, uppercase-only)
    # Valid addresses should be longer or contain chain specifier
    if len(token_candidate) <= 6 and token_candidate.isalpha() and token_candidate.isupper():
        raise ValueError(f"Rejecting symbol-only candidate '{token_candidate}' (not a token address)")
    
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
        chain_norm = _normalize_chain(chain)
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
            resolved_pair_address = pair_map.get(f"{token.lower()}-{chain_norm.lower()}")
        if not resolved_pair_address and not prefer_token_mode:
            resolved_pair_address = pair_map.get(token.lower())

        resolved_token_candidates = _resolve_token_candidates_from_ave(api_key, token, chain_norm)
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
            resolved_from_search = _resolve_pair_candidates_from_ave(api_key, token, chain_norm)
            for cand in resolved_from_search:
                if cand not in candidate_pairs:
                    candidate_pairs.append(cand)

        logger.info(f"Pair candidates for {token}-{chain_norm}: {candidate_pairs}")

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
                response_data = _request_ave_klines(api_key, cand, chain_norm, interval, limit)
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

            logger.info(f"Token candidates for fallback {token}-{chain_norm}: {token_candidates}")

            for cand in token_candidates:
                try:
                    response_data = _request_ave_klines_token(api_key, cand, chain_norm, interval, limit)
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
                f"Using partial klines result with {best_partial_count} candle(s) for {token}-{chain_norm} after exhausting candidates"
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
        chain_suffix = f"-{chain_norm.lower()}"
        if token_address_for_response.lower().endswith(chain_suffix):
            token_address_for_response = token_address_for_response[: -len(chain_suffix)]
        if not _looks_like_address(token_address_for_response):
            token_address_for_response = ""
        token_id_for_response = f"{token_address_for_response}-{chain_norm.lower()}" if token_address_for_response else ""

        return {
            "token": token,
            "chain": chain_norm,
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
        chain_norm = _normalize_chain(chain)
        ave_service = get_ave_service()
        token_data = ave_service.get_token_info(ca, chain_norm)
        
        if not token_data:
            raise HTTPException(status_code=404, detail=f"Token {ca} not found on {chain_norm}")
        
        return {"success": True, "data": token_data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave API error: {exc}")


@app.get("/api/ave/tokens")
def get_ave_tokens(chain: str = Query("bsc"), limit: int = Query(50, ge=1, le=100)) -> Dict[str, Any]:
    """Get trending tokens from Ave API"""
    try:
        chain_norm = _normalize_chain(chain)
        ave_service = get_ave_service()
        tokens = ave_service.get_tokens_by_chain(chain_norm, limit)
        
        return {
            "success": True,
            "chain": chain_norm,
            "count": len(tokens),
            "data": tokens
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave tokens error: {exc}")


@app.get("/api/ave/whales/{ca}")
def get_ave_whales(ca: str, chain: str = Query("bsc")) -> Dict[str, Any]:
    """Get whale movements from Ave API"""
    try:
        chain_norm = _normalize_chain(chain)
        ave_service = get_ave_service()
        whales = ave_service.get_whale_movements(ca, chain_norm)
        
        return {
            "success": True,
            "ca": ca,
            "chain": chain_norm,
            "whales": whales
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave whales error: {exc}")


@app.get("/api/ave/holders/{ca}")
def get_ave_holders(ca: str, chain: str = Query("bsc")) -> Dict[str, Any]:
    """Get holder distribution from Ave API"""
    try:
        chain_norm = _normalize_chain(chain)
        ave_service = get_ave_service()
        holders = ave_service.get_holder_distribution(ca, chain_norm)
        
        return {
            "success": True,
            "ca": ca,
            "chain": chain_norm,
            "distribution": holders
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ave holders error: {exc}")


@app.websocket("/ws/live-buysell")
async def ws_live_buysell(websocket: WebSocket) -> None:
    """Bridge AVE multi_tx buy/sell feed to frontend websocket clients."""
    await websocket.accept()

    params = websocket.query_params
    chain_filter = _normalize_chain(params.get("chain", "solana")) if params.get("chain") else "all"
    sample_size = max(1, min(int(params.get("sample", "4")), 20))
    max_rows = max(50, min(int(params.get("max_rows", "250")), 250))
    include_pair_topic = str(params.get("pair_topic", "")).strip().lower() in {"1", "true", "yes", "on"}
    tokens_arg = str(params.get("tokens", "")).strip()

    tracked_tokens = _select_live_feed_tokens(tokens_arg, chain_filter, sample_size)
    api_key = _resolve_ave_api_key()

    if not api_key:
        await websocket.send_json({"type": "error", "message": "AVE_API_KEY is missing"})
        await websocket.close(code=1011)
        return

    feed = AveLiveBuySellFeed(
        tracked_tokens=tracked_tokens,
        api_key=api_key,
        max_rows=max_rows,
        include_pair_topic=include_pair_topic,
        show_raw=False,
    )

    stop_event = asyncio.Event()

    async def on_row(row: Dict[str, Any]) -> None:
        if stop_event.is_set():
            return
        try:
            await websocket.send_json({"type": "row", "row": row})
        except Exception:
            stop_event.set()

    await websocket.send_json(
        {
            "type": "ready",
            "tracked_tokens": tracked_tokens,
            "max_rows": max_rows,
            "chain_filter": chain_filter,
        }
    )

    feed_task = asyncio.create_task(feed.connect_and_stream(on_row, stop_event.is_set))

    try:
        while not stop_event.is_set():
            if feed_task.done():
                exc = feed_task.exception()
                if exc:
                    logger.exception("Live buy/sell websocket feed failed: %s", exc)
                    await websocket.send_json({"type": "error", "message": "Live feed stopped unexpectedly"})
                break

            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=20)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

            if str(message).strip().lower() == "ping":
                await websocket.send_json({"type": "pong", "ts": int(time.time())})
    finally:
        stop_event.set()
        if not feed_task.done():
            feed_task.cancel()
            try:
                await feed_task
            except asyncio.CancelledError:
                pass


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
            notify_telegram=req.notify_telegram,
            notify_web=req.notify_web,
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
        chain_norm = _normalize_chain(chain)
        alerts = alerts_manager.get_alerts_for_token(token, chain_norm)
        return {
            "token": token,
            "chain": chain_norm,
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


@app.get("/api/telegram/status")
def get_telegram_status() -> Dict[str, Any]:
    """Return Telegram bot configuration and connectivity status."""
    token = _resolve_telegram_token()
    if not token:
        return {
            "token_configured": False,
            "bot_reachable": False,
            "bot_username": "",
        }

    try:
        resp = requests.get(f"{alerts_manager.telegram_base_url}/getMe", timeout=5)
        payload = resp.json() if resp.content else {}
        bot_info = payload.get("result", {}) if isinstance(payload, dict) else {}
        return {
            "token_configured": True,
            "bot_reachable": bool(isinstance(payload, dict) and payload.get("ok")),
            "bot_username": str(bot_info.get("username") or ""),
        }
    except Exception as exc:
        return {
            "token_configured": True,
            "bot_reachable": False,
            "bot_username": "",
            "error": str(exc),
        }


@app.post("/api/telegram/test")
def send_telegram_test(req: TelegramTestRequest) -> Dict[str, Any]:
    """Send a one-off Telegram message to validate chat ID + bot token."""
    token = _resolve_telegram_token()
    if not token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured")

    default_text = (
        "✅ Telegram test from Ave Monitor\n"
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
    )

    try:
        resp = requests.post(
            f"{alerts_manager.telegram_base_url}/sendMessage",
            json={
                "chat_id": req.chat_id,
                "text": req.text or default_text,
            },
            timeout=8,
        )
        payload = resp.json() if resp.content else {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Telegram test failed: {exc}")

    if not (isinstance(payload, dict) and payload.get("ok")):
        description = "Unknown Telegram API error"
        if isinstance(payload, dict):
            description = str(payload.get("description") or description)
        raise HTTPException(status_code=400, detail=f"Telegram API error: {description}")

    return {"success": True, "chat_id": req.chat_id}


@app.post("/api/telegram/deeplink/session")
def create_telegram_deeplink_session() -> Dict[str, Any]:
    """Create one-time Telegram deep-link session for connect flow."""
    token = _resolve_telegram_token()
    if not token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured")

    bot_username = _get_telegram_bot_username()
    if not bot_username:
        raise HTTPException(status_code=400, detail="Telegram bot is not reachable")

    now_ts = int(time.time())
    expires_at = now_ts + TELEGRAM_DEEPLINK_TTL_SECONDS
    code = secrets.token_urlsafe(18)

    with telegram_deeplink_lock:
        _prune_telegram_deeplink_sessions(now_ts)
        while code in telegram_deeplink_sessions:
            code = secrets.token_urlsafe(18)

        telegram_deeplink_sessions[code] = {
            "created_at": now_ts,
            "expires_at": expires_at,
            "claimed": False,
            "chat_id": None,
            "claimed_at": None,
            "username": "",
            "first_name": "",
        }

    return {
        "success": True,
        "code": code,
        "bot_username": bot_username,
        "deep_link": f"https://t.me/{bot_username}?start=connect_{code}",
        "expires_in": TELEGRAM_DEEPLINK_TTL_SECONDS,
        "expires_at": expires_at,
    }


@app.get("/api/telegram/deeplink/session/{code}")
def get_telegram_deeplink_session(code: str) -> Dict[str, Any]:
    """Get status of a Telegram deep-link login session."""
    code_norm = str(code or "").strip()
    if not code_norm:
        raise HTTPException(status_code=400, detail="Invalid deeplink code")

    now_ts = int(time.time())
    with telegram_deeplink_lock:
        _prune_telegram_deeplink_sessions(now_ts)
        session = telegram_deeplink_sessions.get(code_norm)

    if not session:
        raise HTTPException(status_code=404, detail="Deeplink session not found")

    expires_at = int(session.get("expires_at", 0) or 0)
    expired = bool(expires_at and now_ts > expires_at)

    return {
        "code": code_norm,
        "claimed": bool(session.get("claimed")),
        "expired": expired,
        "chat_id": session.get("chat_id"),
        "username": str(session.get("username") or ""),
        "first_name": str(session.get("first_name") or ""),
        "expires_at": expires_at,
    }


@app.post("/api/telegram/deeplink/claim")
def claim_telegram_deeplink(req: TelegramDeepLinkClaimRequest) -> Dict[str, Any]:
    """Claim deep-link session from telegram bot `/start connect_<code>` callback."""
    code_norm = str(req.code or "").strip()
    if not code_norm:
        raise HTTPException(status_code=400, detail="Invalid deeplink code")

    now_ts = int(time.time())
    with telegram_deeplink_lock:
        _prune_telegram_deeplink_sessions(now_ts)
        session = telegram_deeplink_sessions.get(code_norm)
        if not session:
            raise HTTPException(status_code=404, detail="Deeplink session not found")

        expires_at = int(session.get("expires_at", 0) or 0)
        if expires_at and now_ts > expires_at:
            raise HTTPException(status_code=410, detail="Deeplink session expired")

        session["claimed"] = True
        session["chat_id"] = int(req.chat_id)
        session["claimed_at"] = now_ts
        session["username"] = str(req.username or "")
        session["first_name"] = str(req.first_name or "")

    return {"success": True, "code": code_norm, "chat_id": int(req.chat_id)}


@app.get("/api/telegram/connection")
def get_telegram_connection(chat_id: int = Query(...)) -> Dict[str, Any]:
    """Check whether a specific Telegram chat is reachable by this bot."""
    token = _resolve_telegram_token()
    if not token:
        return {
            "token_configured": False,
            "user_connected": False,
            "detail": "TELEGRAM_BOT_TOKEN is not configured",
        }

    try:
        resp = requests.get(
            f"{alerts_manager.telegram_base_url}/getChat",
            params={"chat_id": chat_id},
            timeout=8,
        )
        payload = resp.json() if resp.content else {}
    except Exception as exc:
        return {
            "token_configured": True,
            "user_connected": False,
            "detail": f"Telegram API request failed: {exc}",
        }

    ok = bool(isinstance(payload, dict) and payload.get("ok"))
    if not ok:
        detail = "Unknown Telegram API error"
        if isinstance(payload, dict):
            detail = str(payload.get("description") or detail)
        return {
            "token_configured": True,
            "user_connected": False,
            "chat_id": chat_id,
            "detail": detail,
        }

    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    chat_type = str(result.get("type") or "")
    username = str(result.get("username") or "")
    first_name = str(result.get("first_name") or "")
    last_name = str(result.get("last_name") or "")
    chat_title = str(result.get("title") or username or first_name or "")

    profile_photo_url = ""
    try:
        if chat_type == "private":
            photos_resp = requests.get(
                f"{alerts_manager.telegram_base_url}/getUserProfilePhotos",
                params={"user_id": chat_id, "limit": 1},
                timeout=8,
            )
            photos_payload = photos_resp.json() if photos_resp.content else {}
            if isinstance(photos_payload, dict) and photos_payload.get("ok"):
                photos = (photos_payload.get("result") or {}).get("photos") or []
                if photos and isinstance(photos[0], list) and photos[0]:
                    best_size = photos[0][-1] if isinstance(photos[0][-1], dict) else {}
                    profile_photo_url = _resolve_telegram_file_url(str(best_size.get("file_id") or ""))

        if not profile_photo_url:
            photo_meta = result.get("photo") if isinstance(result, dict) else None
            if isinstance(photo_meta, dict):
                profile_photo_url = _resolve_telegram_file_url(
                    str(photo_meta.get("big_file_id") or photo_meta.get("small_file_id") or "")
                )
    except Exception:
        profile_photo_url = ""

    return {
        "token_configured": True,
        "user_connected": True,
        "chat_id": chat_id,
        "chat_type": chat_type,
        "chat_display": chat_title,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "profile_photo_url": profile_photo_url,
        "detail": "Connected",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
