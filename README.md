# Options Pricing & Analytics Platform

A full-stack options pricing web application that prices American-style options
using a Cox-Ross-Rubinstein (CRR) binomial tree and compares theoretical fair
value against live market prices. Built with Python, Dash, and deployed on Microsoft Azure.

**Live demo:** [options.shariqusoof.com](https://options.shariqusoof.com)

---

## What It Does

The app pulls live market data for 10 of the most actively traded U.S. stocks
and ETFs, refreshing every hour. It prices each option contract using a
custom-built binomial tree, back-solves implied volatility via bisection, and
computes Greeks — then surfaces the gap between the model's theoretical price
and what the market is actually charging.

### Pages

| Page | Description |
|------|-------------|
| **Overview / Screener** | Live grid of all 10 tickers with spot price, 1-day change, realised vol, forecast vol, and IV spread |
| **Ticker Dashboard** | Per-ticker volatility charts, IV term structure, IV smile, and full options chain with filtering |
| **Contract Analysis** | Single-contract view with theoretical vs market pricing, Greeks, payoff diagram, and sensitivity curves |
| **Methodology** | Plain-language explanation of the data pipeline, pricing model, and limitations |

### Tracked Tickers

SPY · QQQ · IWM · AAPL · MSFT · NVDA · AMZN · META · TSLA · AMD

---

## Pricing Model

Options are priced using a **Cox-Ross-Rubinstein (CRR) binomial tree** — the
standard approach for American-style options, which supports early exercise.

```
u = exp(σ√Δt)          d = 1/u
p = (exp((r - q)Δt) - d) / (u - d)
```

The tree runs 200 steps for final pricing and 50 steps during implied volatility
solving (bisection) and sensitivity curve generation.

**Implied volatility** is back-solved from the live market mid price using
bisection search on the binomial pricer, converging to within 0.01% tolerance.

**Greeks** are computed via finite differences on the Black-Scholes model
(Delta, Gamma, Theta, Vega) and displayed alongside plain-English interpretations.

**Volatility forecast** blends 20-day and 60-day realised volatility:

```
Forecast Vol = (0.65 × RV₂₀ + 0.35 × RV₆₀) × ticker_bias
```

The pricing gap (`Theoretical − Market Mid`) signals whether the model considers
the market price cheap or expensive relative to the forecast volatility.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | [Dash](https://dash.plotly.com/) (Plotly / React) |
| Charts | Plotly |
| Data | [yfinance](https://github.com/ranaroussi/yfinance) |
| Data processing | pandas, NumPy |
| Server | Gunicorn (WSGI) |
| Hosting | Microsoft Azure |
| DNS | Cloudflare |
| Language | Python 3.11+ |

---

## Running Locally

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
git clone https://github.com/armagonthefirst/Options-Pricing.git
cd "Dash-Options-Pricing/options pricing app"

pip install -r requirements.txt

cd app
python main.py
```

Open [http://localhost:8050](http://localhost:8050) in your browser.

> **Note:** The app fetches live data from Yahoo Finance by default.
> An internet connection is required. Data is cached in-memory for 1 hour.

---

## Architecture Notes

### Caching

All yfinance calls are wrapped in a custom TTL cache decorator (`data/cache.py`)
with a 1-hour expiry. On startup, a background daemon thread pre-warms the cache
for all 10 tickers — so the first visitor hits a hot cache rather than waiting
for live fetches.

```python
# Simplified pre-warm logic
for ticker in TICKER_ORDER:
    get_live_ticker_kpis(ticker)   # price history, vol metrics, option chain
    fetch_dividend_yield(ticker)   # dividend yield for binomial pricer
    sleep(3)                       # paced to avoid rate limiting
```

The cache refreshes every hour in a background loop without restarting the server.

### Performance

The app was optimised to run on a constrained cloud instance (0.5 CPU, 512MB RAM):

- **Expiry usability checks** use raw yfinance IV instead of running the full binomial solver on every expiry — reducing tree evaluations from ~62,500 to ~2,000 per chain
- **Callback splitting** ensures changing a filter only redraws the options chain, not all charts on the page
- **Sensitivity curves** run at 50 tree steps instead of 200 (fast, with <0.1% accuracy loss)
- **Price history** is capped at 1 year (sufficient for all volatility calculations)

---

## Deployment

The app is deployed on a Microsoft Azure Virtual Machine with configured access controls and basic network settings for secure live hosting.
The app server is run using Gunicorn.

---
