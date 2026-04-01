from __future__ import annotations

from data.cache import ttl_cache
from typing import Tuple

import pandas as pd
import yfinance as yf


DEFAULT_HISTORY_PERIOD = "2y"
DEFAULT_HISTORY_INTERVAL = "1d"


class DataUnavailableError(RuntimeError):
    """Raised when live market data cannot be fetched or is unusable."""


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
    """
    yfinance history usually returns a DatetimeIndex or Date index.
    Reset it into a normal column so downstream processing is simpler.
    """
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


@ttl_cache(maxsize=128)
def _fetch_price_history_cached(
    ticker: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = DEFAULT_HISTORY_INTERVAL,
    auto_adjust: bool = False,
) -> pd.DataFrame:
    ticker = _normalize_ticker(ticker)

    try:
        yf_ticker = yf.Ticker(ticker)
        raw = yf_ticker.history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            actions=False,
        )
    except Exception as exc:
        raise DataUnavailableError(f"Failed to fetch price history for {ticker}: {exc}") from exc

    history = _ensure_date_column(raw)
    history = _validate_history_frame(history, ticker)
    return history


def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = DEFAULT_HISTORY_INTERVAL,
    auto_adjust: bool = False,
) -> pd.DataFrame:
    """
    Return raw historical OHLCV data from yfinance, lightly standardized.

    Output is still 'market-data layer' output, not fully processed analytics data.
    """
    return _fetch_price_history_cached(
        ticker=ticker,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
    ).copy()


@ttl_cache(maxsize=128)
def _fetch_expiries_cached(ticker: str) -> tuple[str, ...]:
    ticker = _normalize_ticker(ticker)

    try:
        yf_ticker = yf.Ticker(ticker)
        expiries = yf_ticker.options or ()
    except Exception as exc:
        raise DataUnavailableError(f"Failed to fetch option expiries for {ticker}: {exc}") from exc

    expiries = tuple(str(expiry) for expiry in expiries if expiry)
    if not expiries:
        raise DataUnavailableError(f"No option expiries returned for {ticker}.")

    return expiries


def fetch_expiries(ticker: str) -> list[str]:
    return list(_fetch_expiries_cached(ticker))


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
        yf_ticker = yf.Ticker(ticker)
        chain = yf_ticker.option_chain(expiry)
    except Exception as exc:
        raise DataUnavailableError(
            f"Failed to fetch option chain for {ticker} at {expiry}: {exc}"
        ) from exc

    calls = _normalize_option_frame(getattr(chain, "calls", pd.DataFrame()), expiry, "call")
    puts = _normalize_option_frame(getattr(chain, "puts", pd.DataFrame()), expiry, "put")

    if calls.empty and puts.empty:
        raise DataUnavailableError(f"No option chain rows returned for {ticker} at {expiry}.")

    return calls, puts


def fetch_option_chain(ticker: str, expiry: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return raw calls and puts frames for a given ticker/expiry.

    This layer intentionally does only light standardization. Full filtering,
    midpoint creation, DTE calculation, and moneyness logic belong in the
    downstream processing layer.
    """
    calls, puts = _fetch_option_chain_cached(ticker, expiry)
    return calls.copy(), puts.copy()


def fetch_latest_spot(ticker: str) -> float:
    """
    Use recent daily history as the source of truth for current/most recent spot.
    """
    history = fetch_price_history(ticker, period="5d", interval="1d", auto_adjust=False)

    close_col = "Close"
    if close_col not in history.columns:
        raise DataUnavailableError(f"Close column unavailable for {ticker} spot lookup.")

    close_series = pd.to_numeric(history[close_col], errors="coerce").dropna()
    if close_series.empty:
        raise DataUnavailableError(f"No valid recent close values available for {ticker}.")

    return float(close_series.iloc[-1])


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


def clear_market_data_cache() -> None:
    """
    Handy during development if you want to force-refresh yfinance pulls
    without restarting the app.
    """
    _fetch_price_history_cached.cache_clear()
    _fetch_expiries_cached.cache_clear()
    _fetch_option_chain_cached.cache_clear()
    _fetch_dividend_yield_cached.cache_clear()