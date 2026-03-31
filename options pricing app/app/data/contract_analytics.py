from __future__ import annotations

from data.cache import ttl_cache
from math import erf, exp, log, pi, sqrt

import numpy as np
import pandas as pd

from data.analytics import (
    get_live_default_expiry,
    get_live_filtered_option_chain,
    get_live_option_chain,
    get_live_supported_tickers,
    get_live_ticker_kpis,
    get_live_usable_expiries,
)
from data.market_data import DataUnavailableError
from data.pricing import price_american_option_binomial


RISK_FREE_RATE = 0.04
DIVIDEND_YIELD = 0.0
MIN_TIME_TO_EXPIRY = 1.0 / 365.0
PAYOFF_GRID_POINTS = 81
SENSITIVITY_GRID_POINTS = 61


def _validate_ticker(ticker: str) -> str:
    ticker = (ticker or "").strip().upper()
    supported = {item["ticker"] for item in get_live_supported_tickers()}
    if ticker not in supported:
        raise ValueError(f"Unsupported ticker: {ticker}")
    return ticker


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def _black_scholes_metrics(
    *,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str,
    risk_free_rate: float = RISK_FREE_RATE,
    dividend_yield: float = DIVIDEND_YIELD,
) -> dict[str, float]:
    option_type = (option_type or "").strip().lower()
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")

    spot = float(spot)
    strike = float(strike)
    time_to_expiry = max(float(time_to_expiry), 0.0)
    volatility = max(float(volatility), 0.0)

    if spot <= 0 or strike <= 0:
        raise DataUnavailableError("Spot and strike must be positive for option pricing.")

    disc_r = exp(-risk_free_rate * time_to_expiry)
    disc_q = exp(-dividend_yield * time_to_expiry)

    if time_to_expiry <= 0 or volatility <= 0:
        intrinsic_call = max(spot - strike, 0.0)
        intrinsic_put = max(strike - spot, 0.0)
        price = intrinsic_call if option_type == "call" else intrinsic_put

        if option_type == "call":
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0

        return {
            "price": float(price),
            "delta": float(delta),
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
        }

    sqrt_t = sqrt(time_to_expiry)
    d1 = (
        log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility * volatility) * time_to_expiry
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t

    if option_type == "call":
        price = spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
        delta = disc_q * _norm_cdf(d1)
        theta = (
            -spot * disc_q * _norm_pdf(d1) * volatility / (2.0 * sqrt_t)
            - risk_free_rate * strike * disc_r * _norm_cdf(d2)
            + dividend_yield * spot * disc_q * _norm_cdf(d1)
        )
    else:
        price = strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)
        delta = disc_q * (_norm_cdf(d1) - 1.0)
        theta = (
            -spot * disc_q * _norm_pdf(d1) * volatility / (2.0 * sqrt_t)
            + risk_free_rate * strike * disc_r * _norm_cdf(-d2)
            - dividend_yield * spot * disc_q * _norm_cdf(-d1)
        )

    gamma = disc_q * _norm_pdf(d1) / (spot * volatility * sqrt_t)
    vega = spot * disc_q * _norm_pdf(d1) * sqrt_t / 100.0

    return {
        "price": float(price),
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta / 365.0),
        "vega": float(vega),
    }


