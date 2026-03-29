from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from data.market_data import DataUnavailableError


TRADING_DAYS = 252

PRICE_REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
OPTION_NUMERIC_COLUMNS = [
    "strike",
    "lastPrice",
    "bid",
    "ask",
    "change",
    "percentChange",
    "volume",
    "openInterest",
    "impliedVolatility",
]

MIN_VALID_IV = 0.01
MAX_VALID_IV = 3.00
MAX_RELATIVE_SPREAD = 0.35
ATM_LOWER_MONEYNESS = 0.90
ATM_UPPER_MONEYNESS = 1.10
ATM_MIN_CANDIDATES = 3
ATM_TOP_N = 5


def _coerce_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.tz_localize(None)


def _coerce_numeric_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _clean_option_quality(
    df: pd.DataFrame,
    *,
    require_valid_quotes: bool = True,
    require_iv: bool = True,
    min_valid_iv: float = MIN_VALID_IV,
    max_valid_iv: float = MAX_VALID_IV,
    max_relative_spread: float | None = MAX_RELATIVE_SPREAD,
) -> pd.DataFrame:
    """
    Apply quote and IV sanity filters to a normalized option chain.
    Returns a filtered copy and preserves column order.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])

    out = df.copy()

    for col in ["strike", "bid", "ask", "mid", "iv", "moneyness"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "volume" in out.columns:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)
    if "open_interest" in out.columns:
        out["open_interest"] = pd.to_numeric(out["open_interest"], errors="coerce").fillna(0)

    out = out.dropna(subset=["strike"]).copy()
    out = out.loc[out["strike"] > 0].copy()

    if require_valid_quotes:
        out = out.dropna(subset=["bid", "ask"]).copy()
        out = out.loc[
            (out["bid"] >= 0)
            & (out["ask"] > 0)
            & (out["ask"] >= out["bid"])
        ].copy()
        out["mid"] = (out["bid"] + out["ask"]) / 2.0
        out = out.loc[out["mid"] > 0].copy()

        if max_relative_spread is not None:
            out["relative_spread"] = (out["ask"] - out["bid"]) / out["mid"]
            out = out.loc[out["relative_spread"] <= max_relative_spread].copy()
    else:
        if "mid" in out.columns:
            out = out.dropna(subset=["mid"]).copy()
            out = out.loc[out["mid"] > 0].copy()

    if require_iv:
        out = out.dropna(subset=["iv"]).copy()
        out = out.loc[
            (out["iv"] >= min_valid_iv)
            & (out["iv"] <= max_valid_iv)
        ].copy()

    if "moneyness" in out.columns:
        out = out.dropna(subset=["moneyness"]).copy()
        out = out.loc[out["moneyness"] > 0].copy()

    return out.reset_index(drop=True)


def annualize_volatility(return_series: pd.Series, window: int) -> pd.Series:
    """
    Annualized rolling standard deviation of daily log returns.
    """
    return return_series.rolling(window).std() * math.sqrt(TRADING_DAYS)


def normalize_price_history(
    df: pd.DataFrame,
    *,
    min_rows: int = 20,
) -> pd.DataFrame:
    """
    Normalize raw yfinance history into a stable OHLCV frame.

    Output columns:
    - Date
    - Open, High, Low, Close, Adj Close, Volume
    - log_return, simple_return
    - ma20, ma60
    - rv20, rv60
    """
    if df is None or df.empty:
        raise DataUnavailableError("Price history is empty.")

    missing = [col for col in PRICE_REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise DataUnavailableError(
            f"Price history is missing required columns: {missing}"
        )

    out = df.copy()

    out["Date"] = _coerce_datetime(out["Date"])
    out = _coerce_numeric_columns(
        out,
        ["Open", "High", "Low", "Close", "Adj Close", "Volume"],
    )

    if "Adj Close" not in out.columns:
        out["Adj Close"] = out["Close"]

    out = out.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    out = out.sort_values("Date").drop_duplicates(subset="Date", keep="last")

    # Remove unusable or nonsensical rows.
    out = out.loc[
        (out["Open"] > 0)
        & (out["High"] > 0)
        & (out["Low"] > 0)
        & (out["Close"] > 0)
        & (out["High"] >= out["Low"])
    ].copy()

    if len(out) < min_rows:
        raise DataUnavailableError(
            f"Price history has only {len(out)} usable rows; at least {min_rows} are required."
        )

    out["Volume"] = out["Volume"].fillna(0).astype("int64")

    out["log_return"] = np.log(out["Close"] / out["Close"].shift(1))
    out["simple_return"] = out["Close"].pct_change()

    out["ma20"] = out["Close"].rolling(20).mean()
    out["ma60"] = out["Close"].rolling(60).mean()
    out["rv20"] = annualize_volatility(out["log_return"], 20)
    out["rv60"] = annualize_volatility(out["log_return"], 60)

    return out.reset_index(drop=True)


def get_latest_price_snapshot(history: pd.DataFrame) -> dict[str, float | str]:
    """
    Extract simple latest-price metrics from a normalized price-history frame.
    """
    if history is None or history.empty:
        raise DataUnavailableError("Normalized price history is empty.")

    latest = history.iloc[-1]
    if len(history) < 2:
        raise DataUnavailableError("Need at least 2 rows to compute 1-day return.")

    previous = history.iloc[-2]

    return {
        "date": latest["Date"].date().isoformat(),
        "spot_price": float(latest["Close"]),
        "price_change_1d": float(latest["Close"] / previous["Close"] - 1.0),
        "rv20": float(latest["rv20"]) if pd.notna(latest["rv20"]) else np.nan,
        "rv60": float(latest["rv60"]) if pd.notna(latest["rv60"]) else np.nan,
    }


def validate_expiry_string(expiry: str) -> pd.Timestamp:
    expiry_ts = pd.to_datetime(expiry, errors="coerce")
    if pd.isna(expiry_ts):
        raise DataUnavailableError(f"Invalid expiry value: {expiry}")
    return pd.Timestamp(expiry_ts).normalize()


def compute_dte(
    expiry: str,
    *,
    as_of_date: pd.Timestamp | None = None,
) -> int:
    if as_of_date is None:
        as_of_date = pd.Timestamp.today().normalize()
    else:
        as_of_date = pd.Timestamp(as_of_date).normalize()

    expiry_ts = validate_expiry_string(expiry)
    return int((expiry_ts - as_of_date).days)


def normalize_option_chain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    *,
    spot: float,
    expiry: str,
    as_of_date: pd.Timestamp | None = None,
    require_valid_quotes: bool = True,
    require_iv: bool = True,
    min_valid_iv: float = MIN_VALID_IV,
    max_valid_iv: float = MAX_VALID_IV,
    max_relative_spread: float | None = MAX_RELATIVE_SPREAD,
) -> pd.DataFrame:
    """
    Merge and normalize raw yfinance calls/puts into one standard chain frame.

    Output columns:
    - contract_id, ticker, type, expiry, dte
    - strike, spot, moneyness
    - bid, ask, mid, last
    - volume, open_interest, iv
    - contract_symbol, last_trade_date
    """
    if spot <= 0:
        raise DataUnavailableError("Spot price must be positive to normalize option chain.")

    expiry_ts = validate_expiry_string(expiry)
    dte = compute_dte(expiry_ts.isoformat(), as_of_date=as_of_date)

    frames: list[pd.DataFrame] = []
    for option_type, raw in [("Call", calls_df), ("Put", puts_df)]:
        if raw is None or raw.empty:
            continue

        frame = raw.copy()
        frame = _coerce_numeric_columns(frame, OPTION_NUMERIC_COLUMNS)

        if "lastTradeDate" in frame.columns:
            frame["lastTradeDate"] = _coerce_datetime(frame["lastTradeDate"])

        if "contractSymbol" not in frame.columns:
            frame["contractSymbol"] = None

        frame["type"] = option_type
        frames.append(frame)

    if not frames:
        raise DataUnavailableError("Both calls and puts are empty for this expiry.")

    out = pd.concat(frames, ignore_index=True, sort=False)

    # Minimal required fields for downstream analytics.
    if "strike" not in out.columns:
        raise DataUnavailableError("Option chain is missing strike values.")

    out = out.dropna(subset=["strike"]).copy()
    out = out.loc[out["strike"] > 0].copy()

    # Normalize price fields.
    out["bid"] = out.get("bid", np.nan)
    out["ask"] = out.get("ask", np.nan)
    out["lastPrice"] = out.get("lastPrice", np.nan)
    out["impliedVolatility"] = out.get("impliedVolatility", np.nan)
    out["volume"] = out.get("volume", 0).fillna(0)
    out["openInterest"] = out.get("openInterest", 0).fillna(0)

    out["expiry"] = expiry_ts.date().isoformat()
    out["dte"] = dte
    out["spot"] = float(spot)
    out["moneyness"] = out["strike"] / float(spot)
    out["mid"] = (out["bid"] + out["ask"]) / 2.0

    out["ticker"] = out["contractSymbol"].astype(str).str.extract(r"^([A-Z]+)", expand=False)
    out["contract_id"] = out["contractSymbol"].fillna(
        out.apply(
            lambda row: f"UNKNOWN-{row['expiry']}-{row['type'].upper()}-{row['strike']:.2f}",
            axis=1,
        )
    )

    normalized = pd.DataFrame(
        {
            "contract_id": out["contract_id"].astype(str),
            "ticker": out["ticker"].fillna(""),
            "type": out["type"].astype(str),
            "expiry": out["expiry"].astype(str),
            "dte": out["dte"].astype(int),
            "strike": out["strike"].astype(float),
            "spot": out["spot"].astype(float),
            "moneyness": out["moneyness"].astype(float),
            "bid": out["bid"].astype(float),
            "ask": out["ask"].astype(float),
            "mid": out["mid"].astype(float),
            "last": out["lastPrice"].astype(float),
            "volume": out["volume"].astype(float).fillna(0).astype(int),
            "open_interest": out["openInterest"].astype(float).fillna(0).astype(int),
            "iv": out["impliedVolatility"].astype(float),
            "contract_symbol": out["contractSymbol"].astype(str),
            "last_trade_date": out["lastTradeDate"] if "lastTradeDate" in out.columns else pd.NaT,
        }
    )

    normalized = _clean_option_quality(
        normalized,
        require_valid_quotes=require_valid_quotes,
        require_iv=require_iv,
        min_valid_iv=min_valid_iv,
        max_valid_iv=max_valid_iv,
        max_relative_spread=max_relative_spread,
    )

    if normalized.empty:
        raise DataUnavailableError("No usable contracts remain after option-chain filtering.")

    normalized = normalized.sort_values(["strike", "type"]).reset_index(drop=True)
    return normalized


def filter_chain_by_moneyness(
    chain_df: pd.DataFrame,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> pd.DataFrame:
    if chain_df is None or chain_df.empty:
        return pd.DataFrame(columns=chain_df.columns if chain_df is not None else [])

    out = chain_df.copy()
    if lower is not None:
        out = out.loc[out["moneyness"] >= lower]
    if upper is not None:
        out = out.loc[out["moneyness"] <= upper]

    return out.reset_index(drop=True)


def filter_chain_by_type(
    chain_df: pd.DataFrame,
    option_type: str = "both",
) -> pd.DataFrame:
    if chain_df is None or chain_df.empty:
        return pd.DataFrame(columns=chain_df.columns if chain_df is not None else [])

    option_type = (option_type or "both").strip().lower()
    if option_type == "both":
        return chain_df.reset_index(drop=True)
    if option_type == "calls":
        return chain_df.loc[chain_df["type"] == "Call"].reset_index(drop=True)
    if option_type == "puts":
        return chain_df.loc[chain_df["type"] == "Put"].reset_index(drop=True)

    raise ValueError("option_type must be one of: both, calls, puts")


def sort_chain(
    chain_df: pd.DataFrame,
    sort_by: str = "strike",
) -> pd.DataFrame:
    if chain_df is None or chain_df.empty:
        return pd.DataFrame(columns=chain_df.columns if chain_df is not None else [])

    if sort_by not in {"strike", "volume", "open_interest", "iv"}:
        raise ValueError("sort_by must be one of: strike, volume, open_interest, iv")

    ascending = sort_by == "strike"
    return chain_df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)


def choose_default_expiry(
    expiries: list[str],
    *,
    target_dte: int = 30,
    as_of_date: pd.Timestamp | None = None,
) -> str:
    if not expiries:
        raise DataUnavailableError("No expiries available to choose from.")

    scored = []
    for expiry in expiries:
        dte = compute_dte(expiry, as_of_date=as_of_date)
        scored.append((expiry, dte, abs(dte - target_dte)))

    # Prefer non-expired expiries if available.
    non_expired = [row for row in scored if row[1] >= 0]
    pool = non_expired if non_expired else scored

    selected = min(pool, key=lambda row: row[2])
    return selected[0]


def build_expiry_choices(
    expiries: list[str],
    *,
    as_of_date: pd.Timestamp | None = None,
) -> list[dict[str, str]]:
    choices = []
    for expiry in expiries:
        dte = compute_dte(expiry, as_of_date=as_of_date)
        choices.append(
            {
                "label": f"{expiry} ({dte} DTE)",
                "value": expiry,
            }
        )
    return choices


def get_atm_reference_iv(
    chain_df: pd.DataFrame,
    *,
    spot: float | None = None,
    lower_moneyness: float = ATM_LOWER_MONEYNESS,
    upper_moneyness: float = ATM_UPPER_MONEYNESS,
    min_candidates: int = ATM_MIN_CANDIDATES,
    top_n: int = ATM_TOP_N,
    max_relative_spread: float | None = MAX_RELATIVE_SPREAD,
) -> float:
    """
    Estimate ATM IV from a normalized chain frame by selecting a robust near-ATM
    subset, ranking candidates by distance to ATM and quote quality, then taking
    the median IV of the best few contracts.
    """
    if chain_df is None or chain_df.empty:
        raise DataUnavailableError("Option chain is empty for ATM IV calculation.")

    if spot is None:
        if "spot" not in chain_df.columns or chain_df["spot"].dropna().empty:
            raise DataUnavailableError("Spot price unavailable for ATM IV calculation.")
        spot = float(chain_df["spot"].dropna().iloc[0])

    working = _clean_option_quality(
        chain_df,
        require_valid_quotes=True,
        require_iv=True,
        max_relative_spread=max_relative_spread,
    )

    if working.empty:
        raise DataUnavailableError("No quality-controlled contracts remain for ATM IV calculation.")

    working = filter_chain_by_moneyness(
        working,
        lower=lower_moneyness,
        upper=upper_moneyness,
    )

    if len(working) < min_candidates:
        raise DataUnavailableError("Insufficient near-ATM contracts for ATM IV calculation.")

    working["distance_to_atm"] = (working["moneyness"] - 1.0).abs()
    if "relative_spread" not in working.columns:
        working["relative_spread"] = (working["ask"] - working["bid"]) / working["mid"]

    ranked = working.sort_values(
        by=["distance_to_atm", "relative_spread", "open_interest", "volume"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)

    top = ranked.head(top_n)
    iv_values = top["iv"].dropna()
    if iv_values.empty:
        raise DataUnavailableError("No valid ATM IV values remain after ranking.")

    return float(iv_values.median())


def get_iv_smile_frame(
    chain_df: pd.DataFrame,
    *,
    lower_moneyness: float = 0.85,
    upper_moneyness: float = 1.15,
    max_relative_spread: float | None = MAX_RELATIVE_SPREAD,
) -> pd.DataFrame:
    """
    Build the dashboard-ready smile frame with one row per strike/moneyness and
    separate call/put IV columns, using quote- and IV-sanitized contracts only.
    """
    if chain_df is None or chain_df.empty:
        raise DataUnavailableError("Option chain is empty for IV smile calculation.")

    working = _clean_option_quality(
        chain_df,
        require_valid_quotes=True,
        require_iv=True,
        max_relative_spread=max_relative_spread,
    )

    working = filter_chain_by_moneyness(
        working,
        lower=lower_moneyness,
        upper=upper_moneyness,
    )

    if working.empty:
        raise DataUnavailableError("No contracts remain after IV smile moneyness filtering.")

    pivot = (
        working.pivot_table(
            index=["expiry", "dte", "strike", "moneyness"],
            columns="type",
            values="iv",
            aggfunc="median",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    if "Call" not in pivot.columns:
        pivot["Call"] = np.nan
    if "Put" not in pivot.columns:
        pivot["Put"] = np.nan

    smile = pivot.rename(
        columns={
            "Call": "call_iv",
            "Put": "put_iv",
        }
    )

    smile = smile.loc[
        smile[["call_iv", "put_iv"]].notna().any(axis=1)
    ].copy()

    if smile.empty:
        raise DataUnavailableError("No usable smile points remain after IV sanitization.")

    return smile.sort_values(["moneyness", "strike"]).reset_index(drop=True)
