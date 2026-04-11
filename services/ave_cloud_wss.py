#!/usr/bin/env python3
"""
AVE Cloud WebSocket Service
Handles real-time kline, price, and transaction streams from wss://wss.ave-api.xyz
"""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass
import websockets

logger = logging.getLogger(__name__)

# AVE Cloud endpoints
WSS_ENDPOINT = "wss://wss.ave-api.xyz"
REST_ENDPOINT = "https://prod.ave-api.com"

# Alternative REST endpoint
REST_ENDPOINT_ALT = "https://data.ave-api.xyz"


@dataclass
class KlineData:
    """Candlestick data point"""
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    token: str
    chain: str

    def to_dict(self):
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass
class PriceData:
    """Price update data"""
    pair: str
    target_token: str
    uprice: float  # USD price
    last_price: float
    price_change: float
    price_change_24h: float
    chain: str
    time: int

    def to_dict(self):
        return {
            "pair": self.pair,
            "target_token": self.target_token,
            "uprice": self.uprice,
            "last_price": self.last_price,
            "price_change": self.price_change,
            "price_change_24h": self.price_change_24h,
            "chain": self.chain,
            "time": self.time,
        }


class AveCloudWSClient:
    """
    AVE Cloud WebSocket Client
    Manages subscriptions to klines, prices, and transactions
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.ws = None
        self.subscriptions: Dict[str, Dict] = {}  # Track active subscriptions
        self.message_handlers: Dict[str, Callable] = {}  # topic -> callback
        self.request_id = 0
        self.ping_interval = 30  # seconds
        self.is_connected = False

    async def connect(self) -> bool:
        """Connect to AVE Cloud WebSocket"""
        try:
            logger.info(f"Connecting to {WSS_ENDPOINT}...")
            self.ws = await websockets.connect(WSS_ENDPOINT)
            self.is_connected = True
            logger.info("✅ Connected to AVE Cloud WSS")

            # Start ping loop to keep connection alive
            asyncio.create_task(self._ping_loop())

            # Start message listener
            asyncio.create_task(self._listen())

            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("Disconnected from AVE Cloud WSS")

    def register_handler(self, topic: str, callback: Callable):
        """Register callback for message topic"""
        self.message_handlers[topic] = callback
        logger.info(f"Registered handler for topic: {topic}")

    async def subscribe_kline(
        self,
        pair_address: str,
        interval: str = "k1",  # k1, k5, k15, k30, k60, k120, k240, k1440, k10080
        chain: str = "solana",
    ) -> bool:
        """
        Subscribe to kline (candlestick) updates for a pair
        
        Args:
            pair_address: Contract address of the pair
            interval: Time interval (k1=1min, k5=5min, etc.) or s1 for 1-second
            chain: Blockchain (solana, ethereum, bsc, etc.)
        
        Returns:
            True if subscription successful
        """
        if not self.is_connected:
            logger.warning("Not connected to WSS")
            return False

        try:
            self.request_id += 1
            sub_id = f"kline-{pair_address}-{interval}-{chain}"

            request = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": ["kline", pair_address, interval, chain],
                "id": self.request_id,
            }

            await self.ws.send(json.dumps(request))
            self.subscriptions[sub_id] = {
                "topic": "kline",
                "pair": pair_address,
                "interval": interval,
                "chain": chain,
            }

            logger.info(f"✅ Subscribed to kline: {sub_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Kline subscription failed: {e}")
            return False

    async def subscribe_price(self, pair_ids: List[str]) -> bool:
        """
        Subscribe to price updates for multiple pairs/tokens
        
        Args:
            pair_ids: List of pair/token IDs in format "{address}-{chain}"
                     e.g., ["Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE-solana"]
        
        Returns:
            True if subscription successful
        """
        if not self.is_connected:
            logger.warning("Not connected to WSS")
            return False

        try:
            self.request_id += 1

            request = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": ["price", pair_ids],
                "id": self.request_id,
            }

            await self.ws.send(json.dumps(request))
            self.subscriptions["price-" + "-".join(pair_ids[:2])] = {
                "topic": "price",
                "pairs": pair_ids,
            }

            logger.info(f"✅ Subscribed to prices: {len(pair_ids)} pairs")
            return True

        except Exception as e:
            logger.error(f"❌ Price subscription failed: {e}")
            return False

    async def subscribe_tx(
        self, pair_address: str, chain: str = "solana"
    ) -> bool:
        """
        Subscribe to transaction stream for a pair
        
        Args:
            pair_address: Pair address
            chain: Blockchain name
        
        Returns:
            True if subscription successful
        """
        if not self.is_connected:
            logger.warning("Not connected to WSS")
            return False

        try:
            self.request_id += 1
            sub_id = f"tx-{pair_address}-{chain}"

            request = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": ["tx", pair_address, chain],
                "id": self.request_id,
            }

            await self.ws.send(json.dumps(request))
            self.subscriptions[sub_id] = {
                "topic": "tx",
                "pair": pair_address,
                "chain": chain,
            }

            logger.info(f"✅ Subscribed to tx: {sub_id}")
            return True

        except Exception as e:
            logger.error(f"❌ TX subscription failed: {e}")
            return False

    async def _ping_loop(self):
        """Send ping to keep connection alive"""
        while self.is_connected:
            try:
                await asyncio.sleep(self.ping_interval)

                self.request_id += 1
                ping_msg = {
                    "jsonrpc": "2.0",
                    "method": "ping",
                    "id": self.request_id,
                }

                await self.ws.send(json.dumps(ping_msg))
                logger.debug("📍 Ping sent")

            except Exception as e:
                logger.warning(f"Ping error: {e}")
                break

    async def _listen(self):
        """Listen for incoming messages"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    logger.info(f"RAW WS: {data}")
                    if data.get("result") == "pong":
                        logger.debug("✅ Pong received")
                        continue

                    result = data.get("result")
                    if not isinstance(result, dict):
                        logger.debug(f"Skip non-dict result: {data}")
                        continue

                    topic = result.get("topic", "")

                    # Route to appropriate handler
                    if topic == "kline" and "kline" in result:
                        await self._handle_kline(result)
                    elif topic == "price" and "prices" in result:
                        await self._handle_price(result)
                    elif topic == "tx" and "tx" in result:
                        await self._handle_tx(result)
                    else:
                        logger.debug(f"Unhandled message: {data}")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message: {message[:100]}")
                except Exception as e:
                    logger.error(f"Message handling error: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Listen error: {e}")
            self.is_connected = False

    async def _handle_kline(self, result: Dict):
        """Process kline data and call registered handler"""
        try:
            logger.info(f"KLINE RESULT: {result}")
            kline_data = result.get("kline", {})
            pair_id = result.get("id", "")
            interval = result.get("interval", "k1")

            # Use USD prices
            usd_data = kline_data.get("usd", {})

            if usd_data:
                kline = KlineData(
                    time=int(usd_data.get("time", 0)),
                    open=float(usd_data.get("open", 0)),
                    high=float(usd_data.get("high", 0)),
                    low=float(usd_data.get("low", 0)),
                    close=float(usd_data.get("close", 0)),
                    volume=float(usd_data.get("volume", 0)),
                    token=pair_id.split("-")[0],
                    chain=pair_id.split("-")[1] if "-" in pair_id else "unknown",
                )

                # Call handler if registered
                if "kline" in self.message_handlers:
                    await self.message_handlers["kline"](kline)

        except Exception as e:
            logger.error(f"Kline handling error: {e}")

    async def _handle_price(self, result: Dict):
        """Process price data and call registered handler"""
        try:
            prices = result.get("prices", [])

            for price_data in prices:
                price = PriceData(
                    pair=price_data.get("pair", ""),
                    target_token=price_data.get("target_token", ""),
                    uprice=float(price_data.get("uprice", 0)),
                    last_price=float(price_data.get("last_price", 0)),
                    price_change=float(price_data.get("price_change", 0)),
                    price_change_24h=float(price_data.get("price_change_24h", 0)),
                    chain=price_data.get("chain", ""),
                    time=int(price_data.get("time", 0)),
                )

                if "price" in self.message_handlers:
                    await self.message_handlers["price"](price)

        except Exception as e:
            logger.error(f"Price handling error: {e}")

    async def _handle_tx(self, result: Dict):
        """Process transaction data and call registered handler"""
        try:
            tx = result.get("tx", {})

            if "tx" in self.message_handlers:
                await self.message_handlers["tx"](tx)

        except Exception as e:
            logger.error(f"TX handling error: {e}")


# Global instance
_client: Optional[AveCloudWSClient] = None


def get_client(api_key: str = "") -> AveCloudWSClient:
    """Get or create global WebSocket client"""
    global _client
    if _client is None:
        _client = AveCloudWSClient(api_key)
    return _client


async def test_connection():
    """Test WebSocket connection"""
    client = get_client()
    connected = await client.connect()

    if connected:
        # Subscribe to BONK kline
        await client.subscribe_kline(
            pair_address="Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
            interval="k1",
            chain="solana",
        )

        # Listen for 10 seconds
        await asyncio.sleep(10)
        await client.disconnect()
    else:
        print("Connection failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_connection())
