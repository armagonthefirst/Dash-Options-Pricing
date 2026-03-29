from pathlib import Path

from dash import Dash

from layout import create_layout

# Resolve project paths
APP_DIR = Path(__file__).resolve().parent
PAGES_DIR = APP_DIR / "pages"
ASSETS_DIR = APP_DIR.parent / "assets"

app = Dash(
    __name__,
    use_pages=True,
    pages_folder=str(PAGES_DIR),
    assets_folder=str(ASSETS_DIR),
    suppress_callback_exceptions=True,
    title="Options Pricing ML App",
)

server = app.server

# Use a callable layout so Dash rebuilds it cleanly on refresh
app.layout = create_layout


if __name__ == "__main__":
    app.run(debug=True)