from dash import dcc, html, register_page

from data.data_source import get_screener_data


register_page(
    __name__,
    path="/",
    name="Market Screener",
    title="Market Screener | Options Pricing ML App",
)


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def format_signed_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def build_metric(label: str, value: str, value_class: str = "metric-value") -> html.Div:
    return html.Div(
        className="metric-block",
        children=[
            html.Div(label, className="metric-label"),
            html.Div(value, className=value_class),
        ],
    )


def build_ticker_card(row: dict) -> html.Div:
    change_class = "metric-value positive" if row["price_change_1d"] >= 0 else "metric-value negative"
    spread_class = (
        "metric-value positive"
        if row["iv_forecast_spread"] >= 0
        else "metric-value negative"
    )

    return html.Div(
        className="ticker-card",
        children=[
            html.Div(
                className="ticker-card-header",
                children=[
                    html.Div(
                        className="ticker-card-title-wrap",
                        children=[
                            html.H2(row["ticker"], className="ticker-symbol"),
                            html.P(row["name"], className="ticker-name"),
                        ],
                    ),
                    html.Div(
                        className="ticker-card-price-wrap",
                        children=[
                            html.Div(format_currency(row["spot_price"]), className="spot-price"),
                            html.Div(
                                format_signed_pct(row["price_change_1d"]),
                                className=change_class,
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="ticker-card-metrics",
                children=[
                    build_metric("20D Realized Vol", format_pct(row["rv20"])),
                    build_metric("20D Forecast Vol", format_pct(row["forecast_vol_20d"])),
                    build_metric("ATM Implied Vol", format_pct(row["atm_iv_30d"])),
                    build_metric(
                        "IV - Forecast Spread",
                        format_signed_pct(row["iv_forecast_spread"]),
                        spread_class,
                    ),
                ],
            ),
            html.Div(
                className="ticker-card-footer",
                children=[
                    html.Div(
                        className="ticker-card-meta",
                        children=f"Default expiry: {row['default_expiry']}",
                    ),
                    dcc.Link(
                        "Open Dashboard",
                        href=f"/ticker-dashboard?ticker={row['ticker']}",
                        className="card-button",
                    ),
                ],
            ),
        ],
    )


def build_screener_error_state(message: str) -> html.Div:
    return html.Div(
        className="section-card",
        children=[
            html.H2("Live Screener Unavailable", className="section-title"),
            html.P(
                "The live market feed could not be loaded right now.",
                className="section-description",
            ),
            html.Div(message, className="empty-state"),
        ],
    )


def layout() -> html.Div:
    try:
        screener_df = get_screener_data()
        screener_rows = screener_df.to_dict("records")
        universe_value = f"{len(screener_rows)} tickers"
        ticker_grid = html.Div(
            className="ticker-grid",
            children=[build_ticker_card(row) for row in screener_rows],
        )
    except Exception as exc:
        screener_rows = []
        universe_value = "Unavailable"
        ticker_grid = build_screener_error_state(str(exc))

    return html.Div(
        className="page screener-page",
        children=[
            html.Div(
                className="page-header",
                children=[
                    html.Div(
                        className="page-header-copy",
                        children=[
                            html.H1("Liquid U.S. Options Universe", className="page-title"),
                            html.P(
                                (
                                    "A curated view of highly liquid U.S. equities and ETFs. "
                                    "Ranked by the absolute difference between ATM implied volatility "
                                    "and the model's 20-day volatility forecast."
                                ),
                                className="page-description",
                            ),
                        ],
                    ),
                    html.Div(
                        className="page-header-note",
                        children=[
                            html.Div("Universe Size", className="note-label"),
                            html.Div(universe_value, className="note-value"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card screener-summary-card",
                children=[
                    html.Div(
                        className="summary-item",
                        children=[
                            html.Div("Sort Logic", className="summary-label"),
                            html.Div("|ATM IV - Forecast Vol| descending", className="summary-value"),
                        ],
                    ),
                    html.Div(
                        className="summary-item",
                        children=[
                            html.Div("Forecast Horizon", className="summary-label"),
                            html.Div("20 trading days", className="summary-value"),
                        ],
                    ),
                    html.Div(
                        className="summary-item",
                        children=[
                            html.Div("IV Reference", className="summary-label"),
                            html.Div("ATM IV near 30 DTE", className="summary-value"),
                        ],
                    ),
                ],
            ),
            ticker_grid,
        ],
    )
