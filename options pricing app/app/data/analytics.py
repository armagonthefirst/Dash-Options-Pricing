from __future__ import annotations

from data.cache import ttl_cache

import numpy as np
import pandas as pd

from data.market_data import (
    DataUnavailableError,
    fetch_expiries,
    fetch_option_chain,
    fetch_price_history,
)
from data.data_processing import (
    build_expiry_choices,
    choose_default_expiry,
    filter_chain_by_moneyness,
    filter_chain_by_type,
    get_atm_reference_iv,
    get_iv_smile_frame,
    get_latest_price_snapshot,
    normalize_option_chain,
    normalize_price_history,
    sort_chain,
)


SUPPORTED_TICKERS = {
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "IWM": "iShares Russell 2000 ETF",
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "META": "Meta Platforms, Inc.",
    "TSLA": "Tesla, Inc.",
    "AMD": "Advanced Micro Devices, Inc.",
}

TICKER_ORDER = list(SUPPORTED_TICKERS.keys())

MIN_DTE = 7
MAX_DTE = 120
TARGET_DTE = 30

DEFAULT_SMILE_LOWER_MONEYNESS = 0.85
DEFAULT_SMILE_UPPER_MONEYNESS = 1.15
USABLE_MIN_NEAR_ATM_CONTRACTS = 4
USABLE_MIN_UNIQUE_STRIKES = 3
USABLE_ATM_ANCHOR_TOLERANCE = 0.05
USABLE_REQUIRED_COLUMNS = ("strike", "mid", "iv", "moneyness")


def _validate_ticker(ticker: str) -> str:
    ticker = (ticker or "").strip().upper()
    if ticker not in SUPPORTED_TICKERS:
        raise ValueError(f"Unsupported ticker: {ticker}")
    return ticker


def _safe_float(value, default=np.nan) -> float:
    try:
        if pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _forecast_vol_from_history(history: pd.DataFrame, ticker: str) -> float:
    """
    Placeholder live forecast logic for now.
    Uses a weighted blend of RV20 and RV60 with a small ticker-specific bias.

    Later this function can be replaced by the real ML volatility model
    without changing the rest of the app-facing interface.
    """
    latest = history.iloc[-1]

    rv20 = _safe_float(latest.get("rv20"))
    rv60 = _safe_float(latest.get("rv60"))

    if np.isnan(rv20) and np.isnan(rv60):
        raise DataUnavailableError(f"Unable to compute forecast volatility for {ticker}.")

    if np.isnan(rv20):
        rv20 = rv60
    if np.isnan(rv60):
        rv60 = rv20

    ticker_bias = {
        "SPY": 0.98,
        "QQQ": 1.00,
        "IWM": 1.02,
        "AAPL": 1.01,
        "MSFT": 0.99,
        "NVDA": 0.97,
        "AMZN": 1.03,
        "META": 1.00,
        "TSLA": 0.96,
        "AMD": 0.98,
    }[ticker]

    forecast = (0.65 * rv20 + 0.35 * rv60) * ticker_bias
    return float(np.clip(forecast, 0.08, 1.20))


