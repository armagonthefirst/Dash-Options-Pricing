from dash import html, register_page


register_page(
    __name__,
    path="/methodology",
    name="Methodology",
    title="Methodology | Live Stock Options Pricing Dashboard",
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
                            "The idea behind this app is pretty simple: pull live "
                            "market data for a handful of popular stocks and ETFs, "
                            "run my own pricing model on their options, and see how "
                            "my prices compare to what the market is actually charging."
                        ),
                        (
                            "The typical flow is: browse the screener to spot "
                            "interesting volatility signals, click into a ticker to "
                            "explore its volatility charts and option chain, then pick "
                            "a specific contract to see how my model values it versus "
                            "the market price."
                        ),
                    ]),

                    # -- 2. Data Pipeline ------------------------------------
                    _section("2. Where the data comes from", [
                        (
                            "All of the live market data comes from Yahoo Finance "
                            "through a Python library called yfinance. It's not "
                            "Bloomberg-grade data, but it's free, it's real, and it's "
                            "good enough to build something meaningful on top of."
                        ),
                        (
                            "For each ticker I pull about a year of daily price "
                            "history (open, high, low, close, volume) and compute "
                            "things like moving averages and rolling realized "
                            "volatility from that."
                        ),
                        (
                            "Option chains are fetched per expiry date. Each contract "
                            "gets a few computed fields: days to expiry, moneyness "
                            "(how far the strike is from the current price), a "
                            "midpoint price from the bid and ask, and implied "
                            "volatility."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "What happens outside market hours?\n"
                                "When the market is closed, Yahoo Finance often "
                                "returns zeros for bid and ask. When that happens, "
                                "I fall back to the last traded price and back-solve "
                                "implied volatility using my binomial pricing model. "
                                "It's a workaround, but it keeps the app functional "
                                "24/7."
                            ),
                        ),
                        (
                            "Everything gets cached in memory once it's loaded. So "
                            "the first page load might take a few seconds while it "
                            "fetches from Yahoo, but after that it's instant until "
                            "the cache refreshes."
                        ),
                    ]),

                    # -- 3. Universe -----------------------------------------
                    _section("3. Which stocks are covered", [
                        (
                            "I picked 10 of the most actively traded U.S. stocks "
                            "and ETFs: SPY, QQQ, IWM, AAPL, MSFT, NVDA, AMZN, META, "
                            "TSLA, and AMD. These all have deep options markets with "
                            "tight spreads and lots of open interest, which means the "
                            "data is clean and the prices are reliable."
                        ),
                        (
                            "For now the app only covers simple single-leg calls and "
                            "puts across weekly and monthly expiries. No spreads, no "
                            "LEAPS, no multi-leg strategies - keeping it focused on "
                            "the core pricing problem."
                        ),
                    ]),

                    # -- 4. Volatility Forecasting ---------------------------
                    _section("4. Volatility forecasting", [
                        (
                            "This is the part I plan to improve the most. Right now "
                            "the volatility forecast is a simple placeholder - it "
                            "blends recent realized volatility numbers together with "
                            "a small per-ticker adjustment. The whole point is that "
                            "this function can be swapped out for a proper ML model "
                            "later without changing anything else in the app."
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
                            "The idea is straightforward: weight recent volatility "
                            "more heavily (65% on the 20-day window) since it "
                            "captures the current regime, but blend in the longer "
                            "60-day window (35%) to smooth out short-term noise. "
                            "The ticker bias accounts for the fact that some stocks "
                            "tend to mean-revert faster than others."
                        ),
                        (
                            "The forecast is clamped between 8% and 120% annualized "
                            "so it never feeds something unreasonable into the "
                            "pricing model."
                        ),
                    ]),

                    # -- 5. Implied Volatility -------------------------------
                    _section("5. Implied volatility", [
                        (
                            "Implied volatility (IV) is basically the market's best "
                            "guess at how much a stock will move. It's backed out of "
                            "the option's price - if the option is expensive, IV is "
                            "high, and vice versa."
                        ),
                        (
                            "I use ATM (at-the-money) implied volatility from the "
                            "expiry closest to 30 days out as the main market "
                            "reference. This gives a clean, comparable number across "
                            "all 10 tickers."
                        ),
                        (
                            "The key signal on the screener is the spread between "
                            "ATM IV and my forecast. If IV is higher than my "
                            "forecast, the market is pricing in more risk than my "
                            "model expects. If it's lower, the market might be "
                            "underpricing risk. Either way, it's worth investigating."
                        ),
                    ]),

                    # -- 6. Pricing Models -----------------------------------
                    _section("6. How options are priced", [
                        (
                            "The app runs two pricing models side by side. The main "
                            "one is a binomial tree (specifically the Cox-Ross-"
                            "Rubinstein model), and the secondary benchmark is "
                            "Black-Scholes."
                        ),
                        html.Div(
                            className="method-formula",
                            children=(
                                "Binomial tree - the short version:\n\n"
                                "Imagine the stock price can go up or down at each "
                                "time step. Build a tree of all possible paths from "
                                "now to expiry, calculate the option payoff at every "
                                "endpoint, then work backwards to today, checking at "
                                "each step whether it's better to exercise early or "
                                "keep holding.\n\n"
                                "That's it. The math handles American-style options "
                                "(where you can exercise any time) which is what all "
                                "U.S. stock options are."
                            ),
                        ),
                        (
                            "The theoretical price plugs my forecast volatility into "
                            "the binomial tree. The benchmark price plugs the "
                            "contract's own implied volatility into Black-Scholes. "
                            "Comparing the two isolates how much of the pricing gap "
                            "comes from my vol forecast versus the model itself."
                        ),
                        (
                            "Black-Scholes assumes you can only exercise at expiry "
                            "(European-style), so for puts especially, the binomial "
                            "price will be slightly higher since it accounts for the "
                            "option to exercise early."
                        ),
                    ]),

                    # -- 7. Greeks -------------------------------------------
                    _section("7. Greeks", [
                        (
                            "Greeks measure how sensitive an option's price is to "
                            "changes in different inputs. Think of them as the "
                            "option's vital signs."
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
                            "Right now the Greeks are calculated using Black-Scholes "
                            "closed-form formulas, which is standard practice and "
                            "gives good results for near-ATM contracts. A future "
                            "upgrade would compute them from the binomial tree "
                            "directly for better accuracy on deep ITM/OTM options."
                        ),
                    ]),

                    # -- 8. Sensitivity Analysis -----------------------------
                    _section("8. Sensitivity charts", [
                        (
                            "On the contract analysis page there are two sensitivity "
                            "charts: one that shows how the option's value changes "
                            "as volatility moves, and another that shows how it "
                            "changes as the stock price moves."
                        ),
                        (
                            "Each chart varies one input across a range while holding "
                            "everything else fixed, and runs the binomial pricer at "
                            "each point. This gives you a visual feel for how "
                            "exposed the option is to different scenarios."
                        ),
                    ]),

                    # -- 9. Limitations --------------------------------------
                    _section("9. Limitations", [
                        (
                            "This is a personal project and analytical tool, not "
                            "a trading system. A few important caveats:"
                        ),
                        html.Ul(
                            className="method-list",
                            children=[
                                html.Li(
                                    "The volatility forecast is a simple weighted "
                                    "average, not a trained ML model (yet)"
                                ),
                                html.Li(
                                    "Dividend yield is assumed to be zero for all "
                                    "tickers"
                                ),
                                html.Li(
                                    "The risk-free rate is hardcoded at 4%"
                                ),
                                html.Li(
                                    "Greeks use European-style (Black-Scholes) "
                                    "approximations"
                                ),
                                html.Li(
                                    "Off-hours data may be stale since Yahoo "
                                    "Finance doesn't update in real time"
                                ),
                            ],
                        ),
                        (
                            "Any pricing gap between my model and the market should "
                            "be treated as a signal worth investigating, not as a "
                            "direct trade recommendation."
                        ),
                    ]),
                ],
            ),
        ],
    )
