#!/usr/bin/env python3
"""Real-time token chart using lightweight-charts-python.

This script loads historical candles from the local FastAPI backend and
continuously updates the latest bar from live token prices.
"""

from __future__ import annotations

import argparse
import asyncio
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests
from lightweight_charts import Chart

from services.ave_cloud_wss import AveCloudWSClient, PriceData


@dataclass
class LiveTick:
    time: datetime
    price: float
    price_change_24h: float


class AveWSSPriceFeed:
    """Background WSS feed for token price ticks."""

    def __init__(self, instrument_id: str, verbose: bool = False):
        self.instrument_id = instrument_id.strip().lower()
        self.verbose = verbose
        self._queue: queue.Queue[LiveTick] = queue.Queue(maxsize=512)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._connected = False

    def start(self) -> bool:
        if not self.instrument_id:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="ave-wss-feed")
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def pop_latest(self, timeout_seconds: float) -> Optional[LiveTick]:
        timeout = max(0.05, timeout_seconds)
        end_at = time.time() + timeout
        latest: Optional[LiveTick] = None

        while time.time() < end_at:
            remaining = max(0.01, end_at - time.time())
            try:
                latest = self._queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                break

        # Drain burst updates and keep only the newest tick.
        while not self._queue.empty():
            try:
                latest = self._queue.get_nowait()
            except queue.Empty:
                break
        return latest

    async def _on_price(self, price: PriceData) -> None:
        pair = str(price.pair or "").strip().lower()
        target_token = str(price.target_token or "").strip().lower()
        if self.instrument_id not in {pair, target_token}:
            return

        now_ts = int(time.time())
        ts = int(price.time or now_ts)
        if ts > 10_000_000_000:
            ts //= 1000

        px = float(price.uprice if price.uprice > 0 else price.last_price)
        if px <= 0:
            return

        tick = LiveTick(
            time=datetime.fromtimestamp(ts if ts > 0 else now_ts, tz=timezone.utc).replace(tzinfo=None),
            price=px,
            price_change_24h=float(price.price_change_24h),
        )

        try:
            self._queue.put_nowait(tick)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(tick)

    async def _run_async(self) -> None:
        client = AveCloudWSClient()
        self._connected = await client.connect()
        if not self._connected:
            if self.verbose:
                print("WSS connection failed; will use polling fallback.")
            return

        client.register_handler("price", self._on_price)
        subscribed = await client.subscribe_price([self.instrument_id])
        if not subscribed:
            if self.verbose:
                print("WSS subscription failed; will use polling fallback.")
            await client.disconnect()
            self._connected = False
            return

        if self.verbose:
            print(f"WSS subscribed: {self.instrument_id}")

        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(0.2)
        finally:
            await client.disconnect()
            self._connected = False

    def _run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            if self.verbose:
                print(f"WSS loop error: {exc}")


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_klines(
    base_url: str,
    token: str,
    chain: str,
    days: int,
    interval: int,
    pair_address: str,
    strict_live: bool,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    params = {
        "token": token,
        "chain": chain,
        "days": str(days),
        "interval": str(interval),
        "strict_live": "true" if strict_live else "false",
    }
    if pair_address:
        params["pair_address"] = pair_address

    response = requests.get(f"{base_url}/api/klines", params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()

    points = payload.get("points", [])
    if not points:
        raise RuntimeError("No historical candles returned from /api/klines")

    df = pd.DataFrame(points)
    required = ["time", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"Missing column '{col}' in klines response")

    df = df[required].copy()
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df.sort_values("time").reset_index(drop=True)
    return df, payload


def fetch_live_price(base_url: str, token: str, chain: str) -> Tuple[float, float]:
    response = requests.get(
        f"{base_url}/api/analyze",
        params={"token": token, "chain": chain},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    return _to_float(payload.get("price"), 0.0), _to_float(payload.get("price_change_24h"), 0.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Real-time TradingView-like chart")
    parser.add_argument("--token", default="jup", help="Token symbol")
    parser.add_argument("--chain", default="solana", help="Chain name")
    parser.add_argument("--days", type=int, default=7, help="Historical days")
    parser.add_argument("--interval", type=int, default=1, help="Candle interval in minutes")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Live update interval")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--pair-address", default="", help="Explicit pair address override")
    parser.add_argument("--allow-mock", action="store_true", help="Allow backend mock fallback")
    parser.add_argument(
        "--live-source",
        choices=("analyze", "wss"),
        default="analyze",
        help="Live update source: backend analyze polling or AVE WebSocket",
    )
    parser.add_argument("--verbose", action="store_true", help="Print live ticks")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    history_df, klines_meta = fetch_klines(
        base_url=args.base_url,
        token=args.token,
        chain=args.chain,
        days=args.days,
        interval=args.interval,
        pair_address=args.pair_address,
        strict_live=not args.allow_mock,
    )

    resolved_pair = str(klines_meta.get("pair_address") or args.pair_address or "")
    token_address = str(klines_meta.get("token_address") or "").strip()
    token_id = str(klines_meta.get("token_id") or "").strip()
    if not token_id and token_address:
        token_id = f"{token_address}-{args.chain.lower()}"

    chart = Chart(toolbox=True)
    chart.layout(
        background_color="#0a0a0a",
        text_color="#dce8ff",
        font_size=13,
        font_family="Space Grotesk",
    )
    chart.candle_style(
        up_color="#3ef5b5",
        down_color="#ff5f84",
        border_up_color="#3ef5b5",
        border_down_color="#ff5f84",
        wick_up_color="#3ef5b5",
        wick_down_color="#ff5f84",
    )
    chart.volume_config(up_color="rgba(62,245,181,0.35)", down_color="rgba(255,95,132,0.35)")
    chart.legend(visible=True)
    chart.watermark(f"{args.token.upper()} · {args.chain}", color="rgba(120,160,255,0.35)")
    chart.set(history_df)

    print(
        f"Chart started for {args.token.upper()}-{args.chain} "
        f"(pair: {resolved_pair or 'auto'}, token_id: {token_id or 'n/a'}, interval: {args.interval}m, source: {args.live_source})"
    )

    chart.show()

    feed: Optional[AveWSSPriceFeed] = None
    if args.live_source == "wss":
        instrument_id = token_id
        if not instrument_id and resolved_pair:
            chain_suffix = f"-{args.chain.lower()}"
            instrument_id = resolved_pair if resolved_pair.lower().endswith(chain_suffix) else f"{resolved_pair}{chain_suffix}"

        if not instrument_id:
            print("WSS source requested but no token-id/pair-id resolved; falling back to analyze polling.")
        else:
            feed = AveWSSPriceFeed(instrument_id, verbose=args.verbose)
            feed.start()

    try:
        while True:
            if feed is not None:
                live_tick = feed.pop_latest(timeout_seconds=max(args.poll_seconds, 0.3))
                if live_tick is not None:
                    chart.update_from_tick(pd.Series({"time": live_tick.time, "price": live_tick.price}))
                    if args.verbose:
                        print(f"[wss] price={live_tick.price:.8f} | 24h={live_tick.price_change_24h:+.2f}%")
                    continue

            price, price_change_24h = fetch_live_price(args.base_url, args.token, args.chain)
            chart.update_from_tick(
                pd.Series(
                    {
                        "time": datetime.now(timezone.utc).replace(tzinfo=None),
                        "price": price,
                    }
                )
            )

            if args.verbose:
                source = "analyze-fallback" if feed is not None else "analyze"
                print(f"[{source}] price={price:.8f} | 24h={price_change_24h:+.2f}%")

            time.sleep(max(args.poll_seconds, 0.3))
    except KeyboardInterrupt:
        print("Stopping chart...")
        return 0
    finally:
        if feed is not None:
            feed.stop()


if __name__ == "__main__":
    raise SystemExit(main())