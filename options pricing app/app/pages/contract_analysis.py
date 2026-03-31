from __future__ import annotations

from urllib.parse import quote, unquote

import plotly.graph_objects as go
from dash import dcc, html, register_page

from data.data_source import (
    get_contract_snapshot,
    get_payoff_curve,
    get_sensitivity_curve,
    get_supported_tickers,
)


register_page(
    __name__,
    path="/contract-analysis",
    name="Contract Analysis",
    title="Contract Analysis | Live Options Pricing Dashboard",
)


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def format_signed_currency(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}${value:,.2f}"


def format_signed_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def get_valid_ticker(requested_ticker: str | None) -> str:
    supported = {item["ticker"] for item in get_supported_tickers()}
    if requested_ticker in supported:
        return requested_ticker
    return "SPY"


def build_stat_card(
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


def build_detail_row(label: str, value: str) -> html.Div:
    return html.Div(
        className="detail-row",
        children=[
            html.Div(label, className="detail-label"),
            html.Div(value, className="detail-value"),
        ],
    )


def make_empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        title=title,
        margin=dict(l=30, r=20, t=55, b=30),
        height=340,
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
        showlegend=False,
    )
    return fig


def make_price_comparison_figure(snapshot: dict) -> go.Figure:
    labels = ["Market Mid", "Theoretical", "Black-Scholes"]
    values = [
        snapshot["mid"],
        snapshot["theoretical_price"],
        snapshot["benchmark_price"],
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                text=[format_currency(v) for v in values],
                textposition="outside",
                name="Price Comparison",
            )
        ]
    )

    fig.update_layout(
        template="plotly_dark",
        title="Contract Value Comparison",
        xaxis_title="Price Type",
        yaxis_title="Option Value",
        margin=dict(l=30, r=20, t=55, b=30),
        height=340,
        showlegend=False,
    )
    return fig


def make_payoff_figure(ticker: str, contract_id: str | None) -> go.Figure:
    try:
        df = get_payoff_curve(ticker, contract_id).copy()
    except Exception as exc:
        return make_empty_figure("Payoff at Expiry", f"Unavailable: {exc}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["underlying_price"],
            y=df["pnl_at_expiry"],
            mode="lines",
            name="PnL at Expiry",
            line=dict(width=2.5),
        )
    )

    fig.add_hline(y=0, line_width=1, line_dash="dash")
    fig.update_layout(
        template="plotly_dark",
        title="Payoff at Expiry",
        xaxis_title="Underlying Price at Expiry",
        yaxis_title="PnL",
        margin=dict(l=30, r=20, t=55, b=30),
        height=340,
        showlegend=False,
    )
    return fig


def make_vol_sensitivity_figure(ticker: str, contract_id: str | None) -> go.Figure:
    try:
        df = get_sensitivity_curve(ticker, contract_id, sensitivity_type="vol").copy()
    except Exception as exc:
        return make_empty_figure("Option Value vs Volatility", f"Unavailable: {exc}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["volatility"],
            y=df["option_value"],
            mode="lines",
            name="Vol Sensitivity",
            line=dict(width=2.5),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Option Value vs Volatility",
        xaxis_title="Implied Volatility",
        yaxis_title="Option Value",
        margin=dict(l=30, r=20, t=55, b=30),
        height=340,
        showlegend=False,
    )
    fig.update_xaxes(tickformat=".0%")
    return fig


def make_spot_sensitivity_figure(ticker: str, contract_id: str | None) -> go.Figure:
    try:
        df = get_sensitivity_curve(ticker, contract_id, sensitivity_type="spot").copy()
    except Exception as exc:
        return make_empty_figure("Option Value vs Underlying Price", f"Unavailable: {exc}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["underlying_price"],
            y=df["option_value"],
            mode="lines",
            name="Spot Sensitivity",
            line=dict(width=2.5),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Option Value vs Underlying Price",
        xaxis_title="Underlying Price",
        yaxis_title="Option Value",
        margin=dict(l=30, r=20, t=55, b=30),
        height=340,
        showlegend=False,
    )
    return fig


def safe_snapshot(ticker: str, contract_id: str | None) -> dict:
    try:
        return get_contract_snapshot(ticker, contract_id)
    except Exception:
        return get_contract_snapshot(ticker, None)


