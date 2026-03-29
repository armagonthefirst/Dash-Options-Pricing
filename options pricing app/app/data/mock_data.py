from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd


TRADING_DAYS = 252
RISK_FREE_RATE = 0.042
TODAY = pd.Timestamp.today().normalize()

DEFAULT_DTES = [7, 14, 21, 30, 45, 60, 90, 120]
DEFAULT_MONEYNESS_GRID = np.round(np.arange(0.85, 1.151, 0.025), 3)

TICKER_ORDER = [
    "SPY",
    "QQQ",
    "IWM",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "TSLA",
    "AMD",
]


@dataclass(frozen=True)
class TickerConfig:
    name: str
    base_price: float
    annual_vol: float
    annual_drift: float
    base_iv: float
    avg_volume: int


TICKER_CONFIG: dict[str, TickerConfig] = {
    "SPY": TickerConfig("SPDR S&P 500 ETF Trust", 575.0, 0.16, 0.08, 0.18, 85_000_000),
    "QQQ": TickerConfig("Invesco QQQ Trust", 505.0, 0.20, 0.10, 0.22, 55_000_000),
    "IWM": TickerConfig("iShares Russell 2000 ETF", 225.0, 0.24, 0.07, 0.25, 32_000_000),
    "AAPL": TickerConfig("Apple Inc.", 218.0, 0.23, 0.11, 0.24, 58_000_000),
    "MSFT": TickerConfig("Microsoft Corporation", 468.0, 0.21, 0.12, 0.23, 27_000_000),
    "NVDA": TickerConfig("NVIDIA Corporation", 132.0, 0.38, 0.20, 0.42, 65_000_000),
    "AMZN": TickerConfig("Amazon.com, Inc.", 196.0, 0.28, 0.13, 0.30, 43_000_000),
    "META": TickerConfig("Meta Platforms, Inc.", 598.0, 0.30, 0.14, 0.31, 22_000_000),
    "TSLA": TickerConfig("Tesla, Inc.", 248.0, 0.45, 0.14, 0.48, 110_000_000),
    "AMD": TickerConfig("Advanced Micro Devices, Inc.", 173.0, 0.36, 0.15, 0.39, 61_000_000),
}


def _seed_from_ticker(ticker: str) -> int:
    return sum((idx + 1) * ord(char) for idx, char in enumerate(ticker))


def _rng_for_ticker(ticker: str, offset: int = 0) -> np.random.Generator:
    return np.random.default_rng(_seed_from_ticker(ticker) + offset)


def _annualize_std(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).std() * math.sqrt(TRADING_DAYS)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    sigma: float,
    option_type: str,
) -> float:
    if time_to_expiry <= 0:
        if option_type == "call":
            return max(spot - strike, 0.0)
        return max(strike - spot, 0.0)

    sigma = max(sigma, 1e-6)
    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (
        math.log(spot / strike) + (rate + 0.5 * sigma**2) * time_to_expiry
    ) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    if option_type == "call":
        return spot * _norm_cdf(d1) - strike * math.exp(-rate * time_to_expiry) * _norm_cdf(d2)

    return strike * math.exp(-rate * time_to_expiry) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def _black_scholes_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    sigma: float,
    option_type: str,
) -> dict[str, float]:
    sigma = max(sigma, 1e-6)
    time_to_expiry = max(time_to_expiry, 1e-6)
    sqrt_t = math.sqrt(time_to_expiry)

    d1 = (
        math.log(spot / strike) + (rate + 0.5 * sigma**2) * time_to_expiry
    ) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    pdf_d1 = math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi)

    if option_type == "call":
        delta = _norm_cdf(d1)
        theta = (
            -(spot * pdf_d1 * sigma) / (2 * sqrt_t)
            - rate * strike * math.exp(-rate * time_to_expiry) * _norm_cdf(d2)
        ) / TRADING_DAYS
    else:
        delta = _norm_cdf(d1) - 1
        theta = (
            -(spot * pdf_d1 * sigma) / (2 * sqrt_t)
            + rate * strike * math.exp(-rate * time_to_expiry) * _norm_cdf(-d2)
        ) / TRADING_DAYS

    gamma = pdf_d1 / (spot * sigma * sqrt_t)
    vega = (spot * pdf_d1 * sqrt_t) / 100.0

    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega),
    }


