from dash import html, register_page


register_page(
    __name__,
    path="/methodology",
    name="Methodology",
    title="Methodology | Live Options Pricing Dashboard",
)


def _section(title: str, paragraphs: list) -> html.Div:
    """Build a collapsible accordion section.

    Each item in *paragraphs* is either a plain string (rendered as <p>) or an
    ``html`` component (rendered as-is, e.g. a formula block or table).
    """
    body_children = []
    for item in paragraphs:
        if isinstance(item, str):
            body_children.append(html.P(item))
        else:
            body_children.append(item)

    return html.Div(
        className="method-section open",
        children=[
            html.Div(
                className="method-section-header",
                children=[
                    html.H2(title),
                    html.Span("v", className="method-chevron"),
                ],
            ),
            html.Div(
                className="method-section-body",
                children=body_children,
            ),
        ],
    )


def layout() -> html.Div:
    return html.Div(
        className="page methodology-page",
        children=[
            html.Div(
                className="page-header",
                children=[
                    html.Div(
                        className="page-header-copy",
                        children=[
                            html.H1("Methodology", className="page-title"),
                            html.P(
                                (
                                    "How the app works: data pipeline, volatility forecasting, "
                                    "option pricing models, and performance design."
                                ),
                                className="page-description",
                            ),
                        ],
                    )
                ],
            ),
            html.Div(
                className="method-accordion",
                children=[
                    # ── 1. Overview ──────────────────────────────────────
                    _section("1. Overview", [
                        (
                            "This application is an options analytics dashboard for liquid U.S. "
                            "equities and ETFs. It compares observed market option prices with "
                            "model-derived theoretical values, giving users ticker-level "
                            "volatility context, implied-volatility surface views, and "
                            "single-contract valuation outputs."
                        ),
                        (
                            "The intended workflow is: screen the universe by volatility "
                            "signals, inspect a ticker's realized and implied volatility "
                            "regime, select a contract from the option chain, and review "
                            "the model's theoretical price against the market quote."
                        ),
                    ]),

                    # ── 2. Data Pipeline ─────────────────────────────────
                    _section("2. Data Pipeline", [
                        (
                            "Live market data is sourced from Yahoo Finance via the yfinance "
                            "Python library. The pipeline follows a strict layered architecture: "
                            "data acquisition, cleaning and validation, metric calculation, "
                            "then rendering."
                        ),
                        (
                            "Price history is fetched as daily OHLCV bars and normalized into a "
                            "standard format with computed fields: log returns, simple returns, "
                            "20-day and 60-day moving averages, and rolling realized volatility."
                        ),
                        (
                            "Option chains are fetched per expiry and normalized into a unified "
                            "schema with computed fields: days to expiry, moneyness, midpoint "
                            "price, and implied volatility."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "Off-Hours IV Solving\n"
                                "When the US market is closed, yfinance returns stale bid/ask "
                                "data (often zeros). In these cases, the app falls back to "
                                "lastPrice and back-solves implied volatility using bisection "
                                "on the binomial pricer at 50 tree steps. This ensures IV "
                                "values remain usable for analysis outside trading hours."
                            ),
                        ),
                        (
                            "All data functions are LRU-cached. Once a ticker's data is loaded, "
                            "subsequent page loads and callback updates hit the cache instantly. "
                            "The cache refreshes when the app is restarted."
                        ),
                    ]),

                    # ── 3. Universe ──────────────────────────────────────
                    _section("3. Universe & Scope", [
                        (
                            "The app covers 10 highly liquid U.S. underlyings: SPY, QQQ, IWM, "
                            "AAPL, MSFT, NVDA, AMZN, META, TSLA, and AMD. These were chosen "
                            "for their deep options markets, tight bid-ask spreads, and high "
                            "open interest, which minimizes data-quality issues."
                        ),
                        (
                            "The contract scope is limited to standard listed single-leg calls "
                            "and puts across available weekly and monthly expiries. Complex "
                            "structures such as spreads, LEAPS, and multi-leg strategies are "
                            "excluded from this version."
                        ),
                    ]),

                    # ── 4. Volatility Forecasting ────────────────────────
                    _section("4. Volatility Forecasting", [
                        (
                            "The app uses a 20-trading-day forecast horizon, which aligns with "
                            "the 30 calendar-day DTE reference used for ATM implied volatility. "
                            "The current forecast model is a placeholder designed to be swapped "
                            "for a trained ML model without changing the app's interface."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "Forecast = (0.65 x RV20 + 0.35 x RV60) x ticker_bias\n\n"
                                "Where:\n"
                                "  RV20  = 20-day annualized realized volatility\n"
                                "  RV60  = 60-day annualized realized volatility\n"
                                "  ticker_bias = per-ticker scaling factor (0.96 - 1.03)"
                            ),
                        ),
                        html.Table(
                            className="method-param-table",
                            children=[
                                html.Thead(html.Tr([
                                    html.Th("Ticker"),
                                    html.Th("Bias Factor"),
                                    html.Th("Rationale"),
                                ])),
                                html.Tbody([
                                    html.Tr([html.Td("SPY"), html.Td("0.98"), html.Td("Index tends to mean-revert")]),
                                    html.Tr([html.Td("QQQ"), html.Td("1.00"), html.Td("Neutral baseline")]),
                                    html.Tr([html.Td("IWM"), html.Td("1.02"), html.Td("Small-cap vol slightly higher")]),
                                    html.Tr([html.Td("NVDA"), html.Td("0.97"), html.Td("High RV overstates forward vol")]),
                                    html.Tr([html.Td("TSLA"), html.Td("0.96"), html.Td("Extreme RV tends to compress")]),
                                    html.Tr([html.Td("AMZN"), html.Td("1.03"), html.Td("Earnings-driven vol clusters")]),
                                ]),
                            ],
                        ),
                        (
                            "The forecast is clipped to a floor of 8% and a ceiling of 120% "
                            "annualized to prevent degenerate inputs to the pricing model."
                        ),
                    ]),

                    # ── 5. Implied Volatility ────────────────────────────
                    _section("5. Implied Volatility Reference", [
                        (
                            "ATM implied volatility is the primary market reference metric. It "
                            "is computed from the expiry closest to 30 calendar days and the "
                            "strike closest to current spot. Where both call and put IV are "
                            "available, the reference is the average of the two."
                        ),
                        (
                            "The spread between ATM IV and forecast volatility is the main "
                            "screening signal. A positive spread (IV > Forecast) suggests the "
                            "market is pricing more risk than the model predicts; a negative "
                            "spread suggests the opposite."
                        ),
                    ]),

                    # ── 6. Pricing Models ────────────────────────────────
                    _section("6. Pricing Models", [
                        (
                            "The app uses two pricing models side by side: a CRR binomial tree "
                            "for theoretical pricing and Black-Scholes as a European benchmark."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "CRR Binomial Tree (Primary)\n\n"
                                "u = exp(sigma * sqrt(dt))\n"
                                "d = 1 / u\n"
                                "p = (exp((r - q) * dt) - d) / (u - d)\n\n"
                                "Parameters:\n"
                                "  Steps     = 200\n"
                                "  r         = 4.0% (risk-free rate)\n"
                                "  q         = 0.0% (dividend yield)\n"
                                "  sigma     = forecast volatility (for theoretical)\n"
                                "            = contract IV (for benchmark)\n\n"
                                "At each node: max(intrinsic, continuation)\n"
                                "This handles American-style early exercise."
                            ),
                        ),
                        (
                            "The theoretical price uses the model's forecast volatility as "
                            "the vol input. The benchmark price uses the contract's own "
                            "implied volatility, providing a like-for-like comparison that "
                            "isolates the vol forecast's impact on pricing."
                        ),
                        (
                            "Black-Scholes is used as the European-exercise benchmark. Since "
                            "all 10 tickers trade American-style options, the binomial price "
                            "will be equal to or higher than BS for puts (due to early exercise "
                            "premium) and approximately equal for calls on non-dividend stocks."
                        ),
                    ]),

                    # ── 7. Greeks ────────────────────────────────────────
                    _section("7. Greeks", [
                        (
                            "The contract analysis page displays four Greeks: Delta, Gamma, "
                            "Theta, and Vega. These are currently computed using the "
                            "Black-Scholes closed-form solutions for efficiency."
                        ),
                        html.Table(
                            className="method-param-table",
                            children=[
                                html.Thead(html.Tr([
                                    html.Th("Greek"),
                                    html.Th("Meaning"),
                                    html.Th("Source"),
                                ])),
                                html.Tbody([
                                    html.Tr([html.Td("Delta"), html.Td("Option price change per $1 underlying move"), html.Td("Black-Scholes N(d1)")]),
                                    html.Tr([html.Td("Gamma"), html.Td("Delta change per $1 underlying move"), html.Td("Black-Scholes")]),
                                    html.Tr([html.Td("Theta"), html.Td("Daily time decay in dollars"), html.Td("Black-Scholes / 365")]),
                                    html.Tr([html.Td("Vega"), html.Td("Price change per 1% volatility move"), html.Td("Black-Scholes / 100")]),
                                ]),
                            ],
                        ),
                        (
                            "A planned upgrade will add binomial finite-difference Greeks, "
                            "which better account for American-style exercise. The current "
                            "BS-based Greeks are a reasonable approximation for near-ATM "
                            "contracts."
                        ),
                    ]),

                    # ── 8. Performance ───────────────────────────────────
                    _section("8. Performance Design", [
                        (
                            "The app is optimized for locally-run analytical use. Key "
                            "performance measures:"
                        ),
                        html.Table(
                            className="method-param-table",
                            children=[
                                html.Thead(html.Tr([
                                    html.Th("Technique"),
                                    html.Th("Impact"),
                                ])),
                                html.Tbody([
                                    html.Tr([html.Td("Near-ATM trimming"), html.Td("Keeps 25 contracts closest to ATM per chain, reducing IV solve work by ~15x")]),
                                    html.Tr([html.Td("Early-stop expiry check"), html.Td("Stops after finding 5 usable expiries near 30 DTE instead of checking all 15+")]),
                                    html.Tr([html.Td("LRU caching"), html.Td("All data functions cached; subsequent loads are instant")]),
                                    html.Tr([html.Td("NumPy-vectorized tree"), html.Td("Binomial pricer uses array ops, ~1ms per call at 200 steps")]),
                                ]),
                            ],
                        ),
                        (
                            "During market hours, yfinance returns real bid/ask/IV values and "
                            "the IV solver never fires, so load times are dominated by network "
                            "calls (~15-20 seconds for the full screener on first load). After "
                            "the first load, everything is cached and instant."
                        ),
                    ]),

                    # ── 9. Sensitivity Analysis ──────────────────────────
                    _section("9. Sensitivity Analysis", [
                        (
                            "The contract analysis page includes two sensitivity curves: "
                            "option value vs. volatility and option value vs. underlying price. "
                            "Each curve is computed by varying a single input across 61 points "
                            "while holding all other parameters fixed."
                        ),
                        (
                            "Sensitivity curves use the binomial pricer (matching the "
                            "theoretical price engine), so they correctly account for "
                            "American-style early exercise across the full parameter range."
                        ),
                    ]),

                    # ── 10. Limitations ───────────────────────────────────
                    _section("10. Limitations & Intended Use", [
                        (
                            "This application is an analytical prototype designed for market "
                            "inspection, contract comparison, and methodology demonstration. "
                            "It is not a brokerage interface, trade execution tool, or "
                            "investment recommendation system."
                        ),
                        (
                            "Key limitations: the volatility forecast is a simple weighted "
                            "blend (not a trained ML model), dividend yield is assumed zero, "
                            "the risk-free rate is hardcoded at 4%, and Greeks are "
                            "European-style approximations. Off-hours data may be stale."
                        ),
                        (
                            "Model-vs-market pricing gaps should be interpreted as analytical "
                            "signals rather than direct evidence of actionable mispricing."
                        ),
                    ]),
                ],
            ),
        ],
    )