@ttl_cache(maxsize=512)
def _get_live_expiry_usability_snapshot(ticker: str, expiry: str) -> dict:
    """
    Lightweight usability check using raw yfinance data only.

    Intentionally avoids calling get_live_option_chain so that no IV solving
    or binomial-tree computation is triggered for expiries that may be
    discarded as unusable.  Only strike arithmetic and yfinance's own
    impliedVolatility column are used here.
    """
    ticker = _validate_ticker(ticker)

    fallback_dte = None
    try:
        fallback_dte = int(
            (pd.Timestamp(expiry).normalize() - pd.Timestamp.today().normalize()).days
        )
    except Exception:
        pass

    snapshot = {
        "expiry": expiry,
        "dte": fallback_dte,
        "n_total": 0,
        "n_near_atm": 0,
        "n_unique_strikes": 0,
        "has_left": False,
        "has_right": False,
        "has_atm_anchor": False,
        "is_usable": False,
    }

    try:
        history = get_live_price_history(ticker)
        spot = float(history["Close"].iloc[-1])
        calls_df, puts_df = fetch_option_chain(ticker, expiry)
    except Exception:
        return snapshot

    frames = [df for df in [calls_df, puts_df] if df is not None and not df.empty]
    if not frames:
        return snapshot

    raw = pd.concat(frames, ignore_index=True)

    if "strike" not in raw.columns:
        return snapshot

    raw["strike"] = pd.to_numeric(raw["strike"], errors="coerce")
    raw = raw.dropna(subset=["strike"])
    raw = raw[raw["strike"] > 0].copy()

    if raw.empty:
        return snapshot

    # Use yfinance's own impliedVolatility — no binomial solving needed here
    if "impliedVolatility" in raw.columns:
        raw["impliedVolatility"] = pd.to_numeric(raw["impliedVolatility"], errors="coerce")
        raw = raw[raw["impliedVolatility"].between(0.01, 3.0)].copy()

    if raw.empty:
        return snapshot

    raw["moneyness"] = raw["strike"] / spot

    near_atm = raw[
        raw["moneyness"].between(
            DEFAULT_SMILE_LOWER_MONEYNESS,
            DEFAULT_SMILE_UPPER_MONEYNESS,
            inclusive="both",
        )
    ]

    n_total = int(len(raw))
    n_near_atm = int(len(near_atm))
    n_unique_strikes = int(near_atm["strike"].nunique()) if not near_atm.empty else 0
    has_left = bool((near_atm["moneyness"] < 1.0).any()) if not near_atm.empty else False
    has_right = bool((near_atm["moneyness"] > 1.0).any()) if not near_atm.empty else False
    has_atm_anchor = (
        bool((near_atm["moneyness"].sub(1.0).abs() <= USABLE_ATM_ANCHOR_TOLERANCE).any())
        if not near_atm.empty
        else False
    )

    is_usable = (
        n_near_atm >= USABLE_MIN_NEAR_ATM_CONTRACTS
        and n_unique_strikes >= USABLE_MIN_UNIQUE_STRIKES
        and has_left
        and has_right
        and has_atm_anchor
    )

    snapshot.update(
        {
            "n_total": n_total,
            "n_near_atm": n_near_atm,
            "n_unique_strikes": n_unique_strikes,
            "has_left": has_left,
            "has_right": has_right,
            "has_atm_anchor": has_atm_anchor,
            "is_usable": is_usable,
        }
    )

    return snapshot


@ttl_cache(maxsize=128)
def get_live_usable_expiries(ticker: str, max_usable: int = 5) -> tuple[str, ...]:
    """
    Return usable expiries, checking at most enough to find ``max_usable``.

    Expiries are sorted by proximity to TARGET_DTE so the most relevant
    ones are tested first, avoiding expensive usability checks on all
    available expiries.
    """
    ticker = _validate_ticker(ticker)

    all_expiries = list(get_live_expiries(ticker))

    # Sort by proximity to target DTE so we check the most useful ones first.
    def _dte_distance(expiry: str) -> int:
        try:
            dte = int((pd.Timestamp(expiry).normalize() - pd.Timestamp.today().normalize()).days)
            return abs(dte - TARGET_DTE)
        except Exception:
            return 9999

    all_expiries.sort(key=_dte_distance)

    usable = []
    for expiry in all_expiries:
        snapshot = _get_live_expiry_usability_snapshot(ticker, expiry)
        if snapshot["is_usable"]:
            usable.append(expiry)
            if len(usable) >= max_usable:
                break

    if not usable:
        raise DataUnavailableError(f"No usable expiries found for {ticker}.")

    # Return sorted by date for consistent downstream ordering.
    usable.sort()
    return tuple(usable)


