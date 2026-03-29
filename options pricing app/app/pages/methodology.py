from dash import html, register_page


register_page(
    __name__,
    path="/methodology",
    name="Methodology",
    title="Methodology | Options Pricing ML App",
)


def build_method_block(title: str, body: list[str]) -> html.Div:
    return html.Div(
        className="section-card methodology-block",
        children=[
            html.H2(title, className="section-title"),
            html.Div(
                className="methodology-body",
                children=[html.P(paragraph, className="section-description") for paragraph in body],
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
                                    "This page explains the analytical structure of the app, the current "
                                    "v1 assumptions, and how data, volatility forecasting, and option "
                                    "valuation will fit together as the build progresses."
                                ),
                                className="page-description",
                            ),
                        ],
                    )
                ],
            ),
            html.Div(
                className="methodology-grid",
                children=[
                    build_method_block(
                        "1. Project Objective",
                        [
                            (
                                "The app is designed as a public-facing options analytics dashboard for "
                                "liquid U.S. equities and ETFs. Its purpose is to compare observed market "
                                "option prices with model-derived theoretical values, while giving the user "
                                "ticker-level context on realized volatility, forecast volatility, and the "
                                "current implied-volatility surface."
                            ),
                            (
                                "The intended workflow is: screen liquid underlyings, inspect ticker-level "
                                "volatility context, select a contract from the option chain, and then review "
                                "market-vs-model valuation outputs for that contract."
                            ),
                        ],
                    ),
                    build_method_block(
                        "2. Universe and Scope",
                        [
                            (
                                "The first version focuses on 10 highly liquid U.S. underlyings. This keeps "
                                "the system controlled, reduces data-quality issues, and makes comparisons more "
                                "consistent across assets with active listed options markets."
                            ),
                            (
                                "The current contract scope is limited to standard listed single-leg calls and "
                                "puts. Weeklies and monthlies are included, while more complex structures such "
                                "as spreads, LEAPS, and multi-leg strategy analytics are intentionally excluded "
                                "from v1."
                            ),
                        ],
                    ),
                    build_method_block(
                        "3. Market Data Layer",
                        [
                            (
                                "The current interface is powered by deterministic mock data so that layout, "
                                "navigation, and visual structure can be designed before the pricing logic is "
                                "finalized. This allows the application flow to be tested without exposing the "
                                "UI to noisy or incomplete market inputs too early."
                            ),
                            (
                                "When the live data phase begins, yfinance will be used for the initial market "
                                "data layer. The production flow will not send raw pulled data directly into the "
                                "UI. Instead, the process will be structured as: data acquisition, cleaning and "
                                "validation, metric calculation, then rendering."
                            ),
                        ],
                    ),
                    build_method_block(
                        "4. Historical Price and Volatility Inputs",
                        [
                            (
                                "Ticker-level metrics are based on daily underlying price history. Realized "
                                "volatility is computed from rolling standard deviations of daily log returns "
                                "and annualized using the standard 252-trading-day convention."
                            ),
                            (
                                "For v1, the dashboard emphasizes 20-day and 60-day realized volatility to show "
                                "shorter-term and medium-term realized volatility regimes. These measures provide "
                                "context for the forecasted volatility estimate and for the interpretation of "
                                "market-implied volatility."
                            ),
                        ],
                    ),
                    build_method_block(
                        "5. Forecast Volatility Layer",
                        [
                            (
                                "The dashboard is being built around a 20-trading-day forecast horizon. This "
                                "horizon fits naturally with short-dated listed options analysis and aligns "
                                "reasonably well with a 30-DTE reference point for ATM implied volatility."
                            ),
                            (
                                "At the current stage, the forecast values are placeholder outputs from the mock "
                                "data layer. Later, this will be replaced by a proper volatility forecasting "
                                "model trained on historical market features. The page structure is already set "
                                "up so that the forecast model can be swapped in without redesigning the app."
                            ),
                        ],
                    ),
                    build_method_block(
                        "6. Implied Volatility Reference Design",
                        [
                            (
                                "The dashboard uses ATM implied volatility as a key market reference metric. "
                                "For consistency, the ATM IV KPI is tied to the expiry closest to 30 calendar "
                                "days and the strike closest to current spot. Where both call and put IV are "
                                "available, the reference value is taken as the average of the two."
                            ),
                            (
                                "This ATM IV reference is used both on the screener and on the ticker dashboard. "
                                "The spread between ATM implied volatility and forecast volatility is one of the "
                                "main high-level signals in the application."
                            ),
                        ],
                    ),
                    build_method_block(
                        "7. Option Chain Exploration",
                        [
                            (
                                "The ticker dashboard includes an option chain exploration layer that acts as a "
                                "contract selection interface rather than a trading terminal. The chain is "
                                "filtered by expiry, option type, moneyness range, and sort order."
                            ),
                            (
                                "For the first version, the design is intentionally simple: single selected "
                                "expiry, both calls and puts available, and a near-the-money focus by default. "
                                "The application uses midpoint pricing as the primary market reference rather "
                                "than last-traded price, since midpoint is generally more stable for valuation "
                                "comparison."
                            ),
                        ],
                    ),
                    build_method_block(
                        "8. Valuation Framework",
                        [
                            (
                                "The final valuation stage of the app will focus on pricing American-style listed "
                                "equity and ETF options using a binomial tree model. This is the core theoretical "
                                "pricing engine planned for the project."
                            ),
                            (
                                "Black-Scholes will still appear in the app, but only as a benchmark or reference "
                                "model rather than the primary valuation engine. This provides a useful comparison "
                                "point while keeping the main model consistent with the American-style exercise "
                                "feature of many listed U.S. equity options."
                            ),
                        ],
                    ),
                    build_method_block(
                        "9. Current State of the Build",
                        [
                            (
                                "At the current stage, the application already supports the full top-level product "
                                "flow: market screener, ticker dashboard, option chain exploration, contract "
                                "analysis page, and methodology page."
                            ),
                            (
                                "The remaining work is mainly quantitative rather than structural: replacing mock "
                                "data with live market data, implementing robust calculation layers, and then "
                                "adding the binomial option pricer and related sensitivity analytics."
                            ),
                        ],
                    ),
                    build_method_block(
                        "10. Limitations and Intended Use",
                        [
                            (
                                "This application is an analytical prototype. It is designed to support market "
                                "inspection, contract comparison, and methodology demonstration. It is not a "
                                "brokerage interface, trade execution tool, or investment recommendation system."
                            ),
                            (
                                "Outputs depend on model assumptions, data quality, and parameter choices. Even "
                                "once live market data is integrated, model-vs-market gaps should be interpreted "
                                "as analytical signals rather than direct evidence of actionable mispricing."
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )