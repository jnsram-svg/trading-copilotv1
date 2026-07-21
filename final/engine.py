"""
engine.py
=========
Shared logic for the Nifty F&O Pivot Confluence Scanner + Tracker.

Contains:
  - Supertrend + pivot-detection pipeline (ported 1:1 from the user's
    05_1_st_engine.py so pivot definitions stay identical across timeframes)
  - Yahoo Finance data fetching (per-timeframe, cached)
  - Confluence scan across multiple timeframes
  - Tracker persistence (JSON file, survives across Streamlit reruns/restarts)
"""

import json
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# ============================================================
# PATHS
# ============================================================

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKER_FILE = os.path.join(APP_DIR, "tracked_stocks.json")

# ============================================================
# DEFAULT NIFTY F&O UNIVERSE
# (editable in the Scanner sidebar - this is just a sane default,
#  the F&O list changes periodically so keep this maintained)
# ============================================================

DEFAULT_FNO_STOCKS = [
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","HDFC","BHARTIARTL",
    "ITC","KOTAKBANK","LT","AXISBANK","BAJFINANCE","ASIANPAINT","MARUTI",
    "HCLTECH","SUNPHARMA","TITAN","ULTRACEMCO","WIPRO","NESTLEIND","M&M",
    "ADANIENT","ADANIPORTS","BAJAJFINSV","POWERGRID","NTPC","TATASTEEL",
    "TATAMOTORS","JSWSTEEL","ONGC","COALINDIA","INDUSINDBK","GRASIM",
    "HINDALCO","TECHM","DRREDDY","CIPLA","EICHERMOT","BAJAJ-AUTO","BPCL",
    "BRITANNIA","DIVISLAB","HEROMOTOCO","APOLLOHOSP","SBILIFE","HDFCLIFE",
    "SHREECEM","UPL","TATACONSUM","LTIM","PIDILITIND","DABUR","GODREJCP",
    "HAVELLS","SIEMENS","DLF","VEDL","AMBUJACEM","ACC","BANKBARODA","PNB",
    "CANBK","IDFCFIRSTB","FEDERALBNK","AUBANK","BANDHANBNK","PEL","CHOLAFIN",
    "MUTHOOTFIN","SRTRANSFIN","LICHSGFIN","RECLTD","PFC","IRFC","GAIL",
    "IOC","HINDPETRO","PETRONET","MRF","APOLLOTYRE","BALKRISIND","BOSCHLTD",
    "MOTHERSON","EXIDEIND","TVSMOTOR","ASHOKLEY","CUMMINSIND","ABB","SIEMENS",
    "BHEL","BEL","HAL","CONCOR","CONTAINER","IRCTC","INDIGO","ZOMATO",
    "NYKAA","PAYTM","POLICYBZR","NAUKRI","DMART","TRENT","JUBLFOOD",
    "PAGEIND","VOLTAS","CROMPTON","WHIRLPOOL","BATAINDIA","RELAXO",
    "PIIND","SRF","AARTIIND","DEEPAKNTR","TATACHEM","GNFC","GUJGASLTD",
    "IGL","MGL","TORNTPOWER","TATAPOWER","ADANIGREEN","ADANIPOWER",
    "ADANIENSOL","JSWENERGY","NHPC","SJVN","NMDC","JINDALSTEL","SAIL",
    "HINDCOPPER","NATIONALUM","RATNAMANI","APLAPOLLO","LTF","LTTS",
    "PERSISTENT","COFORGE","MPHASIS","OFSS","TATAELXSI","KPITTECH",
    "CYIENT","BSOFT","INDIAMART","JUSTDIAL","AFFLE","ANGELONE",
    "CDSL","BSE","MCX","IEX","CAMS","IIFL","MANAPPURAM","ABCAPITAL",
    "ABFRL","RBLBANK","YESBANK","IDEA","INDUSTOWER","GMRINFRA",
    "SUNTV","ZEEL","PVRINOX","DELHIVERY","LODHA","OBEROIRLTY",
    "GODREJPROP","PRESTIGE","PHOENIXLTD","SUNTECK","BRIGADE",
    "ESCORTS","SONACOMS","BHARATFORG","TIINDIA","SUPREMEIND",
    "ASTRAL","POLYCAB","KEI","FINCABLES","VGUARD","DIXON","AMBER",
    "SYNGENE","LAURUSLABS","AUROPHARMA","ALKEM","LUPIN","TORNTPHARM",
    "GLENMARK","IPCALAB","BIOCON","GRANULES","NATCOPHARM","ZYDUSLIFE",
    "COLPAL","MARICO","EMAMILTD","VBL","UBL","MCDOWELL-N","RADICO",
    "PGHH","GILLETTE","ABBOTINDIA","SANOFI","PFIZER","GLAXO",
    "STARHEALTH","GICRE","NIACL","ICICIGI","ICICIPRULI","HDFCAMC",
    "NAM-INDIA","UTIAMC","SBICARD","M&MFIN","BAJAJHLDNG","IIFLWAM",
]

