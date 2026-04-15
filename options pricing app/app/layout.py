from dash import dcc, html, page_container, page_registry


APP_TITLE = "Stock Options Pricing Dashboard"


def build_nav_links():
    # Only show Overview (home) and Methodology in the nav bar.
    # Ticker Dashboard and Contract Analysis are reached through the app flow.
    NAV_PAGES = {"/", "/methodology"}

    if not page_registry:
        return [
            html.Span(
                "Navigation will appear once pages are added.",
                className="nav-placeholder",
            )
        ]

    pages = sorted(
        (p for p in page_registry.values() if p["path"] in NAV_PAGES),
        key=lambda page: (0 if page["path"] == "/" else 1, page["name"]),
    )

    return [
        dcc.Link(
            page["name"],
            href=page["path"],
            className="nav-link",
        )
        for page in pages
    ] + [
        html.A(
            "About Me",
            href="https://www.shariqusoof.com",
            target="_blank",
            rel="noopener noreferrer",
            className="nav-link",
        )
    ]


def _market_status_badge():
    """
    Returns a badge showing market open/closed status.
    Uses a clientside callback or static check.
    """
    return html.Div(
        id="market-status-badge",
        className="market-status-badge market-closed",
        children=[
            html.Span(className="status-dot"),
            html.Span("Market Closed", id="market-status-text"),
        ],
    )


def create_layout():
    return html.Div(
        className="app-shell",
        children=[
            html.Div(className="aurora-bg"),
            html.Header(
                className="app-header",
                children=[
                    html.Div(
                        className="header-left",
                        children=[
                            html.H1(APP_TITLE, className="app-title"),
                        ],
                    ),
                    html.Div(
                        className="header-right",
                        children=[
                            _market_status_badge(),
                        ],
                    ),
                ],
            ),
            html.Nav(
                className="app-nav",
                children=build_nav_links(),
            ),
            html.Main(
                className="app-main",
                children=[
                    html.Div(
                        id="page-loading-overlay",
                        className="page-loading-overlay",
                        children=[
                            html.Div(className="loading-spinner"),
                            html.Div(
                                "Fetching market data...",
                                id="page-loading-text",
                                className="loading-text",
                            ),
                        ],
                    ),
                    page_container,
                ],
            ),
            html.Footer(
                className="app-footer",
                children=[
                    html.Span("Data sourced from Yahoo Finance", className="footer-item"),
                ],
            ),
        ],
    )
