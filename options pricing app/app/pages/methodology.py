from dash import html, register_page


register_page(
    __name__,
    path="/methodology",
    name="Methodology",
    title="Methodology | Live Stock Options Pricing Dashboard",
    in_nav=True,
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
                            html.H1("How it works", className="page-title"),
                            html.P(
                                (
                                    "A quick walk-through of how this app pulls data, "
                                    "prices options, and puts everything together."
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
                    # -- 1. Overview -----------------------------------------
                    _section("1. The big picture", [
                        (
                            "This app pulls live market data for ten actively traded "
                            "U.S. stocks and ETFs, runs a custom options pricing model "
                            "against each contract, and shows how that model price "
                            "compares to what the market is charging. The gap between "
                            "the two is the signal worth paying attention to."
                        ),
                        (
                            "The typical workflow: scan the screener for interesting "
                            "volatility readings, open a ticker to explore its price "
                            "history, volatility regime, and option chain, then drill "
                            "into a specific contract to see the model's valuation "
                            "and Greeks."
                        ),
                    ]),

                    # -- 2. How it's built -----------------------------------
                    _section("2. How it's built", [
                        (
                            "The app is written entirely in Python and built on "
                            "Plotly Dash, a framework that handles the web interface, "
                            "routing, and interactivity."
                        ),
                        (
                            "The pricing models, volatility calculations, and data "
                            "processing are all written in Python. The interface uses "
                            "a single-page layout with client-side routing across four "
                            "views: the screener, ticker dashboard, contract analysis "
                            "page, and this methodology page."
                        ),
                        (
                            "Market data is fetched from the Alpaca Markets API and "
                            "cached in memory on the server. The app is hosted on "
                            "Azure, which means the cache is always warm and page "
                            "loads are fast regardless of traffic."
                        ),
                    ]),

                    # -- 3. Data Pipeline ------------------------------------
                    _section("3. Where the data comes from", [
                        (
                            "All market data comes from the Alpaca Markets API. "
                            "Price history, option expiries, and option chains are "
                            "fetched at startup and kept in a server-side cache."
                        ),
                        (
                            "For each ticker, roughly a year of daily price history "
                            "is pulled (open, high, low, close, volume). Realized "
                            "volatility, moving averages, and return series are all "
                            "derived from that."
                        ),
                        (
                            "Option chains are fetched per expiry from Alpaca's "
                            "snapshot endpoint. Each contract comes with live bid, "
                            "ask, and implied volatility. From there the app computes "
                            "days to expiry, moneyness, and a midpoint price from "
                            "the bid/ask spread."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "Outside market hours\n"
                                "When markets are closed, Alpaca returns the most "
                                "recent snapshot from the last trading session. If "
                                "bid and ask are missing for a contract, the app "
                                "falls back to the last traded price and back-solves "
                                "implied volatility using the binomial model to keep "
                                "the data usable."
                            ),
                        ),
                    ]),

                    # -- 4. Universe -----------------------------------------
                    _section("4. Which stocks are covered", [
                        (
                            "The app covers ten of the most actively traded U.S. "
                            "stocks and ETFs: SPY, QQQ, IWM, AAPL, MSFT, NVDA, AMZN, "
                            "META, TSLA, and AMD. These all have liquid options markets "
                            "with tight spreads and substantial open interest, which "
                            "means the data is reliable and the implied volatility "
                            "readings are meaningful."
                        ),
                        (
                            "Coverage is limited to single-leg calls and puts across "
                            "weekly and monthly expiries. No spreads, no multi-leg "
                            "strategies. The focus is on the core pricing problem."
                        ),
                    ]),

                    # -- 5. Volatility Forecasting ---------------------------
                    _section("5. Volatility forecasting", [
                        (
                            "The volatility forecast is a weighted blend of two "
                            "realized volatility windows, with a small per-ticker "
                            "scaling factor applied. The structure is intentional: "
                            "this function is designed to be a drop-in replacement "
                            "for an ML model when one is ready. Nothing else in the "
                            "app needs to change."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "Current formula:\n\n"
                                "Forecast = (0.65 x RV20 + 0.35 x RV60) x ticker_bias\n\n"
                                "RV20 = realized vol over the last 20 trading days\n"
                                "RV60 = realized vol over the last 60 trading days\n"
                                "ticker_bias = a small scaling factor per stock"
                            ),
                        ),
                        (
                            "Recent volatility gets more weight (65% on the 20-day "
                            "window) to reflect the current regime, with the 60-day "
                            "window smoothing out short-term noise. The per-ticker "
                            "bias accounts for differences in mean-reversion behaviour "
                            "across stocks."
                        ),
                        (
                            "The output is clamped between 8% and 120% annualized "
                            "to prevent unreasonable inputs reaching the pricing model."
                        ),
                    ]),

                    # -- 6. Implied Volatility -------------------------------
                    _section("6. Implied volatility", [
                        (
                            "Implied volatility (IV) is the market's expectation of "
                            "how much a stock will move over a given period. It's "
                            "derived from an option's price: if the option is "
                            "expensive, IV is high, and vice versa."
                        ),
                        (
                            "ATM implied volatility from the expiry closest to 30 "
                            "days out is used as the main market reference. This "
                            "gives a consistent, comparable reading across all "
                            "ten tickers."
                        ),
                        (
                            "The key signal on the screener is the spread between "
                            "ATM IV and the forecast. If IV is above the forecast, "
                            "the market is pricing in more risk than the model "
                            "expects. If it's below, the market may be underpricing "
                            "risk."
                        ),
                    ]),

                    # -- 7. Pricing Models -----------------------------------
                    _section("7. How options are priced", [
                        (
                            "Two models run in parallel. The primary model is a "
                            "binomial tree (Cox-Ross-Rubinstein), and the secondary "
                            "benchmark is Black-Scholes."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "Binomial tree - the short version:\n\n"
                                "The time to expiry is divided into steps. At each "
                                "step the stock price can move up or down by a fixed "
                                "factor. The tree is built forward to expiry, option "
                                "payoffs are calculated at every terminal node, then "
                                "the model works backwards, checking at each node "
                                "whether early exercise is more valuable than holding. "
                                "This makes it correct for American-style options, "
                                "which is what all U.S. equity options are."
                            ),
                        ),
                        (
                            "The theoretical price uses forecast volatility as the "
                            "input. The benchmark price uses the contract's own "
                            "implied volatility fed into Black-Scholes. Comparing "
                            "the two isolates how much of any pricing difference "
                            "comes from the volatility estimate versus the model "
                            "structure itself."
                        ),
                        (
                            "Black-Scholes assumes European-style exercise only, so "
                            "for puts in particular the binomial price will be "
                            "slightly higher since it accounts for the value of "
                            "early exercise."
                        ),
                    ]),

                    # -- 8. Greeks -------------------------------------------
                    _section("8. Greeks", [
                        (
                            "Greeks measure the sensitivity of an option's price "
                            "to changes in its inputs."
                        ),
                        html.Table(
                            className="method-param-table",
                            children=[
                                html.Thead(html.Tr([
                                    html.Th("Greek"),
                                    html.Th("What it tells you"),
                                ])),
                                html.Tbody([
                                    html.Tr([
                                        html.Td("Delta"),
                                        html.Td("How much the option price moves when the stock moves $1"),
                                    ]),
                                    html.Tr([
                                        html.Td("Gamma"),
                                        html.Td("How fast delta itself changes - the acceleration"),
                                    ]),
                                    html.Tr([
                                        html.Td("Theta"),
                                        html.Td("How much value the option loses each day just from time passing"),
                                    ]),
                                    html.Tr([
                                        html.Td("Vega"),
                                        html.Td("How much the option price changes when volatility moves 1%"),
                                    ]),
                                ]),
                            ],
                        ),
                        (
                            "The Greeks are calculated using Black-Scholes closed-form "
                            "formulas, which is standard and accurate for near-ATM "
                            "contracts. A future improvement would compute them "
                            "numerically from the binomial tree for better precision "
                            "on deep in- or out-of-the-money options."
                        ),
                    ]),

                    # -- 9. Sensitivity Analysis -----------------------------
                    _section("9. Sensitivity charts", [
                        (
                            "The contract analysis page includes two sensitivity "
                            "charts: one showing how the option value changes across "
                            "a range of volatility inputs, and one showing how it "
                            "changes across a range of stock prices. Everything else "
                            "is held fixed while one variable moves."
                        ),
                        (
                            "Both charts use the binomial pricer at each grid point, "
                            "giving a realistic picture of how the model responds "
                            "rather than a linear approximation."
                        ),
                    ]),

                    # -- 10. Limitations -------------------------------------
                    _section("10. Limitations", [
                        (
                            "This is a personal project and analytical tool, "
                            "not a trading system."
                        ),
                        html.Ul(
                            className="method-list",
                            children=[
                                html.Li(
                                    "The volatility forecast is a weighted historical "
                                    "average, not a trained predictive model"
                                ),
                                html.Li(
                                    "Dividend yield is fetched live and defaults "
                                    "to 0% if unavailable"
                                ),
                                html.Li(
                                    "The risk-free rate is fixed at 4%"
                                ),
                                html.Li(
                                    "Greeks are calculated using Black-Scholes "
                                    "(European-style) approximations"
                                ),
                                html.Li(
                                    "Option data outside market hours reflects the "
                                    "most recent Alpaca snapshot, which may be from "
                                    "the previous session"
                                ),
                            ],
                        ),
                        (
                            "Any pricing gap between the model and the market is a "
                            "signal worth investigating, not a trade recommendation."
                        ),
                    ]),
                ],
            ),
        ],
    )
