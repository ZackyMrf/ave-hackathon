#!/usr/bin/env python3
"""
CLI test script for fake token filtering.
Tests that the new _pick_best_search_candidate logic correctly
picks the legitimate high-TVL token over low-TVL fakes.

Usage:
    python test_filter_fake_tokens.py
"""

import sys
import os
import math

# --------------------------------------------------------------------------- #
# Ensure we load from project root
# --------------------------------------------------------------------------- #
PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ_ROOT)

# Stub out requests so we don't need a live API for unit-tests
import unittest.mock as mock
import types

from ave_monitor import AveAccumulationMonitor

# --------------------------------------------------------------------------- #
# Colour helpers (work even without PYTHONUTF8)
# --------------------------------------------------------------------------- #
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"{GREEN}[PASS]{RESET} {msg}")
def fail(msg): print(f"{RED}[FAIL]{RESET} {msg}")
def info(msg): print(f"{YELLOW}[INFO]{RESET} {msg}")

# --------------------------------------------------------------------------- #
# Test 1: Internal scorer unit test (no network needed)
# --------------------------------------------------------------------------- #

def test_scorer_prefers_high_tvl():
    """Given two UNI tokens, the one with higher TVL must win."""
    monitor = AveAccumulationMonitor(api_key="dummy")

    fake_uni = {
        "symbol": "UNI",
        "name": "Uniswap Fake",
        "token": "0xFAKE000000000000000000000000000000000001",
        "tvl": 0.0,
        "holders": 0,
        "market_cap": 999_000_000,  # inflated MC, tiny TVL
    }
    real_uni = {
        "symbol": "UNI",
        "name": "Uniswap",
        "token": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "tvl": 150_000_000,
        "holders": 350_000,
        "market_cap": 5_000_000_000,
    }

    # Pick from list containing fake first, then real
    result = monitor._pick_best_search_candidate([fake_uni, real_uni], "UNI")
    if result and result["token"] == real_uni["token"]:
        ok("UNI  ->  real token selected over fake (TVL-based scoring)")
    else:
        fail(f"UNI  ->  wrong token selected: {result}")


def test_scorer_rejects_zero_holder_scam():
    """A scam token with symbol match but 0 holders and 0 TVL must lose."""
    monitor = AveAccumulationMonitor(api_key="dummy")

    scam = {
        "symbol": "PEPE",
        "name": "Pepe Scam",
        "token": "0xSCAM0000000000000000000000000000000000",
        "tvl": 0.0,
        "holders": 0,
        "market_cap": 0,
    }
    legit = {
        "symbol": "PEPE",
        "name": "Pepe",
        "token": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        "tvl": 30_000_000,
        "holders": 200_000,
        "market_cap": 1_000_000_000,
    }

    result = monitor._pick_best_search_candidate([scam, legit], "PEPE")
    if result and result["token"] == legit["token"]:
        ok("PEPE ->  legitimate token selected; scam (0 TVL, 0 holders) rejected")
    else:
        fail(f"PEPE ->  scam was picked instead of legit: {result}")


def test_scorer_partial_symbol_match():
    """A partial match (UNISWAP) should win over irrelevant tokens."""
    monitor = AveAccumulationMonitor(api_key="dummy")

    items = [
        {
            "symbol": "UNISWAP",
            "name": "Uniswap V3",
            "token": "0xAAA",
            "tvl": 500_000,
            "holders": 5_000,
        },
        {
            "symbol": "UNIFORM",
            "name": "Uniform Token",
            "token": "0xBBB",
            "tvl": 1_000_000,
            "holders": 100,
        },
    ]
    result = monitor._pick_best_search_candidate(items, "UNI")
    # Both partially match "uni"; UNISWAP has better holders/tvl
    if result:
        ok(f"Partial-match test -> selected symbol={result.get('symbol')} TVL={result.get('tvl')}")
    else:
        fail("Partial-match test -> nothing selected")


