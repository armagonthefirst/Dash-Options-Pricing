from __future__ import annotations

import os
import requests
from datetime import date, timedelta
from typing import Tuple

import pandas as pd
import yfinance as yf

from data.cache import ttl_cache


DEFAULT_HISTORY_PERIOD = "2y"
DEFAULT_HISTORY_INTERVAL = "1d"

ALPACA_DATA_BASE = "https://data.alpaca.markets"
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")


class DataUnavailableError(RuntimeError):
    """Raised when live market data cannot be fetched or is unusable."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }


def _period_to_start_date(period: str) -> str:
    """Convert a yfinance-style period string to an ISO start date for Alpaca."""
    today = date.today()
    if period.endswith("y"):
        return (today - timedelta(days=int(period[:-1]) * 365)).isoformat()
    elif period.endswith("d"):
        return (today - timedelta(days=int(period[:-1]))).isoformat()
    elif period.endswith("mo"):
        return (today - timedelta(days=int(period[:-2]) * 30)).isoformat()
    return (today - timedelta(days=365)).isoformat()


def _parse_occ_symbol(symbol: str, ticker: str) -> dict | None:
    """
    Parse an OCC option symbol into its components.

    Format: {TICKER}{YYMMDD}{C/P}{8-digit-strike}
    Example: SPY260422C00694000 -> expiry=2026-04-22, type=call, strike=694.0
    """
    try:
        rest = symbol[len(ticker):]
        year  = 2000 + int(rest[0:2])
        month = int(rest[2:4])
        day   = int(rest[4:6])
        expiry = f"{year:04d}-{month:02d}-{day:02d}"
        option_type = "call" if rest[6].upper() == "C" else "put"
        strike = int(rest[7:15]) / 1000.0
        return {"expiry": expiry, "type": option_type, "strike": strike}
    except Exception:
        return None


def _normalize_ticker(ticker: str) -> str:
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string.")
    return ticker.strip().upper()


def _strip_timezone(series: pd.Series) -> pd.Series:
    series = pd.to_datetime(series, errors="coerce")
    try:
        if getattr(series.dt, "tz", None) is not None:
            return series.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return series


def _ensure_date_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.reset_index().copy()

    if "Datetime" in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    elif "index" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"index": "Date"})

    if "Date" in out.columns:
        out["Date"] = _strip_timezone(out["Date"])
        out = out.sort_values("Date").drop_duplicates(subset="Date", keep="last")

    return out.reset_index(drop=True)


def _validate_history_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise DataUnavailableError(f"No price history returned for {ticker}.")

    required_cols = {"Open", "High", "Low", "Close", "Volume"}
    missing = required_cols.difference(df.columns)
    if missing:
        raise DataUnavailableError(
            f"Price history for {ticker} is missing required columns: {sorted(missing)}"
        )

    usable = df.dropna(subset=["Open", "High", "Low", "Close"])
    if usable.empty:
        raise DataUnavailableError(f"Price history for {ticker} has no usable OHLC rows.")

    return usable.reset_index(drop=True)


def _empty_option_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "contractSymbol",
            "lastTradeDate",
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "change",
            "percentChange",
            "volume",
            "openInterest",
            "impliedVolatility",
            "inTheMoney",
            "contractSize",
            "currency",
            "expiry",
            "optionType",
        ]
    )


def _normalize_option_frame(
    df: pd.DataFrame,
    expiry: str,
    option_type: str,
) -> pd.DataFrame:
    if df is None or df.empty:
        empty = _empty_option_frame()
        empty["expiry"] = expiry
        empty["optionType"] = option_type
        return empty

    out = df.copy()

    if "lastTradeDate" in out.columns:
        out["lastTradeDate"] = _strip_timezone(out["lastTradeDate"])

    out["expiry"] = expiry
    out["optionType"] = option_type

    if "strike" in out.columns:
        out["strike"] = pd.to_numeric(out["strike"], errors="coerce")
    if "bid" in out.columns:
        out["bid"] = pd.to_numeric(out["bid"], errors="coerce")
    if "ask" in out.columns:
        out["ask"] = pd.to_numeric(out["ask"], errors="coerce")
    if "impliedVolatility" in out.columns:
        out["impliedVolatility"] = pd.to_numeric(out["impliedVolatility"], errors="coerce")

    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Price history — Alpaca stock bars
# ---------------------------------------------------------------------------

@ttl_cache(maxsize=128)
def _fetch_price_history_cached(
    ticker: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = DEFAULT_HISTORY_INTERVAL,
    auto_adjust: bool = False,
) -> pd.DataFrame:
    ticker = _normalize_ticker(ticker)

    try:
        url = f"{ALPACA_DATA_BASE}/v2/stocks/{ticker}/bars"
        params = {
            "timeframe": "1Day",
            "start": _period_to_start_date(period),
            "end": date.today().isoformat(),
            "limit": 1000,
            "feed": "iex",
        }
        bars = []
        while True:
            resp = requests.get(url, params=params, headers=_alpaca_headers(), timeout=15)
            if resp.status_code != 200:
                raise DataUnavailableError(
                    f"Alpaca bars request failed for {ticker}: {resp.status_code} {resp.text}"
                )
            data = resp.json()
            bars.extend(data.get("bars") or [])
            token = data.get("next_page_token")
            if not token:
                break
            params["page_token"] = token

        if not bars:
            raise DataUnavailableError(f"No price bars returned from Alpaca for {ticker}.")

        raw = pd.DataFrame(bars).rename(columns={
            "t": "Date", "o": "Open", "h": "High",
            "l": "Low",  "c": "Close", "v": "Volume",
        })
        raw["Date"] = pd.to_datetime(raw["Date"], utc=True).dt.tz_localize(None)
        raw = raw[["Date", "Open", "High", "Low", "Close", "Volume"]]

    except DataUnavailableError:
        raise
    except Exception as exc:
        raise DataUnavailableError(
            f"Failed to fetch price history for {ticker}: {exc}"
        ) from exc

    history = _ensure_date_column(raw)
    history = _validate_history_frame(history, ticker)
    return history


def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = DEFAULT_HISTORY_INTERVAL,
    auto_adjust: bool = False,
) -> pd.DataFrame:
    """Return OHLCV price history from Alpaca, lightly standardized."""
    return _fetch_price_history_cached(
        ticker=ticker,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
    ).copy()


# ---------------------------------------------------------------------------
# Option expiry dates — Alpaca snapshots (narrow ATM window, dates only)
# ---------------------------------------------------------------------------

@ttl_cache(maxsize=128)
def _fetch_expiries_cached(ticker: str) -> tuple[str, ...]:
    ticker = _normalize_ticker(ticker)

    # Use cached price history (guaranteed hit by analytics layer) to get spot
    # so we can narrow the strike window and minimise data returned.
    try:
        history = _fetch_price_history_cached(ticker, "1y", "1d", False)
        spot = float(pd.to_numeric(history["Close"], errors="coerce").dropna().iloc[-1])
        strike_lower = round(spot * 0.98)
        strike_upper = round(spot * 1.02)
    except Exception:
        strike_lower, strike_upper = 1, 999999

    try:
        url = f"{ALPACA_DATA_BASE}/v1beta1/options/snapshots/{ticker}"
        params = {
            "expiration_date_gte": (date.today() + timedelta(days=1)).isoformat(),
            "expiration_date_lte": (date.today() + timedelta(days=180)).isoformat(),
            "strike_price_gte": strike_lower,
            "strike_price_lte": strike_upper,
            "limit": 1000,
        }
        expiry_dates: set[str] = set()
        while True:
            resp = requests.get(url, params=params, headers=_alpaca_headers(), timeout=15)
            if resp.status_code != 200:
                raise DataUnavailableError(
                    f"Alpaca snapshots request failed for {ticker}: {resp.status_code} {resp.text}"
                )
            data = resp.json()
            for symbol in (data.get("snapshots") or {}):
                parsed = _parse_occ_symbol(symbol, ticker)
                if parsed:
                    expiry_dates.add(parsed["expiry"])
            token = data.get("next_page_token")
            if not token:
                break
            params["page_token"] = token

    except DataUnavailableError:
        raise
    except Exception as exc:
        raise DataUnavailableError(
            f"Failed to fetch option expiries for {ticker}: {exc}"
        ) from exc

    if not expiry_dates:
        raise DataUnavailableError(f"No option expiries returned for {ticker}.")

    return tuple(sorted(expiry_dates))


def fetch_expiries(ticker: str) -> list[str]:
    return list(_fetch_expiries_cached(ticker))


# ---------------------------------------------------------------------------
# Option chain — Alpaca snapshots (single expiry, ±15% strike bounds)
# ---------------------------------------------------------------------------

@ttl_cache(maxsize=256)
def _fetch_option_chain_cached(ticker: str, expiry: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    ticker = _normalize_ticker(ticker)
    expiry = str(expiry)

    available_expiries = _fetch_expiries_cached(ticker)
    if expiry not in available_expiries:
        raise DataUnavailableError(
            f"Expiry {expiry} is not available for {ticker}. "
            f"Available expiries: {list(available_expiries)}"
        )

    try:
        history = _fetch_price_history_cached(ticker, "1y", "1d", False)
        spot = float(pd.to_numeric(history["Close"], errors="coerce").dropna().iloc[-1])
        strike_lower = int(spot * 0.85)
        strike_upper = int(spot * 1.15)
    except Exception:
        strike_lower, strike_upper = 0, 999999

    try:
        url = f"{ALPACA_DATA_BASE}/v1beta1/options/snapshots/{ticker}"
        params = {
            "expiration_date": expiry,
            "strike_price_gte": strike_lower,
            "strike_price_lte": strike_upper,
            "limit": 1000,
        }
        contracts: dict = {}
        while True:
            resp = requests.get(url, params=params, headers=_alpaca_headers(), timeout=15)
            if resp.status_code != 200:
                raise DataUnavailableError(
                    f"Alpaca chain request failed for {ticker} at {expiry}: "
                    f"{resp.status_code} {resp.text}"
                )
            data = resp.json()
            contracts.update(data.get("snapshots") or {})
            token = data.get("next_page_token")
            if not token:
                break
            params["page_token"] = token

    except DataUnavailableError:
        raise
    except Exception as exc:
        raise DataUnavailableError(
            f"Failed to fetch option chain for {ticker} at {expiry}: {exc}"
        ) from exc

    rows = []
    for symbol, snap in contracts.items():
        parsed = _parse_occ_symbol(symbol, ticker)
        if not parsed or parsed["expiry"] != expiry:
            continue
        quote = snap.get("latestQuote") or {}
        trade = snap.get("latestTrade") or {}
        daily = snap.get("dailyBar") or {}
        rows.append({
            "contractSymbol":    symbol,
            "strike":            parsed["strike"],
            "lastPrice":         float(trade.get("p") or 0.0),
            "bid":               float(quote.get("bp") or 0.0),
            "ask":               float(quote.get("ap") or 0.0),
            "volume":            int(daily.get("v") or 0),
            "openInterest":      int(snap.get("openInterest") or 0),
            "impliedVolatility": float(snap.get("impliedVolatility") or 0.0),
            "lastTradeDate":     trade.get("t"),
        })

    if not rows:
        raise DataUnavailableError(
            f"No option contracts returned for {ticker} at {expiry}."
        )

    df = pd.DataFrame(rows)

    # Split into calls and puts by reading the C/P character from the OCC symbol
    type_char_pos = len(ticker) + 6
    calls = _normalize_option_frame(
        df[df["contractSymbol"].str[type_char_pos] == "C"].copy(), expiry, "call"
    )
    puts = _normalize_option_frame(
        df[df["contractSymbol"].str[type_char_pos] == "P"].copy(), expiry, "put"
    )

    if calls.empty and puts.empty:
        raise DataUnavailableError(
            f"No option chain rows returned for {ticker} at {expiry}."
        )

    return calls, puts


def fetch_option_chain(ticker: str, expiry: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return raw calls and puts frames for a given ticker/expiry from Alpaca.

    This layer intentionally does only light standardization. Full filtering,
    midpoint creation, DTE calculation, and moneyness logic belong in the
    downstream processing layer.
    """
    calls, puts = _fetch_option_chain_cached(ticker, expiry)
    return calls.copy(), puts.copy()


