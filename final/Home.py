import streamlit as st

st.set_page_config(
    page_title="Nifty F&O Pivot Confluence Scanner",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Nifty F&O — Supertrend Pivot Confluence Scanner")

st.markdown(
    """
Use the sidebar/pages on the left to navigate:

- **Scanner** — downloads Daily / Hourly / 15-min / 5-min data for your F&O universe from
  Yahoo Finance, runs your Supertrend pivot engine on each timeframe, and flags any stock
  whose current price is within a configurable tolerance of a confirmed Pivot High (PH) or
  Pivot Low (PL). Results are ranked by **confluence** — how many timeframes agree.
  Each hit also carries a **regime + signal**. Tick a row's **Track** box and hit
  *Add to Tracker* to send it to the Tracker page.

- **Tracker** — shows every stock you've added, with a live-refresh option that re-runs
  the pivot + regime engine to get current price, regime, and signal. Remove stocks anytime.

**Pivot logic** is a direct port of your `05_1_st_engine.py` Supertrend + pivot engine —
identical ATR/RMA, final-band, direction-flip, and confirmed-pivot-window logic — run
independently per timeframe so Daily/Hourly/15-min/5-min pivots stay causally correct
(no lookahead) within each timeframe's own bar series.

**Regime + signal rule:**
- Price breaks below the last **two** confirmed Pivot Lows → **BEARISH** regime.
  Regime persists until price then breaks above the last two confirmed Pivot Highs.
- Price breaks above the last **two** confirmed Pivot Highs → **BULLISH** regime.
  Persists until price breaks below the last two confirmed Pivot Lows.
- **BEARISH** regime + price near a **PH** → **SELL** (fade the rally at resistance).
- **BULLISH** regime + price near a **PL** → **BUY** (buy the dip at support).
- The opposite pairing (e.g. bearish regime + near PL) is flagged as a **WATCH** level
  (possible breakdown/breakout), not a signal against the rule.

Nothing here talks to a broker — it's read-only market data from Yahoo Finance
(`yfinance`), so there can be a delay of a few minutes versus your live feed.
"""
)

st.info(
    "First run: `pip install -r requirements.txt`, then `streamlit run Home.py` "
    "from this folder.",
    icon="ℹ️",
)