def layout(ticker: str | None = None, contract_id: str | None = None, **kwargs) -> html.Div:
    ticker = get_valid_ticker(ticker)
    decoded_contract_id = unquote(contract_id) if contract_id else None

    snapshot = safe_snapshot(ticker, decoded_contract_id)
    selected_contract_id = snapshot["contract_id"]
    dashboard_href = f"/ticker-dashboard?ticker={ticker}"
    reload_href = (
        f"/contract-analysis?ticker={ticker}&contract_id="
        f"{quote(selected_contract_id, safe='')}"
    )

    gap_class = "positive" if snapshot["pricing_gap"] >= 0 else "negative"

    contract_title = (
        f"{snapshot['ticker']} {snapshot['type']} | "
        f"{format_currency(snapshot['strike'])} | "
        f"{snapshot['expiry']}"
    )

    return html.Div(
        className="page contract-analysis-page",
        children=[
            html.Div(
                className="page-header dashboard-header",
                children=[
                    html.Div(
                        className="page-header-copy",
                        children=[
                            html.Div(
                                className="breadcrumbs",
                                children=[
                                    dcc.Link("Screener", href="/"),
                                    html.Span(">", className="breadcrumb-sep"),
                                    dcc.Link(f"{ticker} Dashboard", href=dashboard_href),
                                    html.Span(">", className="breadcrumb-sep"),
                                    html.Span(contract_title),
                                ],
                            ),
                            html.H1(contract_title, className="page-title"),
                            html.P(
                                (
                                    "Single-contract valuation view with live market quote context, "
                                    "theoretical pricing, Greeks, and sensitivity charts."
                                ),
                                className="page-description",
                            ),
                        ],
                    ),
                    html.Div(
                        className="dashboard-header-right",
                        children=[
                            html.Div(
                                className="header-note-card",
                                children=[
                                    html.Div("Contract ID", className="note-label"),
                                    html.Div(selected_contract_id, className="note-value"),
                                ],
                            ),
                            dcc.Link(
                                "Reload Contract View",
                                href=reload_href,
                                className="card-button",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="kpi-grid",
                children=[
                    build_stat_card("Market Mid", format_currency(snapshot["mid"])),
                    build_stat_card(
                        "Theoretical Price",
                        format_currency(snapshot["theoretical_price"]),
                        subtext="American binomial (CRR, 200 steps) with forecast vol",
                    ),
                    build_stat_card(
                        "Black-Scholes Benchmark",
                        format_currency(snapshot["benchmark_price"]),
                    ),
                    build_stat_card(
                        "Pricing Gap",
                        format_signed_currency(snapshot["pricing_gap"]),
                        subtext=f"{format_signed_pct(snapshot['pricing_gap_pct'])} vs market mid",
                        accent_class=gap_class,
                    ),
                    build_stat_card("Implied Volatility", format_pct(snapshot["iv"])),
                    build_stat_card("Days to Expiry", f"{snapshot['dte']}"),
                ],
            ),
            html.Div(
                className="chart-grid chart-grid-top",
                children=[
                    html.Div(
                        className="section-card chart-card",
                        children=[
                            dcc.Graph(
                                figure=make_price_comparison_figure(snapshot),
                                config={"displayModeBar": False},
                            )
                        ],
                    ),
                    html.Div(
                        className="section-card details-card",
                        children=[
                            html.Div(
                                className="section-header",
                                children=[
                                    html.H2("Contract Details", className="section-title"),
                                    html.P(
                                        "Market quote snapshot and contract attributes.",
                                        className="section-description",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="details-grid",
                                children=[
                                    build_detail_row("Ticker", snapshot["ticker"]),
                                    build_detail_row("Type", snapshot["type"]),
                                    build_detail_row("Expiry", snapshot["expiry"]),
                                    build_detail_row("Strike", format_currency(snapshot["strike"])),
                                    build_detail_row("Spot", format_currency(snapshot["spot"])),
                                    build_detail_row("Moneyness", f"{snapshot['moneyness']:.3f}x"),
                                    build_detail_row("Bid", format_currency(snapshot["bid"])),
                                    build_detail_row("Ask", format_currency(snapshot["ask"])),
                                    build_detail_row("Mid", format_currency(snapshot["mid"])),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="greeks-grid",
                children=[
                    build_stat_card(
                        "Delta",
                        f"{snapshot['delta']:.3f}",
                        subtext=f"Price moves ~${abs(snapshot['delta']):.2f} per $1 move in {ticker}",
                    ),
                    build_stat_card(
                        "Gamma",
                        f"{snapshot['gamma']:.4f}",
                        subtext=f"Delta changes by {snapshot['gamma']:.4f} per $1 move",
                    ),
                    build_stat_card(
                        "Theta",
                        f"{snapshot['theta']:.4f}",
                        subtext=f"Loses ~${abs(snapshot['theta']):.4f} per day",
                    ),
                    build_stat_card(
                        "Vega",
                        f"{snapshot['vega']:.4f}",
                        subtext=f"Price changes ~${abs(snapshot['vega']):.4f} per 1% vol move",
                    ),
                ],
            ),
            html.Div(
                className="section-card chart-tabs-container",
                children=[
                    dcc.Tabs(
                        value="payoff",
                        children=[
                            dcc.Tab(
                                label="Payoff at Expiry",
                                value="payoff",
                                className="tab",
                                selected_className="tab tab--selected",
                                children=[
                                    html.Div(
                                        className="tab-content",
                                        children=[
                                            dcc.Graph(
                                                figure=make_payoff_figure(ticker, selected_contract_id),
                                                config={"displayModeBar": False},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="Vol Sensitivity",
                                value="vol-sens",
                                className="tab",
                                selected_className="tab tab--selected",
                                children=[
                                    html.Div(
                                        className="tab-content",
                                        children=[
                                            dcc.Graph(
                                                figure=make_vol_sensitivity_figure(ticker, selected_contract_id),
                                                config={"displayModeBar": False},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dcc.Tab(
                                label="Spot Sensitivity",
                                value="spot-sens",
                                className="tab",
                                selected_className="tab tab--selected",
                                children=[
                                    html.Div(
                                        className="tab-content",
                                        children=[
                                            dcc.Graph(
                                                figure=make_spot_sensitivity_figure(ticker, selected_contract_id),
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
    )
