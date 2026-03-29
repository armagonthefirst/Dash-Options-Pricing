from __future__ import annotations

import traceback

import pandas as pd

from data.market_data import DataUnavailableError, fetch_expiries, fetch_option_chain, fetch_price_history
from data.data_processing import normalize_option_chain, normalize_price_history
from data.analytics import (
    get_live_default_expiry,
    get_live_expiry_choices,
    get_live_filtered_option_chain,
    get_live_iv_smile,
    get_live_iv_term_structure,
    get_live_price_chart_frame,
    get_live_price_history,
    get_live_screener_data,
    get_live_ticker_kpis,
    get_live_volatility_chart_frame,
)


TEST_TICKER = "SPY"


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_ok(message: str) -> None:
    print(f"[OK] {message}")


def print_fail(message: str) -> None:
    print(f"[FAIL] {message}")


def run_test(name: str, fn) -> bool:
    print_section(name)
    try:
        fn()
        return True
    except Exception as exc:
        print_fail(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def test_raw_price_history() -> None:
    raw = fetch_price_history(TEST_TICKER, period="2y", interval="1d", auto_adjust=False)
    print_ok(f"Fetched raw price history for {TEST_TICKER}")
    print(f"Shape: {raw.shape}")
    print(f"Columns: {list(raw.columns)}")
    print(raw.tail(3).to_string(index=False))


def test_normalized_price_history() -> None:
    raw = fetch_price_history(TEST_TICKER, period="2y", interval="1d", auto_adjust=False)
    history = normalize_price_history(raw)
    print_ok(f"Normalized price history for {TEST_TICKER}")
    print(f"Shape: {history.shape}")
    print(history[["Date", "Close", "ma20", "ma60", "rv20", "rv60"]].tail(5).to_string(index=False))


def test_expiries() -> None:
    expiries = fetch_expiries(TEST_TICKER)
    print_ok(f"Fetched expiries for {TEST_TICKER}")
    print(f"Count: {len(expiries)}")
    print(f"First 10 expiries: {expiries[:10]}")


def test_raw_and_normalized_chain() -> None:
    history = get_live_price_history(TEST_TICKER)
    spot = float(history["Close"].iloc[-1])

    expiries = fetch_expiries(TEST_TICKER)
    if not expiries:
        raise DataUnavailableError(f"No expiries returned for {TEST_TICKER}")

    expiry = get_live_default_expiry(TEST_TICKER)
    calls_df, puts_df = fetch_option_chain(TEST_TICKER, expiry)

    print_ok(f"Fetched raw option chain for {TEST_TICKER} at {expiry}")
    print(f"Calls shape: {calls_df.shape}")
    print(f"Puts shape:  {puts_df.shape}")

    chain = normalize_option_chain(calls_df, puts_df, spot=spot, expiry=expiry)
    print_ok("Normalized option chain")
    print(f"Shape: {chain.shape}")
    preview_cols = ["type", "strike", "expiry", "dte", "bid", "ask", "mid", "iv", "moneyness"]
    print(chain[preview_cols].head(10).to_string(index=False))


def test_live_kpis() -> None:
    kpis = get_live_ticker_kpis(TEST_TICKER)
    print_ok(f"Built live KPIs for {TEST_TICKER}")
    for key, value in kpis.items():
        print(f"{key}: {value}")


def test_live_term_structure_and_smile() -> None:
    term = get_live_iv_term_structure(TEST_TICKER)
    print_ok(f"Built IV term structure for {TEST_TICKER}")
    print(term.to_string(index=False))

    expiry = get_live_default_expiry(TEST_TICKER)
    smile = get_live_iv_smile(TEST_TICKER, expiry)
    print_ok(f"Built IV smile for {TEST_TICKER} at {expiry}")
    print(smile.head(10).to_string(index=False))


def test_live_chart_frames() -> None:
    price_frame = get_live_price_chart_frame(TEST_TICKER, display_window=252)
    print_ok("Built price chart frame")
    print(price_frame[["Date", "Open", "High", "Low", "Close", "ma20", "ma60"]].tail(5).to_string(index=False))

    history_frame, forecast_frame = get_live_volatility_chart_frame(TEST_TICKER, display_window=252)
    print_ok("Built volatility chart frames")
    print(history_frame[["Date", "rv20", "rv60"]].tail(5).to_string(index=False))
    print("\nForecast frame:")
    print(forecast_frame.head(5).to_string(index=False))


def test_live_chain_filters() -> None:
    expiry = get_live_default_expiry(TEST_TICKER)
    choices = get_live_expiry_choices(TEST_TICKER)
    print_ok("Built expiry choices")
    print(choices[:5])

    chain = get_live_filtered_option_chain(
        TEST_TICKER,
        expiry=expiry,
        option_type="both",
        moneyness_bucket="0.85-1.15",
        sort_by="strike",
    )
    print_ok(f"Built filtered live option chain for {TEST_TICKER} at {expiry}")
    print(f"Shape: {chain.shape}")
    preview_cols = ["type", "strike", "bid", "ask", "mid", "volume", "open_interest", "iv", "moneyness"]
    print(chain[preview_cols].head(15).to_string(index=False))


def test_live_screener() -> None:
    screener = get_live_screener_data()
    print_ok("Built live screener data")
    print(f"Rows: {len(screener)}")
    cols = [
        "ticker",
        "spot_price",
        "price_change_1d",
        "rv20",
        "forecast_vol_20d",
        "atm_iv_30d",
        "iv_forecast_spread",
        "default_expiry",
    ]
    available_cols = [c for c in cols if c in screener.columns]
    print(screener[available_cols].to_string(index=False))


def main() -> None:
    tests = [
        ("1. Raw price history", test_raw_price_history),
        ("2. Normalized price history", test_normalized_price_history),
        ("3. Expiry list", test_expiries),
        ("4. Raw + normalized option chain", test_raw_and_normalized_chain),
        ("5. Live KPI build", test_live_kpis),
        ("6. IV term structure + smile", test_live_term_structure_and_smile),
        ("7. Chart frames", test_live_chart_frames),
        ("8. Filtered chain + expiry choices", test_live_chain_filters),
        ("9. Full live screener", test_live_screener),
    ]

    passed = 0
    failed = 0

    print("\nStarting live data integration tests...")
    print(f"Test ticker: {TEST_TICKER}")

    for name, fn in tests:
        ok = run_test(name, fn)
        if ok:
            passed += 1
        else:
            failed += 1

    print_section("SUMMARY")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print_ok("All live data tests passed.")
    else:
        print_fail("Some live data tests failed. Scroll up to inspect the first failing stage.")


if __name__ == "__main__":
    main()
