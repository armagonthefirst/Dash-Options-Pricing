from dash import dcc, html, page_container, page_registry


APP_TITLE = "Options Pricing ML App"
APP_SUBTITLE = (
    "Volatility forecasting, option valuation, and market-vs-model analytics "
    "for liquid U.S. equities and ETFs."
)


def build_nav_links():
    """
    Build navigation links from Dash's page registry.
    Home (/) is shown first, then the remaining pages alphabetically.
    """
    if not page_registry:
        return [
            html.Span(
                "Navigation will appear once pages are added.",
                className="nav-placeholder",
            )
        ]

    pages = sorted(
        page_registry.values(),
        key=lambda page: (0 if page["path"] == "/" else 1, page["name"]),
    )

    return [
        dcc.Link(
            page["name"],
            href=page["path"],
            className="nav-link",
        )
        for page in pages
    ]


def create_layout():
    return html.Div(
        className="app-shell",
        children=[
            html.Header(
                className="app-header",
                children=[
                    html.Div(
                        className="header-left",
                        children=[
                            html.H1(APP_TITLE, className="app-title"),
                            html.P(APP_SUBTITLE, className="app-subtitle"),
                        ],
                    ),
                    html.Div(
                        className="header-right",
                        children=[
                            html.Div(
                                className="header-badge",
                                children="Dash Prototype",
                            )
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
                    page_container
                ],
            ),
        ],
    )