@ttl_cache(maxsize=128)
def get_live_price_history(ticker: str) -> pd.DataFrame:
    ticker = _validate_ticker(ticker)
    raw = fetch_price_history(ticker, period="1y", interval="1d", auto_adjust=False)
    history = normalize_price_history(raw, min_rows=20)
    return history


@ttl_cache(maxsize=128)
def get_live_expiries(ticker: str) -> tuple[str, ...]:
    ticker = _validate_ticker(ticker)

    expiries = fetch_expiries(ticker)
    filtered = []

    for expiry in expiries:
        try:
            dte = int((pd.Timestamp(expiry).normalize() - pd.Timestamp.today().normalize()).days)
            if MIN_DTE <= dte <= MAX_DTE:
                filtered.append(expiry)
        except Exception:
            continue

    if not filtered:
        raise DataUnavailableError(
            f"No usable expiries found for {ticker} in {MIN_DTE}-{MAX_DTE} DTE range."
        )

    return tuple(filtered)


@ttl_cache(maxsize=256)
def get_live_option_chain(ticker: str, expiry: str) -> pd.DataFrame:
    ticker = _validate_ticker(ticker)
    history = get_live_price_history(ticker)
    spot = float(history["Close"].iloc[-1])

    calls_df, puts_df = fetch_option_chain(ticker, expiry)
    chain = normalize_option_chain(
        calls_df,
        puts_df,
        spot=spot,
        expiry=expiry,
        require_valid_quotes=True,
        require_iv=True,
    )

    if chain.empty:
        raise DataUnavailableError(f"No usable option contracts found for {ticker} at {expiry}.")

    return chain


@ttl_cache(maxsize=128)
def get_live_default_expiry(ticker: str) -> str:
    ticker = _validate_ticker(ticker)
    expiries = list(get_live_usable_expiries(ticker))
    return choose_default_expiry(expiries, target_dte=TARGET_DTE)


@ttl_cache(maxsize=128)
def get_live_ticker_kpis(ticker: str) -> dict:
    ticker = _validate_ticker(ticker)

    history = get_live_price_history(ticker)
    latest_snapshot = get_latest_price_snapshot(history)

    forecast_vol = _forecast_vol_from_history(history, ticker)
    default_expiry = get_live_default_expiry(ticker)
    default_chain = get_live_option_chain(ticker, default_expiry)
    atm_iv = get_atm_reference_iv(default_chain)

    return {
        "ticker": ticker,
        "name": SUPPORTED_TICKERS[ticker],
        "spot_price": round(latest_snapshot["spot_price"], 2),
        "price_change_1d": float(latest_snapshot["price_change_1d"]),
        "rv20": float(latest_snapshot["rv20"]),
        "rv60": float(latest_snapshot["rv60"]),
        "forecast_vol_20d": float(forecast_vol),
        "atm_iv_30d": float(atm_iv),
        "iv_forecast_spread": float(atm_iv - forecast_vol),
        "default_expiry": default_expiry,
        "last_refresh": latest_snapshot["date"],
    }


@ttl_cache(maxsize=32)
def get_live_screener_data() -> pd.DataFrame:
    rows = []

    for ticker in TICKER_ORDER:
        try:
            rows.append(get_live_ticker_kpis(ticker))
        except Exception:
            # Skip broken tickers rather than failing the entire screener.
            continue

    if not rows:
        raise DataUnavailableError("No screener rows could be built from live data.")

    df = pd.DataFrame(rows)
    df = df.sort_values(
        by="iv_forecast_spread",
        key=lambda s: s.abs(),
        ascending=False,
    ).reset_index(drop=True)

    return df


@ttl_cache(maxsize=128)
def get_live_iv_term_structure(ticker: str) -> pd.DataFrame:
    ticker = _validate_ticker(ticker)

    rows = []
    expiries = get_live_usable_expiries(ticker)

    for expiry in expiries:
        try:
            chain = get_live_option_chain(ticker, expiry)
            atm_iv = get_atm_reference_iv(chain)
            dte = int(chain["dte"].iloc[0])

            rows.append(
                {
                    "expiry": expiry,
                    "dte": dte,
                    "atm_iv": float(atm_iv),
                }
            )
        except Exception:
            continue

    if not rows:
        raise DataUnavailableError(f"Unable to build IV term structure for {ticker}.")

    term = pd.DataFrame(rows).sort_values("dte").reset_index(drop=True)
    return term