DEFAULT_FNO_STOCKS = sorted(set(DEFAULT_FNO_STOCKS))

# ============================================================
# TIMEFRAME CONFIG
# label -> (yfinance interval, default period)
# Yahoo limits: 5m/15m/30m data -> last 60d, 60m data -> last 730d
# ============================================================

TIMEFRAMES = {
    "Daily":  {"interval": "1d",  "period": "1y"},
    "Hourly": {"interval": "60m", "period": "60d"},
    "15min":  {"interval": "15m", "period": "40d"},
    "5min":   {"interval": "5m",  "period": "20d"},
}


# ============================================================
# SUPERTREND + PIVOT ENGINE
# (ported from 05_1_st_engine.py - logic kept identical)
# ============================================================

def compute_supertrend_pivots(df: pd.DataFrame, st_len: int = 10, st_factor: float = 3.0):
    """
    df must have columns: dt, open, high, low, close (lower-case).
    Returns pivot_df with columns: pivot_type, pivot_price, pivot_bar, dt, structure
    Also returns the enriched df (with stDir) in case it's useful for debugging.
    """

    df = df.reset_index(drop=True).copy()

    high = df["high"]
    low = df["low"]
    close = df["close"]

    if len(df) < st_len + 5:
        # not enough bars to form a stable Supertrend
        return pd.DataFrame(
            columns=["pivot_type", "pivot_price", "pivot_bar", "dt",
                     "confirm_bar", "confirm_dt", "structure"]
        ), df

    # --------------------------------------------------------
    # TRUE RANGE
    # --------------------------------------------------------

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # --------------------------------------------------------
    # TRADINGVIEW RMA ATR
    # --------------------------------------------------------

    atr = np.zeros(len(df))
    atr[st_len - 1] = tr.iloc[:st_len].mean()

    for i in range(st_len, len(df)):
        atr[i] = ((atr[i - 1] * (st_len - 1)) + tr.iloc[i]) / st_len

    df["atr"] = atr

    # --------------------------------------------------------
    # BASIC BANDS
    # --------------------------------------------------------

    hl2 = (high + low) / 2
    upperband = hl2 + st_factor * df["atr"]
    lowerband = hl2 - st_factor * df["atr"]

    # --------------------------------------------------------
    # FINAL BANDS
    # --------------------------------------------------------

    final_upperband = upperband.copy()
    final_lowerband = lowerband.copy()

    for i in range(1, len(df)):

        if (upperband.iloc[i] < final_upperband.iloc[i - 1]
                or close.iloc[i - 1] > final_upperband.iloc[i - 1]):
            final_upperband.iloc[i] = upperband.iloc[i]
        else:
            final_upperband.iloc[i] = final_upperband.iloc[i - 1]

        if (lowerband.iloc[i] > final_lowerband.iloc[i - 1]
                or close.iloc[i - 1] < final_lowerband.iloc[i - 1]):
            final_lowerband.iloc[i] = lowerband.iloc[i]
        else:
            final_lowerband.iloc[i] = final_lowerband.iloc[i - 1]

    # --------------------------------------------------------
    # SUPERTREND DIRECTION
    # --------------------------------------------------------

    stDir = np.zeros(len(df))

    for i in range(1, len(df)):
        if close.iloc[i] > final_upperband.iloc[i - 1]:
            stDir[i] = -1
        elif close.iloc[i] < final_lowerband.iloc[i - 1]:
            stDir[i] = 1
        else:
            stDir[i] = stDir[i - 1]

    df["stDir"] = stDir

    df["turnGreen"] = df["stDir"].diff() < 0
    df["turnRed"] = df["stDir"].diff() > 0

    # --------------------------------------------------------
    # PIVOT STORAGE
    # --------------------------------------------------------

    pivot_type, pivot_price, pivot_bar, pivot_dt = [], [], [], []
    confirm_bar, confirm_dt = [], []

    last_green_index = 0
    last_red_index = 0

    for i in range(len(df)):

        turnGreen = df["turnGreen"].iloc[i]
        turnRed = df["turnRed"].iloc[i]

        if turnGreen:

            barsr = i - last_red_index
            if barsr <= 0:
                barsr = 1

            window = df.iloc[i - barsr: i + 1]
            pivot_idx = window["low"].idxmin()
            pivot_low = df.loc[pivot_idx, "low"]

            pivot_type.append("PL")
            pivot_price.append(pivot_low)
            pivot_bar.append(pivot_idx)
            pivot_dt.append(df.loc[pivot_idx, "dt"])
            # the pivot is only KNOWN at the flip bar i (not at the earlier
            # extreme bar) - used for causal regime detection
            confirm_bar.append(i)
            confirm_dt.append(df.loc[i, "dt"])

            last_green_index = i

        elif turnRed:

            barsg = i - last_green_index
            if barsg <= 0:
                barsg = 1

            window = df.iloc[i - barsg: i + 1]
            pivot_idx = window["high"].idxmax()
            pivot_high = df.loc[pivot_idx, "high"]

            pivot_type.append("PH")
            pivot_price.append(pivot_high)
            pivot_bar.append(pivot_idx)
            pivot_dt.append(df.loc[pivot_idx, "dt"])
            confirm_bar.append(i)
            confirm_dt.append(df.loc[i, "dt"])

            last_red_index = i

    pivot_df = pd.DataFrame({
        "pivot_type": pivot_type,
        "pivot_price": pivot_price,
        "pivot_bar": pivot_bar,
        "dt": pivot_dt,
        "confirm_bar": confirm_bar,
        "confirm_dt": confirm_dt,
    })

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    structure = []
    prevHigh = np.nan
    prevLow = np.nan

    for i in range(len(pivot_df)):
        ptype = pivot_df["pivot_type"].iloc[i]
        price = pivot_df["pivot_price"].iloc[i]
        label = "NONE"

        if ptype == "PH":
            if not np.isnan(prevHigh):
                if price > prevHigh:
                    label = "HH"
                elif price < prevHigh:
                    label = "LH"
            prevHigh = price
        elif ptype == "PL":
            if not np.isnan(prevLow):
                if price > prevLow:
                    label = "HL"
                elif price < prevLow:
                    label = "LL"
            prevLow = price

        structure.append(label)

    pivot_df["structure"] = structure

    return pivot_df, df