def _select_default_expiry(dtes: list[int]) -> int:
    return min(dtes, key=lambda x: abs(x - 30))


def _strike_step(spot: float) -> float:
    if spot >= 500:
        return 10.0
    if spot >= 200:
        return 5.0
    if spot >= 75:
        return 2.5
    return 1.0


@lru_cache(maxsize=None)
def get_supported_tickers() -> list[dict[str, str]]:
    return [
        {"ticker": ticker, "name": TICKER_CONFIG[ticker].name}
        for ticker in TICKER_ORDER
    ]


@lru_cache(maxsize=None)
def get_price_history(ticker: str, periods: int = 504) -> pd.DataFrame:
    if ticker not in TICKER_CONFIG:
        raise ValueError(f"Unsupported ticker: {ticker}")

    config = TICKER_CONFIG[ticker]
    rng = _rng_for_ticker(ticker, offset=1)

    dates = pd.bdate_range(end=TODAY, periods=periods)
    dt = 1 / TRADING_DAYS

    seasonal_cycle = np.sin(np.linspace(0, 5 * np.pi, periods)) * 0.12
    vol_path = config.annual_vol * (1 + seasonal_cycle)
    vol_path = np.clip(vol_path, config.annual_vol * 0.65, config.annual_vol * 1.45)

    shocks = rng.normal(0, 1, periods)
    log_returns = (
        (config.annual_drift - 0.5 * vol_path**2) * dt
        + vol_path * np.sqrt(dt) * shocks
    )

    close = np.empty(periods)
    close[0] = config.base_price
    for i in range(1, periods):
        close[i] = close[i - 1] * np.exp(log_returns[i])

    open_noise = rng.normal(0, 0.004, periods)
    open_prices = close * (1 + open_noise)

    intraday_noise = rng.uniform(0.004, 0.018, periods)
    highs = np.maximum(open_prices, close) * (1 + intraday_noise)
    lows = np.minimum(open_prices, close) * (1 - intraday_noise)

    volumes = (
        config.avg_volume
        * (1 + rng.normal(0, 0.10, periods))
        * (1 + np.abs(log_returns) * 6)
    ).astype(int)

    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": open_prices,
            "High": highs,
            "Low": lows,
            "Close": close,
            "Adj Close": close,
            "Volume": volumes,
        }
    )

    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    df["simple_return"] = df["Close"].pct_change()
    df["ma20"] = df["Close"].rolling(20).mean()
    df["ma60"] = df["Close"].rolling(60).mean()
    df["rv20"] = _annualize_std(df["log_return"], 20)
    df["rv60"] = _annualize_std(df["log_return"], 60)

    return df


@lru_cache(maxsize=None)
def get_forecast_volatility(ticker: str) -> float:
    history = get_price_history(ticker)
    rv20 = float(history["rv20"].dropna().iloc[-1])
    rv60 = float(history["rv60"].dropna().iloc[-1])

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
    return float(np.clip(forecast, 0.10, 0.85))


