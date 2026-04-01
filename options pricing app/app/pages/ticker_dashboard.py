from __future__ import annotations

from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html, no_update, register_page

from data.data_source import (
    get_default_expiry,
    get_expiry_choices,
    get_filtered_option_chain,
    get_iv_smile,
    get_iv_term_structure,
    get_price_chart_frame,
    get_supported_tickers,
    get_ticker_kpis,
    get_volatility_chart_frame,
)


register_page(
    __name__,
    path="/ticker-dashboard",
    name="Ticker Dashboard",
    title="Ticker Dashboard | Live Options Pricing Dashboard",
)


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def format_signed_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def get_valid_ticker(requested_ticker: str | None) -> str:
    supported = {item["ticker"] for item in get_supported_tickers()}
    if requested_ticker in supported:
        return requested_ticker
    return "SPY"


def build_kpi_card(
    label: str,
    value: str,
    subtext: str | None = None,
    accent_class: str = "",
) -> html.Div:
    class_name = "kpi-card"
    if accent_class:
        class_name += f" {accent_class}"

    children = [
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value"),
    ]

    if subtext:
        children.append(html.Div(subtext, className="kpi-subtext"))

    return html.Div(className=class_name, children=children)


def build_kpi_grid(kpis: dict) -> list[html.Div]:
    return [
        build_kpi_card("Spot Price", format_currency(kpis["spot_price"])),
        build_kpi_card(
            "1D Return",
            format_signed_pct(kpis["price_change_1d"]),
            accent_class="positive" if kpis["price_change_1d"] >= 0 else "negative",
        ),
        build_kpi_card("20D Realized Vol", format_pct(kpis["rv20"])),
        build_kpi_card("60D Realized Vol", format_pct(kpis["rv60"])),
        build_kpi_card("20D Forecast Vol", format_pct(kpis["forecast_vol_20d"])),
        build_kpi_card(
            "ATM Implied Vol",
            format_pct(kpis["atm_iv_30d"]),
            subtext=f"IV - Forecast Spread: {format_signed_pct(kpis['iv_forecast_spread'])}",
        ),
    ]


def make_empty_figure(title: str, message: str = "Live data unavailable") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        title=title,
        margin=dict(l=30, r=20, t=55, b=30),
        height=320,
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
            )
        ],
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def make_price_figure(ticker: str) -> go.Figure:
    df = get_price_chart_frame(ticker, display_window=252).copy()

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["ma20"],
            mode="lines",
            name="20D MA",
            line=dict(width=1.8),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["ma60"],
            mode="lines",
            name="60D MA",
            line=dict(width=1.8, dash="dot"),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Price History",
        xaxis_title="Date",
        yaxis_title="Price",
        margin=dict(l=30, r=20, t=55, b=30),
        height=430,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return fig


def make_volatility_figure(ticker: str) -> go.Figure:
    history_df = get_volatility_chart_frame(ticker, display_window=252)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=history_df["Date"],
            y=history_df["rv20"],
            mode="lines",
            name="20D Realized Vol",
            line=dict(width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=history_df["Date"],
            y=history_df["rv60"],
            mode="lines",
            name="60D Realized Vol",
            line=dict(width=2, dash="dot"),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Rolling Volatility Regime",
        xaxis_title="Date",
        yaxis_title="Annualized Volatility",
        margin=dict(l=30, r=20, t=55, b=30),
        height=360,
        legend=dict(orientation="h", y=1.08, x=0),
    )
    fig.update_yaxes(tickformat=".0%")
    return fig


def make_term_structure_figure(ticker: str) -> go.Figure:
    df = get_iv_term_structure(ticker).copy()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["dte"],
            y=df["atm_iv"],
            mode="lines+markers",
            name="ATM IV",
            line=dict(width=2.5),
            text=df["expiry"],
            hovertemplate="DTE: %{x}<br>Expiry: %{text}<br>ATM IV: %{y:.2%}<extra></extra>",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="ATM IV Term Structure",
        xaxis_title="Days to Expiry",
        yaxis_title="Implied Volatility",
        margin=dict(l=30, r=20, t=55, b=30),
        height=320,
        showlegend=False,
    )
    fig.update_yaxes(tickformat=".0%")
    return fig


def make_smile_figure(ticker: str, expiry: str) -> go.Figure:
    df = get_iv_smile(ticker, expiry).copy()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["moneyness"],
            y=df["call_iv"],
            mode="lines+markers",
            name="Calls",
            line=dict(width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["moneyness"],
            y=df["put_iv"],
            mode="lines+markers",
            name="Puts",
            line=dict(width=2, dash="dot"),
        )
    )

    dte = int(df["dte"].iloc[0]) if not df.empty else 0

    fig.update_layout(
        template="plotly_dark",
        title=f"IV Smile / Skew ({dte} DTE)",
        xaxis_title="Moneyness (K / S)",
        yaxis_title="Implied Volatility",
        margin=dict(l=30, r=20, t=55, b=30),
        height=320,
        legend=dict(orientation="h", y=1.08, x=0),
    )
    fig.update_yaxes(tickformat=".0%")
    return fig


