"""
American-option pricing via the Cox-Ross-Rubinstein (CRR) binomial tree.

This module provides:

- ``price_american_option_binomial`` — fair value of an American call or put.
- ``implied_vol_from_price`` — back-solve implied volatility from an observed
  market price using bisection on the binomial pricer.

All parameters are explicit so functions can be called from any context
without relying on module-level constants.

Phase 2 will add ``compute_binomial_greeks()`` using finite differences.
"""

from __future__ import annotations

from math import exp, sqrt

import numpy as np


def price_american_option_binomial(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float,
    option_type: str,
    steps: int = 200,
) -> float:
    """
    Price an American option using a CRR binomial tree.

    Parameters
    ----------
    spot : float
        Current underlying price (must be > 0).
    strike : float
        Option strike price (must be > 0).
    time_to_expiry : float
        Time to expiry in years (e.g. 30 / 365).
    risk_free_rate : float
        Annualized risk-free interest rate (e.g. 0.04 for 4 %).
    volatility : float
        Annualized volatility (e.g. 0.25 for 25 %).
    dividend_yield : float
        Continuous dividend yield (e.g. 0.01 for 1 %).
    option_type : str
        ``"call"`` or ``"put"`` (case-insensitive).
    steps : int, optional
        Number of time steps in the tree.  Default is 200.

    Returns
    -------
    float
        The American option fair value.

    Raises
    ------
    ValueError
        If inputs are invalid (non-positive spot/strike, bad option_type,
        steps < 1, or risk-neutral probability outside [0, 1]).
    """
    # ------------------------------------------------------------------
    # Validate inputs
    # ------------------------------------------------------------------
    option_type = (option_type or "").strip().lower()
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")

    spot = float(spot)
    strike = float(strike)
    time_to_expiry = float(time_to_expiry)
    volatility = float(volatility)
    risk_free_rate = float(risk_free_rate)
    dividend_yield = float(dividend_yield)
    steps = int(steps)

    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive.")
    if steps < 1:
        raise ValueError("steps must be >= 1.")

    # ------------------------------------------------------------------
    # Degenerate cases — return intrinsic value immediately
    # ------------------------------------------------------------------
    if time_to_expiry <= 0 or volatility <= 0:
        if option_type == "call":
            return max(spot - strike, 0.0)
        return max(strike - spot, 0.0)

    # ------------------------------------------------------------------
    # Tree parameters
    # ------------------------------------------------------------------
    dt = time_to_expiry / steps
    u = exp(volatility * sqrt(dt))
    d = 1.0 / u
    disc = exp(-risk_free_rate * dt)
    p = (exp((risk_free_rate - dividend_yield) * dt) - d) / (u - d)

    if not (0.0 < p < 1.0):
        raise ValueError(
            f"Risk-neutral probability p = {p:.6f} is outside (0, 1). "
            "Check that the combination of rate, dividend yield, volatility, "
            "and time step is reasonable."
        )

    # ------------------------------------------------------------------
    # Terminal asset prices  (vectorised with NumPy)
    # ------------------------------------------------------------------
    j = np.arange(steps + 1)
    asset_prices = spot * (u ** (steps - j)) * (d ** j)

    # Terminal payoffs
    if option_type == "call":
        values = np.maximum(asset_prices - strike, 0.0)
    else:
        values = np.maximum(strike - asset_prices, 0.0)

    # ------------------------------------------------------------------
    # Backward induction with early-exercise check
    # ------------------------------------------------------------------
    for i in range(steps - 1, -1, -1):
        # Continuation value (discounted expected value under Q)
        values = disc * (p * values[: i + 1] + (1.0 - p) * values[1: i + 2])

        # Asset prices at this time step
        node_j = np.arange(i + 1)
        asset_at_node = spot * (u ** (i - node_j)) * (d ** node_j)

        # Intrinsic value
        if option_type == "call":
            intrinsic = np.maximum(asset_at_node - strike, 0.0)
        else:
            intrinsic = np.maximum(strike - asset_at_node, 0.0)

        # American early-exercise decision
        values = np.maximum(values, intrinsic)

    return float(values[0])


def implied_vol_from_price(
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    dividend_yield: float,
    option_type: str,
    *,
    lower: float = 0.01,
    upper: float = 3.00,
    tol: float = 1e-4,
    max_iter: int = 50,
    steps: int = 50,
) -> float | None:
    """
    Back-solve implied volatility from an observed market price.

    Uses bisection on :func:`price_american_option_binomial`.  The tree
    uses fewer steps than the default pricer (50 vs 200) to keep the
    solve fast — accuracy is still within ~0.1 % of the 200-step value.

    Parameters
    ----------
    market_price : float
        Observed option price (mid or lastPrice).
    spot, strike, time_to_expiry, risk_free_rate, dividend_yield, option_type
        Same as :func:`price_american_option_binomial`.
    lower, upper : float
        Bisection bounds for volatility search.
    tol : float
        Convergence tolerance on price difference.
    max_iter : int
        Maximum bisection iterations.
    steps : int
        Binomial tree steps for each pricing call (50 by default).

    Returns
    -------
    float or None
        The solved implied volatility, or ``None`` if the solver cannot
        converge (e.g. the market price is below intrinsic).
    """
    market_price = float(market_price)
    if market_price <= 0:
        return None

    option_type = (option_type or "").strip().lower()

    # Quick sanity: if market price is below intrinsic, no valid IV exists.
    if option_type == "call":
        intrinsic = max(float(spot) - float(strike), 0.0)
    else:
        intrinsic = max(float(strike) - float(spot), 0.0)
    if market_price < intrinsic - tol:
        return None

    try:
        for _ in range(max_iter):
            mid_vol = (lower + upper) / 2.0
            model_price = price_american_option_binomial(
                spot=spot,
                strike=strike,
                time_to_expiry=time_to_expiry,
                risk_free_rate=risk_free_rate,
                volatility=mid_vol,
                dividend_yield=dividend_yield,
                option_type=option_type,
                steps=steps,
            )

            if abs(model_price - market_price) < tol:
                return mid_vol

            if model_price < market_price:
                lower = mid_vol
            else:
                upper = mid_vol

        # Return best estimate even if not fully converged.
        return (lower + upper) / 2.0

    except (ValueError, ZeroDivisionError):
        return None
