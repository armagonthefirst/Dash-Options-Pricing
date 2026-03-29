from __future__ import annotations

import os

import pandas as pd

USE_LIVE_DATA = os.getenv("USE_LIVE_DATA", "1").strip().lower() not in {"0", "false", "no"}

if USE_LIVE_DATA:
    from data.analytics import (
        get_live_default_expiry as get_default_expiry,
        get_live_expiry_choices as get_expiry_choices,
        get_live_filtered_option_chain as get_filtered_option_chain,
        get_live_iv_smile as get_iv_smile,
        get_live_iv_term_structure as get_iv_term_structure,
        get_live_option_chain as get_option_chain,
        get_live_price_chart_frame as get_price_chart_frame,
        get_live_screener_data as get_screener_data,
        get_live_supported_tickers as get_supported_tickers,
        get_live_ticker_kpis as get_ticker_kpis,
        get_live_volatility_chart_frame as get_volatility_chart_frame,
    )
else:
    from data.mock_data import (
        get_default_expiry,
        get_expiry_choices,
        get_iv_smile,
        get_iv_term_structure,
        get_option_chain,
        get_price_chart_frame,
        get_screener_data,
        get_supported_tickers,
        get_ticker_kpis,
        get_volatility_chart_frame,
    )

    def get_filtered_option_chain(
        ticker: str,
        expiry: str,
        option_type: str = "both",
        moneyness_bucket: str = "0.85-1.15",
        sort_by: str = "strike",
    ) -> pd.DataFrame:
        chain = get_option_chain(ticker, expiry).copy()

        if option_type == "calls":
            chain = chain.loc[chain["type"] == "Call"]
        elif option_type == "puts":
            chain = chain.loc[chain["type"] == "Put"]

        if moneyness_bucket == "0.90-1.10":
            chain = chain.loc[(chain["moneyness"] >= 0.90) & (chain["moneyness"] <= 1.10)]
        elif moneyness_bucket == "0.85-1.15":
            chain = chain.loc[(chain["moneyness"] >= 0.85) & (chain["moneyness"] <= 1.15)]

        ascending = sort_by == "strike"
        return chain.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