def build_dashboard_error_state(message: str) -> html.Div:
    return html.Div(
        className="empty-state",
        children=f"Live data temporarily unavailable: {message}",
    )


def build_chain_table(ticker: str, chain_df: pd.DataFrame) -> html.Div:
    if chain_df.empty:
        return html.Div(
            className="empty-state",
            children="No contracts match the selected filters.",
        )

    header = html.Thead(
        html.Tr(
            [
                html.Th("Type"),
                html.Th("Strike"),
                html.Th("Expiry"),
                html.Th("DTE"),
                html.Th("Bid"),
                html.Th("Ask"),
                html.Th("Mid"),
                html.Th("Volume"),
                html.Th("OI"),
                html.Th("IV"),
                html.Th("Moneyness"),
                html.Th(""),
            ]
        )
    )

    body_rows = []
    for row in chain_df.itertuples(index=False):
        contract_id_encoded = quote(str(row.contract_id), safe="")
        analyze_href = f"/contract-analysis?ticker={ticker}&contract_id={contract_id_encoded}"

        body_rows.append(
            html.Tr(
                [
                    html.Td(row.type),
                    html.Td(format_currency(row.strike)),
                    html.Td(row.expiry),
                    html.Td(int(row.dte)),
                    html.Td(format_currency(row.bid)),
                    html.Td(format_currency(row.ask)),
                    html.Td(format_currency(row.mid)),
                    html.Td(f"{int(row.volume):,}"),
                    html.Td(f"{int(row.open_interest):,}"),
                    html.Td(format_pct(row.iv)),
                    html.Td(f"{row.moneyness:.3f}x"),
                    html.Td("Analyse ↗", className="chain-row-cta"),
                ],
                **{"data-href": analyze_href},
            )
        )

    return html.Div(
        className="table-wrapper",
        children=[
            html.Table(
                className="chain-table",
                children=[header, html.Tbody(body_rows)],
            )
        ],
    )


def build_ticker_selector(current_ticker: str) -> html.Div:
    ticker_options = [
        {"label": f"{item['ticker']} — {item['name']}", "value": item["ticker"]}
        for item in get_supported_tickers()
    ]

    return html.Div(
        className="header-control-block",
        children=[
            html.Div("Ticker", className="control-label"),
            dcc.Dropdown(
                id="dashboard-ticker-dropdown",
                options=ticker_options,
                value=current_ticker,
                clearable=False,
                className="dashboard-dropdown",
            ),
        ],
    )