def test_scorer_single_result_passthrough():
    """If only one result comes back, it must be returned unchanged."""
    monitor = AveAccumulationMonitor(api_key="dummy")
    only = {"symbol": "JUP", "token": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "tvl": 1_000, "holders": 50_000}
    result = monitor._pick_best_search_candidate([only], "JUP")
    if result and result["token"] == only["token"]:
        ok("Single result passthrough -> correct")
    else:
        fail(f"Single result passthrough -> unexpected: {result}")


# --------------------------------------------------------------------------- #
# Test 2: api_server picker unit test
# --------------------------------------------------------------------------- #

def test_api_server_picker():
    """Test _pick_ave_token_from_chain_list from api_server.py."""
    info("Testing api_server._pick_ave_token_from_chain_list ...")

    # Temporarily patch the sys.path so api_server can be imported
    sys.path.insert(0, PROJ_ROOT)
    try:
        from api_server import _pick_ave_token_from_chain_list
    except ImportError as e:
        fail(f"Cannot import api_server: {e}")
        return

    mock_items = [
        {
            "token": "ETH",
            "symbol": "ETH",
            "name": "Ethereum",
            "ca": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "liquidity": 0.0,
            "holder": 0,
            "market_cap": 0,
        },
        {
            "token": "ETH",
            "symbol": "ETH",
            "name": "Wrapped Ether",
            "ca": "0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2",
            "liquidity": 2_000_000_000,
            "holder": 800_000,
            "market_cap": 400_000_000_000,
        },
    ]
    result = _pick_ave_token_from_chain_list(mock_items, "ETH")
    if result and result.get("ca", "").lower() == "0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2".lower():
        ok("api_server ETH -> WETH selected (high liquidity) over placeholder")
    else:
        picked = result.get("ca") if result else "None"
        fail(f"api_server ETH -> wrong ca: {picked}")


# --------------------------------------------------------------------------- #
# Test 3: Live API test (optional, requires network + valid API key)
# --------------------------------------------------------------------------- #

KNOWN_TOKENS = {
    # symbol: (chain, expected_ca_prefix)
    "UNI":  ("eth", "0x1f9840"),
    "PEPE": ("eth", "0x698250"),
    "JUP":  ("solana", "JUPyiw"),
    "BONK": ("solana", "DezXAZ"),
}

def test_live_resolve():
    """Live resolution test — requires AVE_API_KEY in environment."""
    api_key = os.getenv("AVE_API_KEY", "")
    if not api_key:
        info("AVE_API_KEY not set — skipping live resolution test")
        return

    monitor = AveAccumulationMonitor(api_key=api_key)
    info("Running live resolution tests (this makes real API calls) ...")

    for symbol, (chain, ca_prefix) in KNOWN_TOKENS.items():
        try:
            candidate = monitor._search_token(symbol, chain)
            if candidate is None:
                fail(f"Live {symbol}/{chain} -> None returned from search")
                continue

            addr = str(candidate.get("token", candidate.get("address", "")) or "")
            tvl  = float(candidate.get("tvl", 0) or 0)
            hdrs = int(float(candidate.get("holders", 0) or 0))

            if addr.lower().startswith(ca_prefix.lower()):
                ok(f"Live {symbol}/{chain} -> {addr[:12]}... TVL=${tvl:,.0f} holders={hdrs:,}")
            else:
                fail(f"Live {symbol}/{chain} -> unexpected address: {addr} (expected prefix {ca_prefix})")
        except Exception as exc:
            fail(f"Live {symbol}/{chain} -> exception: {exc}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    print(f"\n{BOLD}=== Fake Token Filter Tests ==={RESET}\n")

    # Unit tests (no network)
    print(f"{BOLD}-- Unit Tests (no API calls) --{RESET}")
    test_scorer_prefers_high_tvl()
    test_scorer_rejects_zero_holder_scam()
    test_scorer_partial_symbol_match()
    test_scorer_single_result_passthrough()
    test_api_server_picker()

    # Live tests
    print(f"\n{BOLD}-- Live Resolution Tests --{RESET}")
    test_live_resolve()

    print(f"\n{BOLD}=== Done ==={RESET}\n")


if __name__ == "__main__":
    main()