@lru_cache(maxsize=None)
def get_iv_term_structure(ticker: str) -> pd.DataFrame:
    if ticker not in TICKER_CONFIG:
        raise ValueError(f"Unsupported ticker: {ticker}")

    config = TICKER_CONFIG[ticker]
    rng = _rng_for_ticker(ticker, offset=2)
    forecast_vol = get_forecast_volatility(ticker)

    rows: list[dict[str, Any]] = []
    for dte in DEFAULT_DTES:
        normalized_dte = dte / 30.0
        slope = 0.012 * math.log1p(normalized_dte)
        noise = rng.normal(0, 0.004)

        atm_iv = max(
            0.08,
            config.base_iv
            + 0.30 * (forecast_vol - config.annual_vol)
            + slope
            + noise,
        )

        rows.append(
            {
                "expiry": (TODAY + pd.Timedelta(days=dte)).date().isoformat(),
                "dte": int(dte),
                "atm_iv": float(atm_iv),
            }
        )

    return pd.DataFrame(rows)


@lru_cache(maxsize=None)
def get_default_expiry(ticker: str) -> str:
    term = get_iv_term_structure(ticker)
    target_dte = _select_default_expiry(term["dte"].tolist())
    row = term.loc[term["dte"] == target_dte].iloc[0]
    return str(row["expiry"])


@lru_cache(maxsize=None)
def get_iv_smile(ticker: str, expiry: str | None = None) -> pd.DataFrame:
    if expiry is None:
        expiry = get_default_expiry(ticker)

    term = get_iv_term_structure(ticker)
    term_row = term.loc[term["expiry"] == expiry].iloc[0]
    atm_iv = float(term_row["atm_iv"])
    dte = int(term_row["dte"])

    rng = _rng_for_ticker(ticker, offset=3 + dte)
    smile_rows: list[dict[str, Any]] = []

    for moneyness in DEFAULT_MONEYNESS_GRID:
        call_skew = 0.22 * (moneyness - 1.0) ** 2 + 0.03 * max(moneyness - 1.0, 0)
        put_skew = 0.28 * (moneyness - 1.0) ** 2 + 0.07 * max(1.0 - moneyness, 0)

        call_iv = max(0.08, atm_iv + call_skew + rng.normal(0, 0.003))
        put_iv = max(0.08, atm_iv + put_skew + rng.normal(0, 0.003))

        smile_rows.append(
            {
                "expiry": expiry,
                "dte": dte,
                "moneyness": float(moneyness),
                "call_iv": float(call_iv),
                "put_iv": float(put_iv),
            }
        )

    return pd.DataFrame(smile_rows)


@lru_cache(maxsize=None)
def get_option_chain(ticker: str, expiry: str | None = None) -> pd.DataFrame:
    if ticker not in TICKER_CONFIG:
        raise ValueError(f"Unsupported ticker: {ticker}")

    if expiry is None:
        expiry = get_default_expiry(ticker)

    history = get_price_history(ticker)
    spot = float(history["Close"].iloc[-1])

    term = get_iv_term_structure(ticker)
    term_row = term.loc[term["expiry"] == expiry].iloc[0]
    dte = int(term_row["dte"])
    time_to_expiry = dte / 365.0

    smile = get_iv_smile(ticker, expiry)
    step = _strike_step(spot)

    min_strike = math.floor((spot * 0.85) / step) * step
    max_strike = math.ceil((spot * 1.15) / step) * step
    strikes = np.arange(min_strike, max_strike + step, step)

    rows: list[dict[str, Any]] = []
    rng = _rng_for_ticker(ticker, offset=4 + dte)

    for strike in strikes:
        moneyness = strike / spot

        smile_row = smile.iloc[(smile["moneyness"] - moneyness).abs().argmin()]
        call_iv = float(smile_row["call_iv"])
        put_iv = float(smile_row["put_iv"])

        for option_type, sigma in [("call", call_iv), ("put", put_iv)]:
            mid = _black_scholes_price(
                spot=spot,
                strike=float(strike),
                time_to_expiry=time_to_expiry,
                rate=RISK_FREE_RATE,
                sigma=sigma,
                option_type=option_type,
            )

            spread_floor = 0.05 if mid < 2 else 0.12
            spread = max(spread_floor, 0.03 * mid)
            bid = max(0.01, mid - spread / 2)
            ask = bid + spread

            liquidity_scale = max(0.12, 1.0 - abs(moneyness - 1.0) * 4.0)
            volume = int(
                max(
                    1,
                    rng.normal(900 if dte <= 30 else 550, 180) * liquidity_scale,
                )
            )
            open_interest = int(
                max(
                    10,
                    rng.normal(4_000 if dte <= 45 else 2_600, 700) * liquidity_scale,
                )
            )

            rows.append(
                {
                    "contract_id": f"{ticker}-{expiry}-{option_type.upper()}-{strike:.2f}",
                    "ticker": ticker,
                    "type": option_type.title(),
                    "expiry": expiry,
                    "dte": dte,
                    "strike": round(float(strike), 2),
                    "spot": round(spot, 2),
                    "moneyness": round(float(moneyness), 4),
                    "bid": round(float(bid), 2),
                    "ask": round(float(ask), 2),
                    "mid": round(float((bid + ask) / 2), 2),
                    "last": round(float(mid * rng.uniform(0.97, 1.03)), 2),
                    "volume": volume,
                    "open_interest": open_interest,
                    "iv": round(float(sigma), 4),
                }
            )

    chain = pd.DataFrame(rows).sort_values(["strike", "type"]).reset_index(drop=True)
    return chain


