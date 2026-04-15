"""
Test script: check if yfinance returns IV values off-market hours.

Run this any time — during market hours OR after close — and compare results.
"""

import yfinance as yf
from datetime import datetime, timezone
import sys

TICKERS = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "AMD"]

# How many near-ATM contracts to sample per ticker
SAMPLE_SIZE = 5


def is_market_open() -> bool:
    """Rough check — NYSE hours Mon-Fri 14:30-21:00 UTC."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    return 14 <= now.hour < 21


def check_ticker(ticker: str) -> dict:
    t = yf.Ticker(ticker)

    # Get current spot price
    try:
        hist = t.history(period="1d", interval="1m")
        spot = float(hist["Close"].iloc[-1]) if not hist.empty else None
    except Exception as e:
        return {"ticker": ticker, "error": f"Price fetch failed: {e}"}

    # Get nearest expiry
    try:
        expiries = t.options
        if not expiries:
            return {"ticker": ticker, "spot": spot, "error": "No expiries returned"}
        nearest_expiry = expiries[0]
    except Exception as e:
        return {"ticker": ticker, "spot": spot, "error": f"Expiry fetch failed: {e}"}

    # Fetch option chain for nearest expiry
    try:
        chain = t.option_chain(nearest_expiry)
        calls = chain.calls
    except Exception as e:
        return {"ticker": ticker, "spot": spot, "expiry": nearest_expiry, "error": f"Chain fetch failed: {e}"}

    # Filter near-ATM contracts
    if spot:
        calls = calls[
            (calls["strike"] >= spot * 0.95) &
            (calls["strike"] <= spot * 1.05)
        ]

    sample = calls.head(SAMPLE_SIZE)[["strike", "impliedVolatility", "lastPrice", "volume"]].copy()
    sample["impliedVolatility"] = sample["impliedVolatility"].round(4)

    iv_values = sample["impliedVolatility"].tolist()
    non_zero = [v for v in iv_values if v and v > 0]

    return {
        "ticker": ticker,
        "spot": round(spot, 2) if spot else None,
        "expiry": nearest_expiry,
        "contracts_sampled": len(sample),
        "iv_non_zero": len(non_zero),
        "iv_zero_or_nan": len(iv_values) - len(non_zero),
        "sample": sample.to_dict("records"),
    }


def main():
    now = datetime.now()
    market_status = "OPEN" if is_market_open() else "CLOSED"

    print(f"\n{'='*60}")
    print(f"  yfinance IV Test")
    print(f"  Time: {now.strftime('%Y-%m-%d %H:%M:%S')} local")
    print(f"  Market: {market_status}")
    print(f"{'='*60}\n")

    tickers = sys.argv[1:] if len(sys.argv) > 1 else TICKERS

    summary_rows = []

    for ticker in tickers:
        print(f"Checking {ticker}...", end=" ", flush=True)
        result = check_ticker(ticker)

        if "error" in result:
            print(f"ERROR — {result['error']}")
            summary_rows.append((ticker, "ERROR", result["error"]))
            continue

        iv_status = "OK" if result["iv_non_zero"] > 0 else "ALL ZERO/NaN"
        print(f"done  ({result['iv_non_zero']}/{result['contracts_sampled']} contracts have IV)")

        # Print sample contracts
        for row in result["sample"]:
            iv = row["impliedVolatility"]
            iv_str = f"{iv:.2%}" if iv and iv > 0 else "ZERO/NaN"
            print(f"    strike={row['strike']:>8}  IV={iv_str:<12}  lastPrice={row['lastPrice']}  vol={row['volume']}")

        print()
        summary_rows.append((ticker, iv_status, f"{result['iv_non_zero']}/{result['contracts_sampled']} contracts have IV  |  expiry={result['expiry']}"))

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for ticker, status, detail in summary_rows:
        print(f"  {ticker:<6}  [{status}]  {detail}")
    print()


if __name__ == "__main__":
    main()
