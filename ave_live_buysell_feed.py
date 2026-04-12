#!/usr/bin/env python3
"""CLI tester for AVE Cloud live BUY/SELL swap feed via multi_tx."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import websockets

logger = logging.getLogger("ave_live_buysell_feed")


DEFAULT_TRACKED_TOKEN_POOL: List[Dict[str, str]] = [
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
]


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _short_wallet(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if len(text) <= 12:
        return text
    return f"{text[:6]}...{text[-4:]}"


def _relative_time(ts: int) -> str:
    if ts <= 0:
        return "-"
    if ts > 10_000_000_000:
        ts //= 1000
    now = int(time.time())
    diff = now - ts
    if diff <= 1:
        return "just now"
    if diff < 60:
        return f"{diff}s ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def _format_usd(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.2f}K"
    return f"${value:.2f}"


def _normalize_chain(value: object) -> str:
    return str(value or "").strip().lower()


def _normalize_address(value: object) -> str:
    return str(value or "").strip().lower()


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper()


def _normalize_tracked_tokens(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        symbol = _normalize_symbol(item.get("symbol"))
        token_address = str(item.get("token_address") or "").strip()
        chain = _normalize_chain(item.get("chain"))
        pair_address = str(item.get("pair_address") or "").strip()
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


def _load_tokens_from_json(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, list):
        return []
    rows = [x for x in payload if isinstance(x, dict)]
    return _normalize_tracked_tokens(rows)


def _parse_tokens_arg(value: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for raw in str(value or "").split(","):
        item = raw.strip()
        if not item:
            continue
        parts = [x.strip() for x in item.split(":")]
        if len(parts) < 3:
            continue
        out.append(
            {
                "symbol": parts[0],
                "token_address": parts[1],
                "chain": parts[2],
                "pair_address": parts[3] if len(parts) > 3 else "",
            }
        )
    return _normalize_tracked_tokens(out)


def _build_filter_predicate(filter_mode: str, chain_filter: str) -> Callable[[Dict[str, Any]], bool]:
    mode = str(filter_mode or "all").strip().lower()
    chain = str(chain_filter or "all").strip().lower()

    def _predicate(row: Dict[str, Any]) -> bool:
        usd = _to_float(row.get("usd"), 0.0)
        side = str(row.get("side") or "").upper()
        row_chain = str(row.get("chain") or "").lower()

        if chain != "all" and row_chain != chain:
            return False
        if mode == "usd1" and usd <= 1:
            return False
        if mode == "usd10" and usd <= 10:
            return False
        if mode == "buy" and side != "BUY":
            return False
        if mode == "sell" and side != "SELL":
            return False
        return True

    return _predicate


def _read_env_value_from_dotenv(key: str, dotenv_path: Optional[str] = None) -> str:
    path = Path(dotenv_path) if dotenv_path else Path(__file__).resolve().parent / ".env"
    if not path.exists() or not path.is_file():
        return ""

    key_prefix = f"{key}="
    try:
        with path.open("r", encoding="utf-8") as fh:
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


def _resolve_api_key(cli_key: str) -> str:
    cli_key_clean = str(cli_key or "").strip()
    if cli_key_clean:
        return cli_key_clean

    env_key = str(os.getenv("AVE_API_KEY", "")).strip()
    if env_key:
        return env_key

    return _read_env_value_from_dotenv("AVE_API_KEY")


class AveLiveBuySellFeed:
    def __init__(
        self,
        tracked_tokens: List[Dict[str, str]],
        *,
        ws_url: str = "wss://wss.ave-api.xyz",
        api_key: str = "",
        max_rows: int = 150,
        include_pair_topic: bool = False,
        show_raw: bool = False,
    ):
        rows_limit = max(50, min(250, int(max_rows or 150)))
        self.max_rows = rows_limit
        self.ws_url = ws_url
        self.api_key = api_key
        self.include_pair_topic = include_pair_topic
        self.show_raw = show_raw
        self.request_id = 0
        self.rows: List[Dict[str, Any]] = []
        self.seen_keys: set[str] = set()
        self.received_events = 0
        self.accepted_events = 0

        normalized = _normalize_tracked_tokens(tracked_tokens)
        self.tracked_tokens = {t["token_address"].lower(): t for t in normalized}
        self.tracked_tokens_list = normalized

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def resolve_tracked_token_from_event(self, tx: Dict[str, Any]) -> Optional[Dict[str, str]]:
        candidates = [
            _normalize_address(tx.get("target_token")),
            _normalize_address(tx.get("from_address")),
            _normalize_address(tx.get("to_address")),
        ]
        for cand in candidates:
            if cand and cand in self.tracked_tokens:
                return self.tracked_tokens[cand]
        return None

    def classify_side(self, tx: Dict[str, Any], token_address: str) -> Optional[str]:
        from_addr = _normalize_address(tx.get("from_address"))
        to_addr = _normalize_address(tx.get("to_address"))
        target = _normalize_address(token_address)

        if to_addr == target:
            return "BUY"
        if from_addr == target:
            return "SELL"
        return None

    def _to_row(self, tx: Dict[str, Any], tracked: Dict[str, str], side: str) -> Optional[Dict[str, Any]]:
        tx_hash = str(tx.get("transaction") or "").strip()
        if not tx_hash:
            return None

        amount_usd_raw = tx.get("amount_usd")
        if amount_usd_raw in (None, ""):
            return None
        amount_usd = _to_float(amount_usd_raw, -1.0)
        if amount_usd <= 0:
            return None

        dedupe_key = str(tx.get("id") or f"{tx_hash}:{tracked['token_address']}")

        row = {
            "id": dedupe_key,
            "wallet": str(tx.get("wallet_address") or tx.get("sender") or ""),
            "side": side,
            "symbol": tracked["symbol"],
            "usd": amount_usd,
            "chain": str(tx.get("chain") or tracked.get("chain") or ""),
            "amm": str(tx.get("amm") or ""),
            "time": _to_int(tx.get("time"), 0),
            "txHash": tx_hash,
            "swapLabel": f"{tx.get('from_symbol') or '?'} -> {tx.get('to_symbol') or '?'}",
            "tokenAddress": tracked["token_address"],
            "_dedupe": dedupe_key,
        }
        return row

    def _insert_row(self, row: Dict[str, Any]) -> bool:
        dedupe_key = str(row.get("_dedupe") or row.get("id") or "")
        if not dedupe_key:
            return False
        if dedupe_key in self.seen_keys:
            return False

        self.rows.append(row)
        self.rows.sort(key=lambda x: _to_int(x.get("time"), 0), reverse=True)
        self.rows = self.rows[: self.max_rows]
        self.seen_keys = {str(x.get("_dedupe") or "") for x in self.rows if x.get("_dedupe")}
        self.accepted_events += 1
        return True

    def _connect_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "ping_interval": 20,
            "ping_timeout": 20,
            "close_timeout": 5,
        }
        if self.api_key:
            headers = {"X-API-KEY": self.api_key}
            params = inspect.signature(websockets.connect).parameters
            if "extra_headers" in params:
                kwargs["extra_headers"] = headers
            elif "additional_headers" in params:
                kwargs["additional_headers"] = headers
        return kwargs

    async def _subscribe_all(self, ws: Any) -> None:
        for token in self.tracked_tokens_list:
            sub_multi = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": ["multi_tx", token["token_address"], token["chain"]],
                "id": self._next_id(),
            }
            await ws.send(json.dumps(sub_multi))
            logger.info(
                "Subscribed multi_tx token=%s chain=%s",
                token["token_address"],
                token["chain"],
            )

            pair_address = str(token.get("pair_address") or "").strip()
            if self.include_pair_topic and pair_address:
                sub_pair = {
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "params": ["tx", pair_address, token["chain"]],
                    "id": self._next_id(),
                }
                await ws.send(json.dumps(sub_pair))
                logger.info(
                    "Subscribed tx pair=%s chain=%s",
                    pair_address,
                    token["chain"],
                )

    async def _handle_message(
        self,
        message: str,
        on_row: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        if self.show_raw:
            logger.info("RAW %s", message)

        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            logger.debug("Skip non-JSON frame")
            return

        if msg.get("result") == "pong":
            return

        result = msg.get("result")
        if not isinstance(result, dict):
            return

        tx = result.get("tx")
        if not isinstance(tx, dict):
            return

        self.received_events += 1

        tracked = self.resolve_tracked_token_from_event(tx)
        if not tracked:
            return

        side = self.classify_side(tx, tracked["token_address"])
        if not side:
            return

        row = self._to_row(tx, tracked, side)
        if not row:
            return

        inserted = self._insert_row(row)
        if not inserted:
            return

        await on_row({k: v for k, v in row.items() if not k.startswith("_")})

    async def connect_and_stream(
        self,
        on_row: Callable[[Dict[str, Any]], Awaitable[None]],
        should_stop: Callable[[], bool],
    ) -> None:
        retry_delay = 1

        while not should_stop():
            try:
                logger.info("Connecting to AVE WSS %s", self.ws_url)
                async with websockets.connect(self.ws_url, **self._connect_kwargs()) as ws:
                    logger.info("Connected to AVE WSS")
                    await self._subscribe_all(ws)
                    retry_delay = 1

                    while not should_stop():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        await self._handle_message(raw, on_row)

            except asyncio.CancelledError:
                raise
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logger.exception("AVE feed error: %s", exc)
                if should_stop():
                    break
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)


def _render_side(side: str, use_color: bool) -> str:
    text = str(side or "").upper()
    if not use_color:
        return text
    if text == "BUY":
        return f"\033[92m{text}\033[0m"
    if text == "SELL":
        return f"\033[91m{text}\033[0m"
    return text


def _print_header() -> None:
    print("\nTime        Wallet         Side   Token  Swap                 USD       Chain      AMM")
    print("-" * 92)


def _print_row(row: Dict[str, Any], use_color: bool) -> None:
    rel = _relative_time(_to_int(row.get("time"), 0))
    wallet = _short_wallet(row.get("wallet"))
    side = _render_side(str(row.get("side") or ""), use_color)
    symbol = _normalize_symbol(row.get("symbol"))
    swap = str(row.get("swapLabel") or "-")[:20]
    usd = _format_usd(_to_float(row.get("usd"), 0.0))
    chain = str(row.get("chain") or "-")[:10]
    amm = str(row.get("amm") or "-")[:10]

    print(f"{rel:<11} {wallet:<13} {side:<6} {symbol:<6} {swap:<20} {usd:<9} {chain:<10} {amm}")


def _choose_tokens(
    token_specs: str,
    tokens_json: str,
    sample_size: int,
) -> List[Dict[str, str]]:
    from_arg = _parse_tokens_arg(token_specs)
    if from_arg:
        return from_arg

    if tokens_json:
        from_json = _load_tokens_from_json(tokens_json)
        if from_json:
            return from_json

    pool = _normalize_tracked_tokens(DEFAULT_TRACKED_TOKEN_POOL)
    if not pool:
        return []

    n = max(1, min(sample_size, len(pool)))
    if n >= len(pool):
        return pool
    return random.sample(pool, k=n)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI tester for AVE Cloud live BUY/SELL feed")
    parser.add_argument(
        "--tokens",
        default="",
        help="CSV token specs: SYMBOL:TOKEN_ADDRESS:CHAIN[:PAIR_ADDRESS]",
    )
    parser.add_argument(
        "--tokens-json",
        default="",
        help="Path JSON array of {symbol, token_address, chain, pair_address?}",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=4,
        help="Random sample size from internal token pool when tokens are not provided",
    )
    parser.add_argument(
        "--url",
        default="wss://wss.ave-api.xyz",
        help="AVE websocket endpoint",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="AVE API key (fallback: --api-key, env AVE_API_KEY, then local .env)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=150,
        help="Feed memory size, clamped to 50-250",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (0 means run until Ctrl+C)",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=30,
        help="Stop after printing N filtered rows (0 means unlimited)",
    )
    parser.add_argument(
        "--filter",
        default="all",
        choices=["all", "usd1", "usd10", "buy", "sell"],
        help="Display filter: all/usd1/usd10/buy/sell",
    )
    parser.add_argument(
        "--chain-filter",
        default="all",
        help="Chain filter for display (e.g. solana, ethereum, all)",
    )
    parser.add_argument(
        "--pair-topic",
        action="store_true",
        help="Also subscribe tx topic for pair_address when provided",
    )
    parser.add_argument("--raw", action="store_true", help="Log raw websocket frames")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser


async def run_cli(args: argparse.Namespace) -> int:
    tokens = _choose_tokens(args.tokens, args.tokens_json, args.sample_size)
    if not tokens:
        print("No tracked tokens found. Provide --tokens or --tokens-json.")
        return 2

    max_rows = max(50, min(250, int(args.max_rows or 150)))
    predicate = _build_filter_predicate(args.filter, args.chain_filter)
    use_color = (not args.no_color) and sys.stdout.isatty()

    print("Tracked tokens:")
    for token in tokens:
        pair = str(token.get("pair_address") or "").strip()
        suffix = f" pair={pair}" if pair else ""
        print(f"- {token['symbol']} {token['token_address']} chain={token['chain']}{suffix}")

    print(
        "\nStarting AVE multi_tx live feed"
        f" | filter={args.filter}"
        f" | chain_filter={args.chain_filter}"
        f" | max_rows={max_rows}"
        f" | duration={args.duration}s"
        f" | max_events={args.max_events}"
    )
    _print_header()

    api_key = _resolve_api_key(args.api_key)
    if not api_key:
        print("Warning: AVE_API_KEY not found in --api-key, process env, or .env")

    feed = AveLiveBuySellFeed(
        tracked_tokens=tokens,
        ws_url=args.url,
        api_key=api_key,
        max_rows=max_rows,
        include_pair_topic=bool(args.pair_topic),
        show_raw=bool(args.raw),
    )

    start_time = time.time()
    printed = 0

    def should_stop() -> bool:
        if args.duration > 0 and (time.time() - start_time) >= args.duration:
            return True
        if args.max_events > 0 and printed >= args.max_events:
            return True
        return False

    async def on_row(row: Dict[str, Any]) -> None:
        nonlocal printed
        if not predicate(row):
            return
        printed += 1
        _print_row(row, use_color)

    try:
        await feed.connect_and_stream(on_row, should_stop)
    except KeyboardInterrupt:
        print("\nStopped by user")

    print("\nSummary:")
    print(f"- Received tx events: {feed.received_events}")
    print(f"- Accepted unique rows: {feed.accepted_events}")
    print(f"- Printed rows (after filter): {printed}")
    print(f"- Stored rows in memory: {len(feed.rows)} / {feed.max_rows}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    return asyncio.run(run_cli(args))


if __name__ == "__main__":
    raise SystemExit(main())