@lru_cache(maxsize=None)
def get_ticker_kpis(ticker: str) -> dict[str, Any]:
    history = get_price_history(ticker)
    term = get_iv_term_structure(ticker)

    latest = history.iloc[-1]
    prev = history.iloc[-2]
    forecast_vol = get_forecast_volatility(ticker)
    default_expiry = get_default_expiry(ticker)
    atm_iv = float(term.loc[term["expiry"] == default_expiry, "atm_iv"].iloc[0])

    return {
        "ticker": ticker,
        "name": TICKER_CONFIG[ticker].name,
        "spot_price": round(float(latest["Close"]), 2),
        "price_change_1d": float(latest["Close"] / prev["Close"] - 1.0),
        "rv20": float(latest["rv20"]),
        "rv60": float(latest["rv60"]),
        "forecast_vol_20d": float(forecast_vol),
        "atm_iv_30d": float(atm_iv),
        "iv_forecast_spread": float(atm_iv - forecast_vol),
        "default_expiry": default_expiry,
        "last_refresh": TODAY.strftime("%Y-%m-%d"),
    }


@lru_cache(maxsize=None)
def get_screener_data() -> pd.DataFrame:
    rows = [get_ticker_kpis(ticker) for ticker in TICKER_ORDER]
    df = pd.DataFrame(rows)

    return df.sort_values(
        by="iv_forecast_spread",
        key=lambda s: s.abs(),
        ascending=False,
    ).reset_index(drop=True)


def get_price_chart_frame(ticker: str, display_window: int = 252) -> pd.DataFrame:
    history = get_price_history(ticker).copy()
    return history.tail(display_window).reset_index(drop=True)


def get_volatility_chart_frame(ticker: str, display_window: int = 252) -> pd.DataFrame:
    history = get_price_history(ticker).copy().tail(display_window).reset_index(drop=True)
    forecast = get_forecast_volatility(ticker)

    forecast_dates = pd.bdate_range(start=history["Date"].iloc[-1], periods=21)[1:]
    forecast_frame = pd.DataFrame(
        {
            "Date": forecast_dates,
            "forecast_vol": forecast,
        }
    )

    return history, forecast_frame


def get_expiry_choices(ticker: str) -> list[dict[str, str]]:
    term = get_iv_term_structure(ticker)
    return [
        {
            "label": f"{row.expiry} ({int(row.dte)} DTE)",
            "value": str(row.expiry),
        }
        for row in term.itertuples(index=False)
    ]