def latest_pivots(pivot_df: pd.DataFrame):
    """Return (latest_PH_row, latest_PL_row) as dicts, or None if not present."""
    if pivot_df.empty:
        return None, None

    ph = pivot_df[pivot_df["pivot_type"] == "PH"]
    pl = pivot_df[pivot_df["pivot_type"] == "PL"]

    latest_ph = ph.iloc[-1].to_dict() if not ph.empty else None
    latest_pl = pl.iloc[-1].to_dict() if not pl.empty else None

    return latest_ph, latest_pl


# ============================================================
# REGIME STATE MACHINE
# Bearish: price breaks below the last TWO confirmed Pivot Lows
# Bullish: price breaks above the last TWO confirmed Pivot Highs
# Regime persists until the opposite break happens (state machine, not
# a per-bar flag) - matches the CHoCH-based regime framework.
# ============================================================

def compute_regime(df_enriched: pd.DataFrame, pivot_df: pd.DataFrame):
    """
    Causal, bar-by-bar regime walk using only pivots confirmed as of each bar
    (confirm_bar), so there's no lookahead.

    Returns (regime_series, current_regime) where regime_series is a list
    aligned to df_enriched rows, values in {"NEUTRAL","BULLISH","BEARISH"}.
    """
    n = len(df_enriched)
    regime_series = ["NEUTRAL"] * n

    if pivot_df.empty or n == 0:
        return regime_series, "NEUTRAL"

    close = df_enriched["close"]

    # group pivots by the bar they become known at
    pivots_by_confirm_bar = {}
    for _, row in pivot_df.iterrows():
        pivots_by_confirm_bar.setdefault(int(row["confirm_bar"]), []).append(row)

    recent_pls = []  # chronological, keep last 2 prices
    recent_phs = []
    regime = "NEUTRAL"

    for i in range(n):

        if i in pivots_by_confirm_bar:
            for row in pivots_by_confirm_bar[i]:
                if row["pivot_type"] == "PL":
                    recent_pls.append(float(row["pivot_price"]))
                    recent_pls = recent_pls[-2:]
                elif row["pivot_type"] == "PH":
                    recent_phs.append(float(row["pivot_price"]))
                    recent_phs = recent_phs[-2:]

        c = close.iloc[i]

        if len(recent_pls) >= 2 and c < min(recent_pls):
            regime = "BEARISH"
        elif len(recent_phs) >= 2 and c > max(recent_phs):
            regime = "BULLISH"
        # else: regime persists (state machine)

        regime_series[i] = regime

    return regime_series, regime


