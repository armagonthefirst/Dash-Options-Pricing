from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Thread
from time import sleep

from dash import Dash

from layout import create_layout
from data.analytics import clear_analytics_cache, get_live_ticker_kpis, get_live_iv_term_structure, get_live_iv_smile, TICKER_ORDER
from data.contract_analytics import clear_contract_analytics_cache
from data.market_data import clear_market_data_cache

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
    title="Stock Options Pricing Dashboard",
)

server = app.server

# Use a callable layout so Dash rebuilds it cleanly on refresh
app.layout = create_layout

# ---------------------------------------------------------------------------
# Periodic cache refresh
# ---------------------------------------------------------------------------
CACHE_REFRESH_SECONDS = 60 * 60  # 1 hour


def _clear_all_caches() -> None:
    clear_market_data_cache()
    clear_analytics_cache()
    clear_contract_analytics_cache()


def _prewarm_ticker(ticker: str) -> None:
    try:
        get_live_ticker_kpis(ticker)
    except Exception:
        pass
    try:
        get_live_iv_term_structure(ticker)
    except Exception:
        pass
    try:
        get_live_iv_smile(ticker)
    except Exception:
        pass


def _prewarm_cache(delay: bool = False) -> None:
    if delay:
        sleep(3)  # let server stabilise before starting
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_prewarm_ticker, ticker) for ticker in TICKER_ORDER]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass


def _cache_refresh_loop() -> None:
    while True:
        sleep(CACHE_REFRESH_SECONDS)
        _clear_all_caches()
        _prewarm_cache()


# Start the cache refresh thread for both dev and production (gunicorn)
refresh_thread = Thread(target=_cache_refresh_loop, daemon=True)
refresh_thread.start()

# Pre-warm the cache at startup so the first visitor hits a hot cache
prewarm_thread = Thread(target=lambda: _prewarm_cache(delay=True), daemon=True)
prewarm_thread.start()

if __name__ == "__main__":
    app.run(debug=True)