def fetch_latest_spot(ticker: str) -> float:
    """Use recent daily history as the source of truth for current/most recent spot."""
    history = fetch_price_history(ticker, period="5d", interval="1d", auto_adjust=False)

    close_col = "Close"
    if close_col not in history.columns:
        raise DataUnavailableError(f"Close column unavailable for {ticker} spot lookup.")

    close_series = pd.to_numeric(history[close_col], errors="coerce").dropna()
    if close_series.empty:
        raise DataUnavailableError(f"No valid recent close values available for {ticker}.")

    return float(close_series.iloc[-1])


# ---------------------------------------------------------------------------
# Dividend yield — yfinance (isolated, fails gracefully with 0.0)
# ---------------------------------------------------------------------------

@ttl_cache(maxsize=64)
def _fetch_dividend_yield_cached(ticker: str) -> float:
    ticker = _normalize_ticker(ticker)
    try:
        info = yf.Ticker(ticker).info or {}
        return float(info.get("dividendYield") or 0.0)
    except Exception:
        return 0.0


def fetch_dividend_yield(ticker: str) -> float:
    """Return the annualised dividend yield for a ticker (e.g. 0.013 for 1.3%)."""
    return _fetch_dividend_yield_cached(ticker)


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def clear_market_data_cache() -> None:
    _fetch_price_history_cached.cache_clear()
    _fetch_expiries_cached.cache_clear()
    _fetch_option_chain_cached.cache_clear()
    _fetch_dividend_yield_cached.cache_clear()
