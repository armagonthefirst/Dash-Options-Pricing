from dash import dcc, html, register_page

from data.data_source import get_screener_data


register_page(
    __name__,
    path="/",
    name="Overview",
    title="Overview | Live Options Pricing Dashboard",
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


def build_ticker_card(row: dict, index: int) -> html.Div:
    change_class = "metric-value positive" if row["price_change_1d"] >= 0 else "metric-value negative"
    change_display_class = "positive" if row["price_change_1d"] >= 0 else "negative"
    spread_class = (
        "metric-value positive"
        if row["iv_forecast_spread"] >= 0
        else "metric-value negative"
    )

    spread_accent = "iv-positive" if row["iv_forecast_spread"] >= 0 else "iv-negative"

    return dcc.Link(
        href=f"/ticker-dashboard?ticker={row['ticker']}",
        style={"textDecoration": "none", "color": "inherit"},
        children=html.Div(
            className=f"ticker-card fade-in-card {spread_accent}",
            style={"--card-index": index},
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
                                    className=f"price-change-pill {change_display_class}",
                                ),
                            ],
                        ),
                    ],
                ),
                # Metrics hidden by default, revealed on hover via CSS
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
                html.Div("Analyse ↗", className="ticker-card-cta"),
            ],
        ),
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
            children=[build_ticker_card(row, i) for i, row in enumerate(screener_rows)],
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
                            html.H1("Welcome to my options pricing dashboard!", className="page-title"),
                            html.P(
                                (
                                    "This app pulls live market data for 10 of the most actively "
                                    "traded U.S. stocks and ETFs, refreshing every hour. Click on "
                                    "any ticker below to explore its volatility profile, option "
                                    "chain, and see how my pricing model compares to the market."
                                ),
                                className="page-description",
                            ),
                        ],
                    ),
                ],
            ),
            ticker_grid,
        ],
    )