def get_contract_snapshot(ticker: str, contract_id: str | None = None) -> dict[str, Any]:
    chain = get_option_chain(ticker)
    if contract_id is None:
        default_expiry = get_default_expiry(ticker)
        subset = chain[(chain["expiry"] == default_expiry) & (chain["type"] == "Call")]
        subset = subset.iloc[(subset["moneyness"] - 1.0).abs().argsort()]
        contract = subset.iloc[0]
    else:
        contract = chain.loc[chain["contract_id"] == contract_id].iloc[0]

    spot = float(contract["spot"])
    strike = float(contract["strike"])
    dte = int(contract["dte"])
    sigma = float(contract["iv"])
    option_type = contract["type"].lower()
    time_to_expiry = dte / 365.0

    market_mid = float(contract["mid"])
    benchmark_price = _black_scholes_price(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        rate=RISK_FREE_RATE,
        sigma=sigma,
        option_type=option_type,
    )

    theoretical_price = benchmark_price * (1.01 if option_type == "put" else 1.015)
    greeks = _black_scholes_greeks(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        rate=RISK_FREE_RATE,
        sigma=sigma,
        option_type=option_type,
    )

    return {
        "contract_id": str(contract["contract_id"]),
        "ticker": ticker,
        "type": str(contract["type"]),
        "expiry": str(contract["expiry"]),
        "dte": dte,
        "spot": round(spot, 2),
        "strike": round(strike, 2),
        "moneyness": float(contract["moneyness"]),
        "bid": float(contract["bid"]),
        "ask": float(contract["ask"]),
        "mid": market_mid,
        "iv": sigma,
        "benchmark_price": round(float(benchmark_price), 2),
        "theoretical_price": round(float(theoretical_price), 2),
        "pricing_gap": round(float(theoretical_price - market_mid), 2),
        "pricing_gap_pct": float((theoretical_price - market_mid) / market_mid) if market_mid else 0.0,
        "delta": greeks["delta"],
        "gamma": greeks["gamma"],
        "theta": greeks["theta"],
        "vega": greeks["vega"],
    }


def get_payoff_curve(
    ticker: str,
    contract_id: str | None = None,
    points: int = 50,
) -> pd.DataFrame:
    snapshot = get_contract_snapshot(ticker, contract_id)
    strike = snapshot["strike"]
    premium = snapshot["mid"]
    option_type = snapshot["type"].lower()
    spot = snapshot["spot"]

    underlying_prices = np.linspace(spot * 0.7, spot * 1.3, points)

    if option_type == "call":
        payoff = np.maximum(underlying_prices - strike, 0) - premium
    else:
        payoff = np.maximum(strike - underlying_prices, 0) - premium

    return pd.DataFrame(
        {
            "underlying_price": underlying_prices,
            "pnl_at_expiry": payoff,
        }
    )


def get_sensitivity_curve(
    ticker: str,
    contract_id: str | None = None,
    sensitivity_type: str = "vol",
    points: int = 40,
) -> pd.DataFrame:
    snapshot = get_contract_snapshot(ticker, contract_id)

    spot = snapshot["spot"]
    strike = snapshot["strike"]
    dte = snapshot["dte"]
    base_iv = snapshot["iv"]
    option_type = snapshot["type"].lower()
    time_to_expiry = dte / 365.0

    if sensitivity_type == "vol":
        vol_grid = np.linspace(max(0.10, base_iv * 0.6), base_iv * 1.4, points)
        values = [
            _black_scholes_price(spot, strike, time_to_expiry, RISK_FREE_RATE, vol, option_type)
            for vol in vol_grid
        ]
        return pd.DataFrame({"volatility": vol_grid, "option_value": values})

    price_grid = np.linspace(spot * 0.8, spot * 1.2, points)
    values = [
        _black_scholes_price(price, strike, time_to_expiry, RISK_FREE_RATE, base_iv, option_type)
        for price in price_grid
    ]
    return pd.DataFrame({"underlying_price": price_grid, "option_value": values})