def regime_signal(regime: str, pivot_type: str):
    """
    Your trading rule:
      - BEARISH regime + price near a PH  -> SELL (fade the rally)
      - BULLISH regime + price near a PL  -> BUY  (buy the dip)
      - Anything else near a pivot is a structure watch-level, not an entry
        against the rule, so it's flagged rather than signalled.
    """
    if regime == "BEARISH" and pivot_type == "PH":
        return "SELL"
    if regime == "BULLISH" and pivot_type == "PL":
        return "BUY"
    if regime == "BEARISH" and pivot_type == "PL":
        return "WATCH (breakdown)"
    if regime == "BULLISH" and pivot_type == "PH":
        return "WATCH (breakout)"
    return "-"


# ============================================================
# DATA FETCHING (Yahoo Finance)
# ============================================================

@st.cache_data(ttl=180, show_spinner=False)
def fetch_ohlc(symbol: str, interval: str, period: str):
    """
    symbol: NSE symbol WITHOUT .NS suffix (e.g. 'RELIANCE')
    Returns a clean dataframe with columns: dt, open, high, low, close, volume
    """
    ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return pd.DataFrame()

    if hist is None or hist.empty:
        return pd.DataFrame()

    hist = hist.reset_index()

    # yfinance names the datetime column "Date" for daily, "Datetime" for intraday
    dt_col = "Datetime" if "Datetime" in hist.columns else "Date"

    out = pd.DataFrame({
        "dt": hist[dt_col],
        "open": hist["Open"],
        "high": hist["High"],
        "low": hist["Low"],
        "close": hist["Close"],
        "volume": hist["Volume"],
    }).dropna(subset=["open", "high", "low", "close"])

    return out.reset_index(drop=True)


# ============================================================
# CONFLUENCE SCAN
# ============================================================

def scan_symbol(symbol: str, timeframe_labels, tolerance_pct: float,
                 st_len: int = 10, st_factor: float = 3.0):
    """
    Scans one symbol across the requested timeframe labels (subset of TIMEFRAMES keys).
    Returns a dict:
      {
        "symbol": ..., "current_price": ...,
        "hits": [ {"timeframe":.., "pivot_type":.., "pivot_price":.., "distance_pct":.., "pivot_dt":..}, ... ],
        "confluence_count": n,
      }
    Returns None if no data available at all.
    """
    hits = []
    current_price = None

    for tf_label in timeframe_labels:
        cfg = TIMEFRAMES[tf_label]
        df = fetch_ohlc(symbol, cfg["interval"], cfg["period"])

        if df.empty:
            continue

        if current_price is None:
            current_price = float(df["close"].iloc[-1])

        pivot_df, enriched = compute_supertrend_pivots(df, st_len=st_len, st_factor=st_factor)
        ph, pl = latest_pivots(pivot_df)
        _, current_regime = compute_regime(enriched, pivot_df)

        for kind, piv in (("PH", ph), ("PL", pl)):
            if piv is None:
                continue
            piv_price = float(piv["pivot_price"])
            if piv_price == 0:
                continue
            dist_pct = (current_price - piv_price) / piv_price * 100.0
            if abs(dist_pct) <= tolerance_pct:
                hits.append({
                    "timeframe": tf_label,
                    "pivot_type": kind,
                    "pivot_price": round(piv_price, 2),
                    "distance_pct": round(dist_pct, 3),
                    "pivot_dt": piv["dt"],
                    "regime": current_regime,
                    "signal": regime_signal(current_regime, kind),
                })

    if current_price is None:
        return None

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "hits": hits,
        "confluence_count": len(hits),
    }


# ============================================================
# TRACKER PERSISTENCE (JSON file - survives reruns / restarts)
# ============================================================

def _load_json():
    if not os.path.exists(TRACKER_FILE):
        return []
    try:
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_json(data):
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_tracked():
    return _load_json()


def add_tracked(symbol: str, hits: list, current_price: float):
    """Adds/updates a symbol in the tracker with its confluence detail at time of add."""
    data = _load_json()

    entry = {
        "symbol": symbol,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "added_price": current_price,
        "hits_at_add": hits,
    }

    # replace existing entry for the same symbol if present
    data = [d for d in data if d.get("symbol") != symbol]
    data.append(entry)

    _save_json(data)


def remove_tracked(symbol: str):
    data = _load_json()
    data = [d for d in data if d.get("symbol") != symbol]
    _save_json(data)


def clear_tracked():
    _save_json([])