def _score_contract_candidates(chain: pd.DataFrame) -> pd.DataFrame:
    working = chain.copy()
    working["atm_distance"] = (working["moneyness"] - 1.0).abs()
    working["relative_spread"] = np.where(
        working["mid"] > 0,
        (working["ask"] - working["bid"]) / working["mid"],
        np.nan,
    )
    return working.sort_values(
        by=["atm_distance", "relative_spread", "open_interest", "volume"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)


@ttl_cache(maxsize=1024)
def _find_live_contract_row(ticker: str, contract_id: str) -> dict:
    ticker = _validate_ticker(ticker)
    contract_id = str(contract_id)

    for expiry in get_live_usable_expiries(ticker):
        try:
            chain = get_live_option_chain(ticker, expiry)
        except Exception:
            continue

        matched = chain.loc[chain["contract_id"].astype(str) == contract_id]
        if not matched.empty:
            return matched.iloc[0].to_dict()

    raise DataUnavailableError(f"Contract {contract_id} was not found for {ticker}.")


@ttl_cache(maxsize=256)
def _get_default_live_contract_row(ticker: str) -> dict:
    ticker = _validate_ticker(ticker)
    expiry = get_live_default_expiry(ticker)

    chain = get_live_filtered_option_chain(
        ticker=ticker,
        expiry=expiry,
        option_type="both",
        moneyness_bucket="0.90-1.10",
        sort_by="strike",
    )

    if chain.empty:
        chain = get_live_option_chain(ticker, expiry)

    if chain.empty:
        raise DataUnavailableError(f"No default contract could be selected for {ticker}.")

    ranked = _score_contract_candidates(chain)
    return ranked.iloc[0].to_dict()


def _resolve_contract_row(ticker: str, contract_id: str | None) -> dict:
    ticker = _validate_ticker(ticker)

    if contract_id:
        try:
            return _find_live_contract_row(ticker, str(contract_id))
        except Exception:
            pass

    return _get_default_live_contract_row(ticker)


def _build_snapshot_from_row(ticker: str, row: dict) -> dict:
    ticker = _validate_ticker(ticker)
    kpis = get_live_ticker_kpis(ticker)

    spot = float(row["spot"])
    strike = float(row["strike"])
    dte = int(row["dte"])
    time_to_expiry = max(dte / 365.0, MIN_TIME_TO_EXPIRY)
    option_type = str(row["type"]).strip().lower()
    contract_iv = float(row["iv"])
    forecast_vol = float(kpis["forecast_vol_20d"])
    market_mid = float(row["mid"])

    benchmark_metrics = _black_scholes_metrics(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        volatility=contract_iv,
        option_type=option_type,
    )
    theoretical_price = price_american_option_binomial(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        risk_free_rate=RISK_FREE_RATE,
        volatility=forecast_vol,
        dividend_yield=DIVIDEND_YIELD,
        option_type=option_type,
    )

    pricing_gap = theoretical_price - market_mid
    pricing_gap_pct = pricing_gap / market_mid if market_mid > 0 else np.nan

    return {
        "contract_id": str(row["contract_id"]),
        "ticker": ticker,
        "type": str(row["type"]),
        "expiry": str(row["expiry"]),
        "strike": strike,
        "spot": spot,
        "moneyness": float(row["moneyness"]),
        "bid": float(row["bid"]),
        "ask": float(row["ask"]),
        "mid": market_mid,
        "iv": contract_iv,
        "dte": dte,
        "forecast_vol": forecast_vol,
        "theoretical_price": float(theoretical_price),
        "benchmark_price": float(benchmark_metrics["price"]),
        "pricing_gap": float(pricing_gap),
        "pricing_gap_pct": float(pricing_gap_pct) if pd.notna(pricing_gap_pct) else np.nan,
        "delta": float(benchmark_metrics["delta"]),
        "gamma": float(benchmark_metrics["gamma"]),
        "theta": float(benchmark_metrics["theta"]),
        "vega": float(benchmark_metrics["vega"]),
        "last_refresh": str(kpis["last_refresh"]),
    }


@ttl_cache(maxsize=1024)
def get_live_contract_snapshot(ticker: str, contract_id: str | None = None) -> dict:
    row = _resolve_contract_row(ticker, contract_id)
    return _build_snapshot_from_row(ticker, row)


@ttl_cache(maxsize=1024)
def get_live_payoff_curve(ticker: str, contract_id: str | None = None) -> pd.DataFrame:
    snapshot = get_live_contract_snapshot(ticker, contract_id)

    spot = float(snapshot["spot"])
    strike = float(snapshot["strike"])
    premium = float(snapshot["mid"])
    option_type = str(snapshot["type"]).strip().lower()

    underlying_prices = np.linspace(spot * 0.70, spot * 1.30, PAYOFF_GRID_POINTS)

    if option_type == "call":
        payoff = np.maximum(underlying_prices - strike, 0.0)
    else:
        payoff = np.maximum(strike - underlying_prices, 0.0)

    pnl = payoff - premium

    return pd.DataFrame(
        {
            "underlying_price": underlying_prices,
            "pnl_at_expiry": pnl,
        }
    )


@ttl_cache(maxsize=2048)
def get_live_sensitivity_curve(
    ticker: str,
    contract_id: str | None = None,
    sensitivity_type: str = "vol",
) -> pd.DataFrame:
    snapshot = get_live_contract_snapshot(ticker, contract_id)

    sensitivity_type = (sensitivity_type or "vol").strip().lower()
    if sensitivity_type not in {"vol", "spot"}:
        raise ValueError("sensitivity_type must be one of: vol, spot")

    spot = float(snapshot["spot"])
    strike = float(snapshot["strike"])
    option_type = str(snapshot["type"]).strip().lower()
    forecast_vol = float(snapshot["forecast_vol"])
    current_iv = float(snapshot["iv"])
    time_to_expiry = max(float(snapshot["dte"]) / 365.0, MIN_TIME_TO_EXPIRY)

    if sensitivity_type == "vol":
        base_low = min(current_iv, forecast_vol)
        base_high = max(current_iv, forecast_vol)
        lower = max(0.05, base_low * 0.5)
        upper = max(lower + 0.05, min(1.50, base_high * 1.5))
        grid = np.linspace(lower, upper, SENSITIVITY_GRID_POINTS)
        values = [
            price_american_option_binomial(
                spot=spot,
                strike=strike,
                time_to_expiry=time_to_expiry,
                risk_free_rate=RISK_FREE_RATE,
                volatility=float(vol),
                dividend_yield=DIVIDEND_YIELD,
                option_type=option_type,
                steps=50,
            )
            for vol in grid
        ]
        return pd.DataFrame({"volatility": grid, "option_value": values})

    grid = np.linspace(spot * 0.70, spot * 1.30, SENSITIVITY_GRID_POINTS)
    values = [
        price_american_option_binomial(
            spot=float(s),
            strike=strike,
            time_to_expiry=time_to_expiry,
            risk_free_rate=RISK_FREE_RATE,
            volatility=forecast_vol,
            dividend_yield=DIVIDEND_YIELD,
            option_type=option_type,
            steps=50,
        )
        for s in grid
    ]
    return pd.DataFrame({"underlying_price": grid, "option_value": values})


def clear_contract_analytics_cache() -> None:
    _find_live_contract_row.cache_clear()
    _get_default_live_contract_row.cache_clear()
    get_live_contract_snapshot.cache_clear()
    get_live_payoff_curve.cache_clear()
    get_live_sensitivity_curve.cache_clear()