def layout(ticker: str | None = None, **kwargs) -> html.Div:
    ticker = get_valid_ticker(ticker)

    try:
        kpis = get_ticker_kpis(ticker)
        default_expiry = kpis["default_expiry"]
        expiry_options = get_expiry_choices(ticker)
        initial_chain = get_filtered_option_chain(
            ticker=ticker,
            expiry=default_expiry,
            option_type="both",
            moneyness_bucket="0.85-1.15",
            sort_by="strike",
        )
        initial_summary = (
            f"{len(initial_chain)} contracts shown | "
            f"Expiry: {default_expiry} | "
            "Type: Both"
        )

        page_description = (
            f"{kpis['name']} | Ticker-level volatility context, "
            "implied volatility structure, and option-chain exploration."
        )
        last_refresh = kpis["last_refresh"]
        kpi_children = build_kpi_grid(kpis)
        price_figure = make_price_figure(ticker)
        vol_figure = make_volatility_figure(ticker)
        term_figure = make_term_structure_figure(ticker)
        smile_figure = make_smile_figure(ticker, default_expiry)
        chain_children = build_chain_table(ticker, initial_chain)
    except Exception as exc:
        default_expiry = None
        expiry_options = []
        initial_summary = "Live data temporarily unavailable."
        page_description = "Ticker-level volatility context is temporarily unavailable."
        last_refresh = "Unavailable"
        kpi_children = [
            build_kpi_card(
                "Live Data Status",
                "Unavailable",
                subtext="Try refreshing the page or switching ticker.",
                accent_class="negative",
            )
        ]
        price_figure = make_empty_figure("Price History")
        vol_figure = make_empty_figure("Rolling Volatility Regime")
        term_figure = make_empty_figure("ATM IV Term Structure")
        smile_figure = make_empty_figure("IV Smile / Skew")
        chain_children = build_dashboard_error_state(str(exc))

    return html.Div(
        className="page ticker-dashboard-page",
        children=[
            dcc.Store(id="dashboard-ticker-store", data=ticker),
            html.Div(
                className="page-header dashboard-header",
                children=[
                    html.Div(
                        className="page-header-copy",
                        children=[
                            html.Div(
                                className="breadcrumbs",
                                id="dashboard-breadcrumbs",
                                children=[
                                    dcc.Link("Screener", href="/"),
                                    html.Span(">", className="breadcrumb-sep"),
                                    html.Span(f"{ticker} Dashboard"),
                                ],
                            ),
                            html.H1(
                                f"{ticker} Dashboard",
                                id="dashboard-page-title",
                                className="page-title",
                            ),
                            html.P(
                                page_description,
                                id="dashboard-page-description",
                                className="page-description",
                            ),
                        ],
                    ),
                    html.Div(
                        className="dashboard-header-right",
                        children=[
                            build_ticker_selector(ticker),
                        ],
                    ),
                    # Hidden element to satisfy callback output
                    html.Div(id="dashboard-last-refresh", style={"display": "none"}),
                ],
            ),
            html.Div(
                id="dashboard-kpi-grid",
                className="kpi-grid",
                children=kpi_children,
            ),
            html.Div(
                className="section-card chart-tabs-container",
                children=[
                    dcc.Tabs(
                        id="dashboard-chart-tabs",
                        value="price",
                        children=[
                            dcc.Tab(
                                label="Price & Volume",
                                value="price",
                                className="tab",
                                selected_className="tab tab--selected",
                                children=[
                                    html.Div(
                                        className="tab-content",
                                        children=[
                                            dcc.Graph(
                                                id="price-history-chart",
                                                figure=price_figure,
                                                config={"displayModeBar": False},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="Volatility",
                                value="volatility",
                                className="tab",
                                selected_className="tab tab--selected",
                                children=[
                                    html.Div(
                                        className="tab-content",
                                        children=[
                                            dcc.Graph(
                                                id="volatility-regime-chart",
                                                figure=vol_figure,
                                                config={"displayModeBar": False},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="IV Structure",
                                value="iv-structure",
                                className="tab",
                                selected_className="tab tab--selected",
                                children=[
                                    html.Div(
                                        className="tab-content",
                                        children=[
                                            html.Div(
                                                className="chart-grid chart-grid-bottom",
                                                children=[
                                                    html.Div(
                                                        className="chart-card",
                                                        children=[
                                                            dcc.Graph(
                                                                id="term-structure-chart",
                                                                figure=term_figure,
                                                                config={"displayModeBar": False},
                                                            ),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        className="chart-card",
                                                        children=[
                                                            dcc.Graph(
                                                                id="iv-smile-chart",
                                                                figure=smile_figure,
                                                                config={"displayModeBar": False},
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card chain-section",
                children=[
                    html.Div(
                        className="section-header",
                        children=[
                            html.Div(
                                children=[
                                    html.H2("Option Chain", className="section-title"),
                                    html.P(
                                        "Here are the available options contracts for this stock. "
                                        "Click any row to see its detailed pricing analysis.",
                                        className="section-description",
                                    ),
                                ]
                            ),
                            html.Div(
                                id="chain-summary-text",
                                className="chain-summary-text",
                                children=initial_summary,
                            ),
                        ],
                    ),
                    html.Div(
                        className="chain-control-grid",
                        children=[
                            html.Div(
                                className="control-block",
                                children=[
                                    html.Div("Expiry", className="control-label"),
                                    dcc.Dropdown(
                                        id="dashboard-expiry-dropdown",
                                        options=expiry_options,
                                        value=default_expiry,
                                        clearable=False,
                                        className="dashboard-dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-block",
                                children=[
                                    html.Div("Option Type", className="control-label"),
                                    dcc.RadioItems(
                                        id="dashboard-type-radio",
                                        options=[
                                            {"label": "Both", "value": "both"},
                                            {"label": "Calls", "value": "calls"},
                                            {"label": "Puts", "value": "puts"},
                                        ],
                                        value="both",
                                        className="dashboard-radio-group",
                                        inputClassName="dashboard-radio-input",
                                        labelClassName="dashboard-radio-label",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-block",
                                children=[
                                    html.Div("Moneyness Range", className="control-label"),
                                    dcc.Dropdown(
                                        id="dashboard-moneyness-dropdown",
                                        options=[
                                            {"label": "0.90x to 1.10x", "value": "0.90-1.10"},
                                            {"label": "0.85x to 1.15x", "value": "0.85-1.15"},
                                            {"label": "All displayed strikes", "value": "all"},
                                        ],
                                        value="0.85-1.15",
                                        clearable=False,
                                        className="dashboard-dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-block",
                                children=[
                                    html.Div("Sort By", className="control-label"),
                                    dcc.Dropdown(
                                        id="dashboard-sort-dropdown",
                                        options=[
                                            {"label": "Strike", "value": "strike"},
                                            {"label": "Volume", "value": "volume"},
                                            {"label": "Open Interest", "value": "open_interest"},
                                            {"label": "Implied Volatility", "value": "iv"},
                                        ],
                                        value="strike",
                                        clearable=False,
                                        className="dashboard-dropdown",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(id="option-chain-container", children=chain_children),
                ],
            ),
        ],
    )


@callback(
    Output("dashboard-ticker-store", "data"),
    Input("dashboard-ticker-dropdown", "value"),
)
def sync_ticker_store(ticker_value: str) -> str:
    return get_valid_ticker(ticker_value)


@callback(
    Output("dashboard-breadcrumbs", "children"),
    Output("dashboard-page-title", "children"),
    Output("dashboard-page-description", "children"),
    Output("dashboard-last-refresh", "children"),
    Output("dashboard-kpi-grid", "children"),
    Output("dashboard-expiry-dropdown", "options"),
    Output("dashboard-expiry-dropdown", "value"),
    Output("price-history-chart", "figure"),
    Output("volatility-regime-chart", "figure"),
    Output("term-structure-chart", "figure"),
    Input("dashboard-ticker-store", "data"),
)
def update_ticker_content(ticker: str):
    """Fires only when the ticker changes — rebuilds KPIs and charts."""
    ticker = get_valid_ticker(ticker)

    breadcrumbs = [
        dcc.Link("Screener", href="/"),
        html.Span(">", className="breadcrumb-sep"),
        html.Span(f"{ticker} Dashboard"),
    ]

    try:
        kpis = get_ticker_kpis(ticker)
        expiry_options = get_expiry_choices(ticker)
        default_expiry = get_default_expiry(ticker)

        return (
            breadcrumbs,
            f"{ticker} Dashboard",
            f"{kpis['name']} | Ticker-level volatility context, implied volatility structure, and option-chain exploration.",
            kpis["last_refresh"],
            build_kpi_grid(kpis),
            expiry_options,
            default_expiry,
            make_price_figure(ticker),
            make_volatility_figure(ticker),
            make_term_structure_figure(ticker),
        )
    except Exception as exc:
        return (
            breadcrumbs,
            f"{ticker} Dashboard",
            "Live data temporarily unavailable.",
            "Unavailable",
            [
                build_kpi_card(
                    "Live Data Status",
                    "Unavailable",
                    subtext="Previous data may be stale. Try refreshing.",
                    accent_class="negative",
                )
            ],
            no_update,
            no_update,
            make_empty_figure("Price History"),
            make_empty_figure("Rolling Volatility Regime"),
            make_empty_figure("ATM IV Term Structure"),
        )


@callback(
    Output("iv-smile-chart", "figure"),
    Input("dashboard-ticker-store", "data"),
    Input("dashboard-expiry-dropdown", "value"),
)
def update_smile_chart(ticker: str, selected_expiry: str | None):
    """Fires when ticker or expiry changes — rebuilds IV smile only."""
    ticker = get_valid_ticker(ticker)

    try:
        if not selected_expiry:
            selected_expiry = get_default_expiry(ticker)
        return make_smile_figure(ticker, selected_expiry)
    except Exception:
        return make_empty_figure("IV Smile / Skew")


@callback(
    Output("chain-summary-text", "children"),
    Output("option-chain-container", "children"),
    Input("dashboard-ticker-store", "data"),
    Input("dashboard-expiry-dropdown", "value"),
    Input("dashboard-type-radio", "value"),
    Input("dashboard-moneyness-dropdown", "value"),
    Input("dashboard-sort-dropdown", "value"),
)
def update_chain_table(
    ticker: str,
    selected_expiry: str | None,
    option_type: str,
    moneyness_bucket: str,
    sort_by: str,
):
    """Fires on any filter change — rebuilds option chain table only."""
    ticker = get_valid_ticker(ticker)

    try:
        if not selected_expiry:
            selected_expiry = get_default_expiry(ticker)

        filtered_chain = get_filtered_option_chain(
            ticker=ticker,
            expiry=selected_expiry,
            option_type=option_type,
            moneyness_bucket=moneyness_bucket,
            sort_by=sort_by,
        )

        summary_text = (
            f"{len(filtered_chain)} contracts shown | "
            f"Expiry: {selected_expiry} | "
            f"Type: {option_type.title()}"
        )

        return summary_text, build_chain_table(ticker, filtered_chain)
    except Exception as exc:
        return (
            f"Live data temporarily unavailable: {exc}",
            build_dashboard_error_state(str(exc)),
        )