@ttl_cache(maxsize=256)
def get_live_iv_smile(ticker: str, expiry: str | None = None) -> pd.DataFrame:
    ticker = _validate_ticker(ticker)

    if expiry is None:
        expiry = get_live_default_expiry(ticker)

    snapshot = _get_live_expiry_usability_snapshot(ticker, expiry)
    if not snapshot["is_usable"]:
        raise DataUnavailableError(
            f"Expiry {expiry} is not usable for IV smile analytics for {ticker}."
        )

    chain = get_live_option_chain(ticker, expiry)
    smile = get_iv_smile_frame(
        chain,
        lower_moneyness=DEFAULT_SMILE_LOWER_MONEYNESS,
        upper_moneyness=DEFAULT_SMILE_UPPER_MONEYNESS,
    )

    if smile.empty:
        raise DataUnavailableError(f"Unable to build IV smile for {ticker} at {expiry}.")

    return smile


def get_live_expiry_choices(ticker: str) -> list[dict[str, str]]:
    ticker = _validate_ticker(ticker)
    expiries = list(get_live_usable_expiries(ticker))
    return build_expiry_choices(expiries)


def get_live_price_chart_frame(ticker: str, display_window: int = 252) -> pd.DataFrame:
    ticker = _validate_ticker(ticker)
    history = get_live_price_history(ticker).copy()
    return history.tail(display_window).reset_index(drop=True)


def get_live_volatility_chart_frame(
    ticker: str,
    display_window: int = 252,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticker = _validate_ticker(ticker)

    full_history = get_live_price_history(ticker)
    history = full_history.copy().tail(display_window).reset_index(drop=True)
    forecast = _forecast_vol_from_history(full_history, ticker)

    forecast_dates = pd.bdate_range(start=history["Date"].iloc[-1], periods=21)[1:]
    forecast_frame = pd.DataFrame(
        {
            "Date": forecast_dates,
            "forecast_vol": forecast,
        }
    )

    return history, forecast_frame


def get_live_filtered_option_chain(
    ticker: str,
    expiry: str,
    option_type: str = "both",
    moneyness_bucket: str = "0.85-1.15",
    sort_by: str = "strike",
) -> pd.DataFrame:
    ticker = _validate_ticker(ticker)

    chain = get_live_option_chain(ticker, expiry)

    chain = filter_chain_by_type(chain, option_type)

    if moneyness_bucket == "0.90-1.10":
        chain = filter_chain_by_moneyness(chain, lower=0.90, upper=1.10)
    elif moneyness_bucket == "0.85-1.15":
        chain = filter_chain_by_moneyness(
            chain,
            lower=DEFAULT_SMILE_LOWER_MONEYNESS,
            upper=DEFAULT_SMILE_UPPER_MONEYNESS,
        )

    chain = sort_chain(chain, sort_by)
    return chain.reset_index(drop=True)


def get_live_supported_tickers() -> list[dict[str, str]]:
    return [
        {"ticker": ticker, "name": SUPPORTED_TICKERS[ticker]}
        for ticker in TICKER_ORDER
    ]


def clear_analytics_cache() -> None:
    _get_live_expiry_usability_snapshot.cache_clear()
    get_live_price_history.cache_clear()
    get_live_expiries.cache_clear()
    get_live_usable_expiries.cache_clear()
    get_live_option_chain.cache_clear()
    get_live_default_expiry.cache_clear()
    get_live_ticker_kpis.cache_clear()
    get_live_screener_data.cache_clear()
    get_live_iv_term_structure.cache_clear()
    get_live_iv_smile.cache_clear()
