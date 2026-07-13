"""
Triple Signal Confluence Scanner
---------------------------------
Standalone research script - completely separate from rsiscanner_portfolio_tracker.py.
No shared imports/state with that app; safe to run independently.

Tests whether three signals clustering within a small trailing window carries edge:
  1. RSI Cross Count  - zone-entry-with-reset count hitting >=3 (oversold/overbought)
  2. RSI Divergence   - swing-pivot based price/RSI divergence (peak/trough method)
  3. BB Signal        - price crossunder lower band (BUY) / crossover upper band (SELL)

A "confluence event" fires on the bar where, looking back `window_bars` bars,
all three have appeared with the SAME direction (bullish or bearish).
This is real-time-usable: only trailing data is used, no lookahead.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import uuid
from datetime import date, datetime

# --------------------------
# Ticker universe (same list as the main scanner, duplicated here on purpose
# so this file has zero dependency on rsiscanner_portfolio_tracker.py)
# --------------------------
NIFTY_FO_TICKERS = ["CL=F", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "WIPRO.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "NTPC.NS",
    "M&M.NS", "BAJFINANCE.NS",  "TATASTEEL.NS", "JSWSTEEL.NS",
    "HCLTECH.NS", "POWERGRID.NS", "NESTLEIND.NS", "BAJAJFINSV.NS",
    "COALINDIA.NS", "ONGC.NS", "ADANIENT.NS", "SBILIFE.NS", "HINDALCO.NS",
    "BRITANNIA.NS", "GRASIM.NS", "EICHERMOT.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "CIPLA.NS", "SHREECEM.NS", "APOLLOHOSP.NS", "HEROMOTOCO.NS", "BPCL.NS",
    "IOC.NS", "UPL.NS", "TECHM.NS", "HDFCLIFE.NS", "ICICIPRULI.NS",
    "MUTHOOTFIN.NS", "PIDILITIND.NS", "DABUR.NS", "INDUSINDBK.NS",
    "BSE.NS",
    "IDEA.NS",
    "POWERINDIA.NS",
    "POLYCAB.NS",
    "BHEL.NS",
    "GVT&D.NS",
    "INDIANB.NS",
    "AAVAS.NS",
    "AFFLE.NS",
    "ALKYLAMINE.NS",
    "ALLCARGO.NS",
    "ALOKINDS.NS",
    "CLEAN.NS",
    "FINEORG.NS",
    "GILLETTE.NS",
    "GPIL.NS",
    "NAM-INDIA.NS",
    "TTML.NS",
    "UJJIVANSFB.NS",
    "MAXHEALTH.NS",
    "PFC.NS",
    "RECLTD.NS",
    "MUTHOOTFIN.NS",
    "UNIONBANK.NS",
    "MOTHERSON.NS",
    "ASHOKLEY.NS",
    "BHARATFORG.NS",
   
    "MCX.NS",
    "FEDERALBNK.NS",
    "CUMMINSIND.NS",
    "ABB.NS",


]


# --------------------------
# Core indicator functions (self-contained copies)
# --------------------------
def compute_rsi(close, period=14, wilder=False):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    if wilder:
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    else:
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100)
    return rsi


def count_zone_entries_with_reset(rsi_series, red_level=70, green_level=30):
    """
    Zone-entry-with-reset RSI cross count: increments each time RSI enters
    the red (>=70) or green (<=30) zone from outside, resets when RSI exits
    back through the opposite direction / neutral zone crossing.
    """
    n = len(rsi_series)
    red_count = pd.Series(0, index=rsi_series.index)
    green_count = pd.Series(0, index=rsi_series.index)
    r_vals = rsi_series.values

    red_c = 0
    green_c = 0
    prev_in_red = False
    prev_in_green = False

    for i in range(n):
        v = r_vals[i]
        if np.isnan(v):
            red_count.iloc[i] = red_c
            green_count.iloc[i] = green_c
            continue

        in_red = v >= red_level
        in_green = v <= green_level

        if in_red and not prev_in_red:
            red_c += 1
        if in_green and not prev_in_green:
            green_c += 1

        # Reset counters once RSI travels back through the neutral midpoint (50)
        if not in_red and not in_green and 45 <= v <= 55:
            red_c = 0
            green_c = 0

        prev_in_red = in_red
        prev_in_green = in_green

        red_count.iloc[i] = red_c
        green_count.iloc[i] = green_c

    return red_count, green_count


def detect_divergence(price, rsi, window=5, min_price_change_pct=0.0, min_rsi_change=0.0):
    """
    Swing-pivot (peak/trough) divergence method.

    User-tunable parameters (all optional, default to the original
    unfiltered behaviour so existing results don't shift unless you
    change them):
      - window: pivot lookback/lookahead in bars. Larger = fewer, more
        significant pivots; smaller = more, noisier pivots.
      - min_price_change_pct: minimum % move between the two compared
        pivots' price (abs value) required for a divergence to count.
        Filters out divergences formed by two nearly-identical price
        pivots.
      - min_rsi_change: minimum absolute RSI point move between the two
        compared pivots required for a divergence to count. Filters out
        divergences where RSI barely moved.

    Returns 4 Series aligned to price.index:
      bullish, bearish  - True on the bar where the divergence confirms
                           (the more recent of the two compared pivots)
      bullish_ref_time, bearish_ref_time - the timestamp of the EARLIER
                           pivot each divergence was compared against
                           (NaT where no divergence). This is what makes
                           a divergence marker visually verifiable: a
                           lone dot at e.g. RSI 65 can look bullish in
                           isolation, but connecting it back to the
                           earlier, higher-RSI peak it lost to shows the
                           actual lower-high-on-RSI pattern.
    """
    n = len(price)
    bullish = pd.Series(False, index=price.index)
    bearish = pd.Series(False, index=price.index)
    bullish_ref_time = pd.Series(pd.NaT, index=price.index, dtype=price.index.dtype)
    bearish_ref_time = pd.Series(pd.NaT, index=price.index, dtype=price.index.dtype)
    if n < 2 * window:
        return bullish, bearish, bullish_ref_time, bearish_ref_time
    p_vals = price.values
    r_vals = rsi.values
    peaks = []
    troughs = []
    for i in range(window, n - window):
        left_max = max(p_vals[i-window:i]) if i-window >= 0 else -np.inf
        right_max = max(p_vals[i+1:i+window+1]) if i+window+1 <= n else -np.inf
        if p_vals[i] > left_max and p_vals[i] > right_max:
            peaks.append(i)
        left_min = min(p_vals[i-window:i]) if i-window >= 0 else np.inf
        right_min = min(p_vals[i+1:i+window+1]) if i+window+1 <= n else np.inf
        if p_vals[i] < left_min and p_vals[i] < right_min:
            troughs.append(i)
    for i in range(1, len(peaks)):
        idx1, idx2 = peaks[i-1], peaks[i]
        price_change_pct = abs(p_vals[idx2] - p_vals[idx1]) / p_vals[idx1] * 100 if p_vals[idx1] != 0 else 0.0
        rsi_change = abs(r_vals[idx2] - r_vals[idx1])
        if (p_vals[idx2] > p_vals[idx1] and r_vals[idx2] < r_vals[idx1]
                and price_change_pct >= min_price_change_pct and rsi_change >= min_rsi_change):
            bearish.iloc[idx2] = True
            bearish_ref_time.iloc[idx2] = price.index[idx1]
    for i in range(1, len(troughs)):
        idx1, idx2 = troughs[i-1], troughs[i]
        price_change_pct = abs(p_vals[idx2] - p_vals[idx1]) / p_vals[idx1] * 100 if p_vals[idx1] != 0 else 0.0
        rsi_change = abs(r_vals[idx2] - r_vals[idx1])
        if (p_vals[idx2] < p_vals[idx1] and r_vals[idx2] > r_vals[idx1]
                and price_change_pct >= min_price_change_pct and rsi_change >= min_rsi_change):
            bullish.iloc[idx2] = True
            bullish_ref_time.iloc[idx2] = price.index[idx1]
    return bullish, bearish, bullish_ref_time, bearish_ref_time


def detect_zone_extremum_divergence(price, rsi, ob_level=60, os_level=40,
                                     min_price_change_pct=0.0, min_rsi_change=0.0,
                                     max_gap_bars=20):
    """
    Zone-excursion RSI divergence - an alternate definition to the swing-
    pivot method above. Mirrors the segment-tracking logic of the
    "Trend Lines for RSI, CCI, Momentum, OBV" Pine Script indicator
    (crossunder/crossover-triggered excursions, always roll forward to
    the next segment, maxGap-limited comparison), with a price condition
    added on top since that script only compares the indicator itself.

    Instead of comparing arbitrary local price/RSI swing highs, this:
      - Tracks every excursion where RSI stays >= ob_level (overbought).
        Within that excursion, records the bar with the HIGHEST RSI
        reached - the "episode peak". The episode is only finalized (and
        thus only usable for comparison) once RSI drops back BELOW
        ob_level, so the peak can't later be exceeded/repainted.
      - Tracks every excursion where RSI stays <= os_level (oversold),
        recording the bar with the LOWEST RSI reached - the "episode
        trough" - finalized once RSI rises back ABOVE os_level.
      - Bearish divergence: current episode's peak has a HIGHER price but
        LOWER RSI than the PREVIOUS episode's peak, AND the two peaks are
        no more than max_gap_bars apart.
      - Bullish divergence: current episode's trough has a LOWER price but
        HIGHER RSI than the PREVIOUS episode's trough, AND the two
        troughs are no more than max_gap_bars apart.
      - Price is read directly off the RSI-extreme bar - no separate
        price-pivot requirement.
      - max_gap_bars: maximum bar distance allowed between the two
        compared pivot bars (not the confirmation bars). Sets to 0 or
        None to disable (no limit). Matches the Pine reference's
        "Maximum bar gap between pivot points" input, which stops a
        comparison being made between two excursions that are so far
        apart in time they're not really a meaningful pair anymore.
      - Every excursion always becomes the new "previous" reference for
        the next one, whether or not it produced a divergence - same as
        the Pine reference's unconditional bullLow1 := bullLow2 shift.

    The bullish/bearish flag fires on the CONFIRMATION bar (where RSI
    exits the zone) - keeping this real-time/no-lookahead safe, same as
    the rest of this scanner. The actual peak/trough bar (which can be
    earlier than the confirmation bar) is tracked separately so the chart
    can mark and connect to the real extreme, not the exit bar.

    Returns 6 Series aligned to price.index:
      bullish, bearish                       - True on the confirmation bar
      bullish_pivot_time, bearish_pivot_time - timestamp of THIS episode's
                                                trough/peak bar
      bullish_ref_time, bearish_ref_time     - timestamp of the PREVIOUS
                                                episode's trough/peak bar
    """
    n = len(price)
    idx = price.index
    p_vals = price.values
    r_vals = rsi.values

    bullish = pd.Series(False, index=idx)
    bearish = pd.Series(False, index=idx)
    bullish_pivot_time = pd.Series(pd.NaT, index=idx, dtype=idx.dtype)
    bearish_pivot_time = pd.Series(pd.NaT, index=idx, dtype=idx.dtype)
    bullish_ref_time = pd.Series(pd.NaT, index=idx, dtype=idx.dtype)
    bearish_ref_time = pd.Series(pd.NaT, index=idx, dtype=idx.dtype)

    in_ob = False
    in_os = False
    ob_peak_i = None
    os_trough_i = None
    prev_ob_peak_i = None
    prev_os_trough_i = None

    for i in range(n):
        v = r_vals[i]
        if np.isnan(v):
            continue

        # --- Overbought excursion tracking ---
        if v >= ob_level:
            if not in_ob:
                in_ob = True
                ob_peak_i = i
            elif v > r_vals[ob_peak_i]:
                ob_peak_i = i
        elif in_ob:
            # Excursion just ended - bar i is the confirmation bar.
            if prev_ob_peak_i is not None and ob_peak_i is not None:
                ref_p = p_vals[prev_ob_peak_i]
                price_change_pct = abs(p_vals[ob_peak_i] - ref_p) / ref_p * 100 if ref_p != 0 else 0.0
                rsi_change = abs(r_vals[ob_peak_i] - r_vals[prev_ob_peak_i])
                gap_bars = ob_peak_i - prev_ob_peak_i
                gap_ok = (not max_gap_bars) or gap_bars <= max_gap_bars
                if (p_vals[ob_peak_i] > ref_p and r_vals[ob_peak_i] < r_vals[prev_ob_peak_i]
                        and price_change_pct >= min_price_change_pct and rsi_change >= min_rsi_change
                        and gap_ok):
                    bearish.iloc[i] = True
                    bearish_pivot_time.iloc[i] = idx[ob_peak_i]
                    bearish_ref_time.iloc[i] = idx[prev_ob_peak_i]
            prev_ob_peak_i = ob_peak_i
            in_ob = False
            ob_peak_i = None

        # --- Oversold excursion tracking ---
        if v <= os_level:
            if not in_os:
                in_os = True
                os_trough_i = i
            elif v < r_vals[os_trough_i]:
                os_trough_i = i
        elif in_os:
            if prev_os_trough_i is not None and os_trough_i is not None:
                ref_p = p_vals[prev_os_trough_i]
                price_change_pct = abs(p_vals[os_trough_i] - ref_p) / ref_p * 100 if ref_p != 0 else 0.0
                rsi_change = abs(r_vals[os_trough_i] - r_vals[prev_os_trough_i])
                gap_bars = os_trough_i - prev_os_trough_i
                gap_ok = (not max_gap_bars) or gap_bars <= max_gap_bars
                if (p_vals[os_trough_i] < ref_p and r_vals[os_trough_i] > r_vals[prev_os_trough_i]
                        and price_change_pct >= min_price_change_pct and rsi_change >= min_rsi_change
                        and gap_ok):
                    bullish.iloc[i] = True
                    bullish_pivot_time.iloc[i] = idx[os_trough_i]
                    bullish_ref_time.iloc[i] = idx[prev_os_trough_i]
            prev_os_trough_i = os_trough_i
            in_os = False
            os_trough_i = None

    return bullish, bearish, bullish_pivot_time, bearish_pivot_time, bullish_ref_time, bearish_ref_time


def compute_bollinger_bands(close, period=20, std_dev=2):
    mid = close.rolling(window=period).mean()
    std = close.rolling(window=period).std(ddof=0)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return mid, upper, lower


def crossunder(series_a, series_b):
    prev_a, prev_b = series_a.shift(1), series_b.shift(1)
    return (prev_a >= prev_b) & (series_a < series_b)


def crossover(series_a, series_b):
    prev_a, prev_b = series_a.shift(1), series_b.shift(1)
    return (prev_a <= prev_b) & (series_a > series_b)


# --------------------------
# Confluence detection
# --------------------------
DATE_LIKE_EVENT_COLUMNS = ['confirm_date', 'rsi_cross_date', 'divergence_date', 'bb_signal_date', 'trail_exit_date']


def normalize_event_date_columns(events_df):
    """
    Tickers can come from different exchanges with different timezones
    (e.g. NSE tickers vs CL=F crude futures). Concatenating their events
    dataframes leaves date columns as mixed-tz object dtype, which breaks
    the .dt accessor (and can break sorting/comparisons). Force everything
    to a single UTC datetime64 dtype right after any cross-ticker concat.
    """
    if events_df.empty:
        return events_df
    events_df = events_df.copy()
    for col in DATE_LIKE_EVENT_COLUMNS:
        if col in events_df.columns:
            events_df[col] = pd.to_datetime(events_df[col], utc=True, errors='coerce')
    return events_df


def shift_index_to_ist(idx):
    """
    Converts a DatetimeIndex (or single Timestamp) to Asia/Kolkata for
    chart display only. This is separate from to_ist_display, which
    handles the UTC-normalized event table columns - this one handles
    the raw OHLC dataframe's index used as the x-axis in the price/RSI
    charts, which was staying in whatever tz (or tz-naive UTC) yfinance/
    the CSV handed back, i.e. displaying 5:30 hours behind IST.

    - tz-aware index -> tz_convert('Asia/Kolkata') (correct, no guessing)
    - tz-naive index -> treated as UTC and shifted +5:30 to IST
    """
    if isinstance(idx, pd.Timestamp):
        if idx.tzinfo is not None:
            return idx.tz_convert('Asia/Kolkata')
        return idx + pd.Timedelta(hours=5, minutes=30)
    if getattr(idx, 'tz', None) is not None:
        return idx.tz_convert('Asia/Kolkata')
    return idx + pd.Timedelta(hours=5, minutes=30)


def align_ts_to_index(ts, reference_index):
    """
    Reconciles a Timestamp's tz-awareness with a DatetimeIndex's tz-awareness
    before doing an exact .get_loc() lookup. Without this, looking up a
    UTC-aware confirm_date (see normalize_event_date_columns) in a tz-naive
    index - which is what yfinance hands back for daily ('1d') interval data -
    raises KeyError in current pandas (aware vs naive is never considered
    equal, even for the same instant).

    normalize_event_date_columns() only relabels already-naive timestamps as
    UTC (pd.to_datetime(..., utc=True) does not shift the clock when the
    input has no tz info) - so converting back (tz_convert('UTC').tz_localize(None))
    exactly reconstructs the original naive value, verified by round-trip.
    """
    if ts is None or pd.isna(ts):
        return ts
    ts = pd.Timestamp(ts)
    index_tz = getattr(reference_index, 'tz', None)

    if index_tz is None and ts.tzinfo is not None:
        return ts.tz_convert('UTC').tz_localize(None)
    if index_tz is not None and ts.tzinfo is None:
        return ts.tz_localize(index_tz)
    if index_tz is not None and ts.tzinfo is not None:
        return ts.tz_convert(index_tz)
    return ts


def to_ist_display(df, cols=DATE_LIKE_EVENT_COLUMNS):
    """Converts UTC-normalized date columns to Asia/Kolkata for display only.
    Internal storage/sorting/cutoff math stays in UTC (see normalize_event_date_columns);
    this is purely so tables and labels shown to the user read in IST, not UTC."""
    if df.empty:
        return df
    df = df.copy()
    for col in cols:
        if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]) and df[col].dt.tz is not None:
            df[col] = df[col].dt.tz_convert('Asia/Kolkata')
    return df


def find_confluence_events(df, window_bars=5, directions=('bullish', 'bearish'), require_divergence=True,
                            rsi_cross_threshold=3):
    """
    For each bar, checks whether the required signals have occurred with the
    SAME direction within the trailing `window_bars` bars. Flags the event
    only on the bar where the condition first becomes true (avoids
    re-flagging every subsequent bar).

    `directions` lets the caller restrict the scan to only bullish, only
    bearish, or both (default).

    `require_divergence` toggles whether RSI divergence is a required
    component. When False, confluence only needs the RSI cross-count and
    BB signal to align (divergence_date is still recorded if it happened to
    co-occur, purely informational, but doesn't gate the event). This is
    what lets you A/B the two definitions and see the difference divergence
    makes to the edge.

    `rsi_cross_threshold` is the Green_Count/Red_Count level that counts as
    an RSI cross-count "hit" (default 3). Lower it to loosen that gate and
    see whether more events surface without giving up divergence.

    Returns a DataFrame of confluence events with component trigger dates
    and the max bar-gap between the earliest and latest REQUIRED component.
    """
    n = len(df)
    rsi_dir = pd.Series(None, index=df.index, dtype=object)
    rsi_dir[df['Green_Count'] >= rsi_cross_threshold] = 'bullish'
    rsi_dir[df['Red_Count'] >= rsi_cross_threshold] = 'bearish'

    div_dir = pd.Series(None, index=df.index, dtype=object)
    div_dir[df['Bullish_Div']] = 'bullish'
    div_dir[df['Bearish_Div']] = 'bearish'

    bb_dir = pd.Series(None, index=df.index, dtype=object)
    bb_dir[df['BB_Signal'] == 'BUY'] = 'bullish'
    bb_dir[df['BB_Signal'] == 'SELL'] = 'bearish'

    events = []
    was_confluent = {d: False for d in directions}

    for i in range(n):
        lo = max(0, i - window_bars)
        window_idx = df.index[lo:i+1]

        for direction in directions:
            rsi_hits = [idx for idx in window_idx if rsi_dir.loc[idx] == direction]
            div_hits = [idx for idx in window_idx if div_dir.loc[idx] == direction]
            bb_hits = [idx for idx in window_idx if bb_dir.loc[idx] == direction]

            if require_divergence:
                currently_confluent = bool(rsi_hits) and bool(div_hits) and bool(bb_hits)
            else:
                currently_confluent = bool(rsi_hits) and bool(bb_hits)

            if currently_confluent and not was_confluent[direction]:
                rsi_date = rsi_hits[-1]
                div_date = div_hits[-1] if div_hits else None
                bb_date = bb_hits[-1]
                required_dates = [rsi_date, bb_date] + ([div_date] if require_divergence else [])
                gap_bars = df.index.get_loc(max(required_dates)) - df.index.get_loc(min(required_dates))

                events.append({
                    'confirm_date': df.index[i],
                    'direction': direction,
                    'close_at_confirm': float(df['close'].iloc[i]),
                    'rsi_cross_date': rsi_date,
                    'divergence_date': div_date,
                    'divergence_required': require_divergence,
                    'bb_signal_date': bb_date,
                    'max_gap_bars': gap_bars,
                    'confirm_bar_index': i
                })

            was_confluent[direction] = currently_confluent

    return pd.DataFrame(events)


def add_forward_returns(events_df, df, horizons=(1, 3, 5, 10)):
    """Adds forward return columns (in %) for each horizon, direction-adjusted
    (positive = the direction called it correctly)."""
    if events_df.empty:
        return events_df
    events_df = events_df.copy()
    n = len(df)
    for h in horizons:
        col = f'fwd_ret_{h}d_pct'
        vals = []
        for _, row in events_df.iterrows():
            idx = row['confirm_bar_index']
            if idx + h < n:
                entry_px = df['close'].iloc[idx]
                exit_px = df['close'].iloc[idx + h]
                raw_ret = (exit_px - entry_px) / entry_px * 100
                vals.append(raw_ret if row['direction'] == 'bullish' else -raw_ret)
            else:
                vals.append(np.nan)
        events_df[col] = vals
    return events_df


def simulate_trailing_stop(df, entry_idx, direction, trail_pct):
    """
    Enters at close[entry_idx]. Walks forward bar by bar tracking the running
    favorable extreme (highest close since entry for LONG, lowest for SHORT).
    Exits the bar the close retraces trail_pct from that extreme.
    Returns dict with exit_date, exit_price, pnl_pct, holding_bars, status.
    """
    n = len(df)
    entry_price = float(df['close'].iloc[entry_idx])
    extreme = entry_price

    for j in range(entry_idx + 1, n):
        px = float(df['close'].iloc[j])
        if direction == 'bullish':
            extreme = max(extreme, px)
            stop_level = extreme * (1 - trail_pct / 100)
            if px <= stop_level:
                pnl_pct = (px - entry_price) / entry_price * 100
                return {'exit_date': df.index[j], 'exit_price': px, 'pnl_pct': pnl_pct,
                        'holding_bars': j - entry_idx, 'status': 'CLOSED_TRAIL'}
        else:  # bearish / short
            extreme = min(extreme, px)
            stop_level = extreme * (1 + trail_pct / 100)
            if px >= stop_level:
                pnl_pct = (entry_price - px) / entry_price * 100
                return {'exit_date': df.index[j], 'exit_price': px, 'pnl_pct': pnl_pct,
                        'holding_bars': j - entry_idx, 'status': 'CLOSED_TRAIL'}

    # Never stopped out - still open as of last available bar
    last_px = float(df['close'].iloc[-1])
    pnl_pct = (last_px - entry_price) / entry_price * 100 if direction == 'bullish' else (entry_price - last_px) / entry_price * 100
    return {'exit_date': df.index[-1], 'exit_price': last_px, 'pnl_pct': pnl_pct,
            'holding_bars': n - 1 - entry_idx, 'status': 'OPEN'}


def simulate_fixed_target(df, entry_idx, direction, target_pct, stop_pct=0.0):
    """
    Enters at close[entry_idx]. Exits the first bar the close reaches a fixed
    target_pct move in the trade's favor ('CLOSED_TARGET'). If stop_pct > 0,
    also exits the first bar the close moves stop_pct against the trade
    ('CLOSED_STOP') - whichever is hit first. stop_pct = 0 disables the
    stop (target-only, rides to end of data if never hit).
    Returns dict with exit_date, exit_price, pnl_pct, holding_bars, status.
    """
    n = len(df)
    entry_price = float(df['close'].iloc[entry_idx])
    if direction == 'bullish':
        target_level = entry_price * (1 + target_pct / 100)
        stop_level = entry_price * (1 - stop_pct / 100) if stop_pct > 0 else None
    else:
        target_level = entry_price * (1 - target_pct / 100)
        stop_level = entry_price * (1 + stop_pct / 100) if stop_pct > 0 else None

    for j in range(entry_idx + 1, n):
        px = float(df['close'].iloc[j])
        hit_target = (px >= target_level) if direction == 'bullish' else (px <= target_level)
        hit_stop = stop_level is not None and ((px <= stop_level) if direction == 'bullish' else (px >= stop_level))
        if hit_target or hit_stop:
            pnl_pct = (px - entry_price) / entry_price * 100 if direction == 'bullish' else (entry_price - px) / entry_price * 100
            return {'exit_date': df.index[j], 'exit_price': px, 'pnl_pct': pnl_pct,
                    'holding_bars': j - entry_idx, 'status': 'CLOSED_TARGET' if hit_target else 'CLOSED_STOP'}

    last_px = float(df['close'].iloc[-1])
    pnl_pct = (last_px - entry_price) / entry_price * 100 if direction == 'bullish' else (entry_price - last_px) / entry_price * 100
    return {'exit_date': df.index[-1], 'exit_price': last_px, 'pnl_pct': pnl_pct,
            'holding_bars': n - 1 - entry_idx, 'status': 'OPEN'}


def simulate_bb_opposite(df, entry_idx, direction):
    """
    Enters at close[entry_idx]. Exits the first bar an OPPOSITE Bollinger
    Band signal fires after entry: a long (bullish) exits on the first
    'SELL' BB_Signal (close crossing above the upper band); a short
    (bearish) exits on the first 'BUY' BB_Signal (close crossing below the
    lower band). Requires df['BB_Signal'] to already be populated.
    Returns dict with exit_date, exit_price, pnl_pct, holding_bars, status.
    """
    n = len(df)
    entry_price = float(df['close'].iloc[entry_idx])
    opposite_signal = 'SELL' if direction == 'bullish' else 'BUY'
    bb_signal = df['BB_Signal']

    for j in range(entry_idx + 1, n):
        if bb_signal.iloc[j] == opposite_signal:
            px = float(df['close'].iloc[j])
            pnl_pct = (px - entry_price) / entry_price * 100 if direction == 'bullish' else (entry_price - px) / entry_price * 100
            return {'exit_date': df.index[j], 'exit_price': px, 'pnl_pct': pnl_pct,
                    'holding_bars': j - entry_idx, 'status': 'CLOSED_BB'}

    last_px = float(df['close'].iloc[-1])
    pnl_pct = (last_px - entry_price) / entry_price * 100 if direction == 'bullish' else (entry_price - last_px) / entry_price * 100
    return {'exit_date': df.index[-1], 'exit_price': last_px, 'pnl_pct': pnl_pct,
            'holding_bars': n - 1 - entry_idx, 'status': 'OPEN'}


def simulate_exit(df, entry_idx, direction, exit_method='trailing_stop',
                   trail_pct=1.0, target_pct=2.0, stop_pct=0.0):
    """Dispatches to the selected exit/target method. Same return shape
    (exit_date, exit_price, pnl_pct, holding_bars, status) regardless of
    method, so callers don't need to care which one was used."""
    if exit_method == 'fixed_target':
        return simulate_fixed_target(df, entry_idx, direction, target_pct, stop_pct)
    elif exit_method == 'bb_opposite':
        return simulate_bb_opposite(df, entry_idx, direction)
    else:
        return simulate_trailing_stop(df, entry_idx, direction, trail_pct)


def add_exit_results(events_df, df, exit_method='trailing_stop', trail_pct=1.0, target_pct=2.0, stop_pct=0.0):
    """
    Adds exit columns to each confluence event, using whichever exit/target
    method is selected: 'trailing_stop' (default, existing behaviour),
    'fixed_target' (fixed % target +/- optional fixed % stop), or
    'bb_opposite' (exit on the first opposite-direction Bollinger Band
    signal). Columns are still named trail_* for backward compatibility -
    every table, metric, and chart in this app reads those names regardless
    of which exit method actually produced them.
    """
    if events_df.empty:
        return events_df
    events_df = events_df.copy()
    exit_dates, exit_prices, pnl_pcts, holding_bars, statuses = [], [], [], [], []
    for _, row in events_df.iterrows():
        r = simulate_exit(df, row['confirm_bar_index'], row['direction'], exit_method,
                           trail_pct=trail_pct, target_pct=target_pct, stop_pct=stop_pct)
        exit_dates.append(r['exit_date'])
        exit_prices.append(r['exit_price'])
        pnl_pcts.append(r['pnl_pct'])
        holding_bars.append(r['holding_bars'])
        statuses.append(r['status'])
    events_df['trail_exit_date'] = exit_dates
    events_df['trail_exit_price'] = exit_prices
    events_df['trail_pnl_pct'] = pnl_pcts
    events_df['trail_holding_bars'] = holding_bars
    events_df['trail_status'] = statuses
    return events_df




def _normalize_ohlc_columns(data):
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.columns = [str(c).lower() for c in data.columns]
    return data


def fetch_yf_data(ticker, period, interval):
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False, timeout=15)
        if data.empty:
            return None
    except Exception:
        return None
    return _normalize_ohlc_columns(data)


def load_csv_data(uploaded_file):
    """
    Reads an uploaded OHLC CSV. Expects a date/datetime column plus
    open/high/low/close (volume optional), case-insensitive.

    Resets the stream position first - Streamlit's UploadedFile persists
    across reruns, so re-clicking Scan without re-uploading would otherwise
    read from wherever the pointer was left after the previous read (often
    EOF), silently returning nothing.
    """
    try:
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        raw = pd.read_csv(uploaded_file)
    except Exception:
        return None

    raw.columns = [str(c).strip().lower() for c in raw.columns]
    date_col = next((c for c in raw.columns if c in ('date', 'datetime', 'timestamp', 'time', 'dt')), None)
    if date_col is None:
        return None

    raw[date_col] = pd.to_datetime(raw[date_col])
    raw = raw.set_index(date_col).sort_index()

    required = ['open', 'high', 'low', 'close']
    if not all(c in raw.columns for c in required):
        return None
    if 'volume' not in raw.columns:
        raw['volume'] = 0

    return raw[['open', 'high', 'low', 'close', 'volume']]


def process_dataframe(ticker, data, window_bars, wilder, horizons, trail_pct,
                       directions=('bullish', 'bearish'), require_divergence=True, rsi_cross_threshold=3,
                       div_method='swing_pivot', div_window=5, div_min_price_pct=0.0, div_min_rsi_pts=0.0,
                       div_ob_level=60, div_os_level=40, div_max_gap_bars=20,
                       exit_method='trailing_stop', target_pct=2.0, stop_pct=0.0):
    """Shared indicator + confluence + backtest pipeline for any OHLC dataframe,
    regardless of whether it came from yfinance or an uploaded CSV."""
    data = data.copy()
    data['RSI'] = compute_rsi(data['close'], wilder=wilder)
    data['Red_Count'], data['Green_Count'] = count_zone_entries_with_reset(data['RSI'])

    if div_method == 'zone_extremum':
        (data['Bullish_Div'], data['Bearish_Div'],
         bull_pivot, bear_pivot,
         data['Bullish_Div_Ref'], data['Bearish_Div_Ref']) = detect_zone_extremum_divergence(
            data['close'], data['RSI'], ob_level=div_ob_level, os_level=div_os_level,
            min_price_change_pct=div_min_price_pct, min_rsi_change=div_min_rsi_pts,
            max_gap_bars=div_max_gap_bars
        )
        data['Bullish_Div_Pivot'] = bull_pivot
        data['Bearish_Div_Pivot'] = bear_pivot
    else:
        data['Bullish_Div'], data['Bearish_Div'], data['Bullish_Div_Ref'], data['Bearish_Div_Ref'] = detect_divergence(
            data['close'], data['RSI'], window=div_window,
            min_price_change_pct=div_min_price_pct, min_rsi_change=div_min_rsi_pts
        )
        # Swing-pivot method flags True directly at the pivot bar, so the
        # "pivot" is just the flagged bar's own timestamp.
        data['Bullish_Div_Pivot'] = pd.Series(pd.NaT, index=data.index, dtype=data.index.dtype)
        data['Bearish_Div_Pivot'] = pd.Series(pd.NaT, index=data.index, dtype=data.index.dtype)
        data.loc[data['Bullish_Div'], 'Bullish_Div_Pivot'] = data.index[data['Bullish_Div']]
        data.loc[data['Bearish_Div'], 'Bearish_Div_Pivot'] = data.index[data['Bearish_Div']]

    data['BB_Mid'], data['BB_Upper'], data['BB_Lower'] = compute_bollinger_bands(data['close'])
    data['BB_Signal'] = None
    data.loc[crossunder(data['close'], data['BB_Lower']), 'BB_Signal'] = 'BUY'
    data.loc[crossover(data['close'], data['BB_Upper']), 'BB_Signal'] = 'SELL'

    events = find_confluence_events(data, window_bars=window_bars, directions=directions,
                                     require_divergence=require_divergence, rsi_cross_threshold=rsi_cross_threshold)
    events = add_forward_returns(events, data, horizons=horizons)
    events = add_exit_results(events, data, exit_method=exit_method, trail_pct=trail_pct,
                               target_pct=target_pct, stop_pct=stop_pct)
    if not events.empty:
        events.insert(0, 'ticker', ticker)

    return {'ticker': ticker, 'data': data, 'events': events}


def scan_ticker(ticker, period, interval, window_bars, wilder, horizons, trail_pct,
                 directions=('bullish', 'bearish'), require_divergence=True, rsi_cross_threshold=3,
                 div_method='swing_pivot', div_window=5, div_min_price_pct=0.0, div_min_rsi_pts=0.0,
                 div_ob_level=60, div_os_level=40, div_max_gap_bars=20,
                 exit_method='trailing_stop', target_pct=2.0, stop_pct=0.0):
    data = fetch_yf_data(ticker, period, interval)
    if data is None:
        return None
    return process_dataframe(ticker, data, window_bars, wilder, horizons, trail_pct, directions,
                              require_divergence, rsi_cross_threshold,
                              div_method, div_window, div_min_price_pct, div_min_rsi_pts,
                              div_ob_level, div_os_level, div_max_gap_bars,
                              exit_method, target_pct, stop_pct)


def scan_uploaded_csv(ticker_name, uploaded_file, window_bars, wilder, horizons, trail_pct,
                       directions=('bullish', 'bearish'), require_divergence=True, rsi_cross_threshold=3,
                       div_method='swing_pivot', div_window=5, div_min_price_pct=0.0, div_min_rsi_pts=0.0,
                       div_ob_level=60, div_os_level=40, div_max_gap_bars=20,
                       exit_method='trailing_stop', target_pct=2.0, stop_pct=0.0):
    data = load_csv_data(uploaded_file)
    if data is None:
        return None
    return process_dataframe(ticker_name, data, window_bars, wilder, horizons, trail_pct, directions,
                              require_divergence, rsi_cross_threshold,
                              div_method, div_window, div_min_price_pct, div_min_rsi_pts,
                              div_ob_level, div_os_level, div_max_gap_bars,
                              exit_method, target_pct, stop_pct)


def render_event_chart(data, ticker, event_row, window_bars):
    confirm_date = event_row['confirm_date']
    entry_price = event_row['close_at_confirm']
    direction = event_row['direction']
    exit_date = event_row.get('trail_exit_date')
    exit_price = event_row.get('trail_exit_price')
    pnl_pct = event_row.get('trail_pnl_pct')
    trail_status = event_row.get('trail_status')

    confirm_date_for_lookup = align_ts_to_index(confirm_date, data.index)
    exit_date_for_lookup = align_ts_to_index(exit_date, data.index) if exit_date is not None else None

    idx = data.index.get_loc(confirm_date_for_lookup)
    exit_idx = data.index.get_loc(exit_date_for_lookup) if exit_date_for_lookup is not None and exit_date_for_lookup in data.index else idx
    lo = max(0, idx - window_bars - 15)
    hi = min(len(data), max(idx + 15, exit_idx + 10))

    # Keep an original-timezone copy for reference-pivot lookups (a
    # divergence's earlier compared pivot can fall outside this window),
    # and a separate IST-shifted copy purely for what gets plotted.
    chunk = data.iloc[lo:hi].copy()
    chunk_index_orig = chunk.index

    chunk_ist = chunk.copy()
    chunk_ist.index = shift_index_to_ist(chunk.index)
    confirm_date_ist = shift_index_to_ist(confirm_date)
    exit_date_ist = shift_index_to_ist(exit_date) if exit_date is not None else None

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                         row_heights=[0.65, 0.35],
                         subplot_titles=(f"{ticker} - Confluence @ {confirm_date.date()} (IST)", "RSI"))

    fig.add_trace(go.Scatter(x=chunk_ist.index, y=chunk_ist['close'], name='Close', line=dict(color='black')), row=1, col=1)
    fig.add_trace(go.Scatter(x=chunk_ist.index, y=chunk_ist['BB_Upper'], name='BB Upper', line=dict(color='gray', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=chunk_ist.index, y=chunk_ist['BB_Lower'], name='BB Lower', line=dict(color='gray', dash='dot')), row=1, col=1)

    # --- Divergence markers + connecting line to the earlier compared pivot ---
    # Marker is placed at the PIVOT bar (the actual RSI extreme), not the
    # confirmation bar - for the zone-extremum method these can differ (the
    # extreme is only confirmed once RSI exits the zone, which can be many
    # bars later). For the swing-pivot method pivot == confirmation bar, so
    # this is a no-op change there. Without the connecting line, a marker
    # like "bearish div at RSI 65" looks bullish in isolation - it only
    # makes sense next to the prior, higher-RSI peak it lost to. If that
    # earlier pivot falls inside the visible window we draw a dotted line
    # straight to it (on both price and RSI panels); if it's further back
    # than the window shows, we annotate instead of stretching the x-axis.
    for div_col, ref_col, pivot_col, color, price_symbol, rsi_symbol, label in [
        ('Bullish_Div', 'Bullish_Div_Ref', 'Bullish_Div_Pivot', '#00cc44', 'circle', 'triangle-up', 'Bullish'),
        ('Bearish_Div', 'Bearish_Div_Ref', 'Bearish_Div_Pivot', '#e60000', 'circle', 'triangle-down', 'Bearish'),
    ]:
        flagged = chunk[chunk[div_col]]  # original-tz copy, so ref/pivot timestamps match data.index directly
        first_marker = True
        for confirm_ts, row in flagged.iterrows():
            ref_time = row[ref_col]
            if pd.isna(ref_time):
                continue
            pivot_time = row[pivot_col] if pd.notna(row[pivot_col]) else confirm_ts
            if pivot_time not in data.index or ref_time not in data.index:
                continue

            pivot_price = data.loc[pivot_time, 'close']
            pivot_rsi = data.loc[pivot_time, 'RSI']
            ref_price = data.loc[ref_time, 'close']
            ref_rsi = data.loc[ref_time, 'RSI']
            pivot_ts_ist = shift_index_to_ist(pivot_time)

            fig.add_trace(go.Scatter(
                x=[pivot_ts_ist], y=[pivot_price], mode='markers',
                marker=dict(color=color, size=11, symbol=price_symbol, line=dict(color='black', width=1)),
                name=f'{label} Div (Price)', showlegend=first_marker
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=[pivot_ts_ist], y=[pivot_rsi], mode='markers',
                marker=dict(color=color, size=11, symbol=rsi_symbol, line=dict(color='black', width=1)),
                name=f'{label} Div (RSI)', showlegend=first_marker
            ), row=2, col=1)
            first_marker = False

            if ref_time in chunk_index_orig and pivot_time in chunk_index_orig:
                ref_ts_ist = shift_index_to_ist(ref_time)
                fig.add_trace(go.Scatter(
                    x=[ref_ts_ist, pivot_ts_ist], y=[ref_price, pivot_price],
                    mode='lines+markers', line=dict(color=color, dash='dot', width=1.5),
                    marker=dict(color=color, size=6, symbol='circle-open'),
                    showlegend=False
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=[ref_ts_ist, pivot_ts_ist], y=[ref_rsi, pivot_rsi],
                    mode='lines+markers', line=dict(color=color, dash='dot', width=1.5),
                    marker=dict(color=color, size=6, symbol='circle-open'),
                    showlegend=False
                ), row=2, col=1)
            else:
                # Reference pivot is off-screen (further back than this
                # window) - annotate on the RSI panel so it's still clear
                # what the divergence is being measured against.
                fig.add_annotation(
                    x=pivot_ts_ist, y=pivot_rsi, xref='x2', yref='y2',
                    text=f"{label} div vs {ref_time.date()} (RSI {ref_rsi:.0f})",
                    showarrow=True, arrowhead=2, ax=0, ay=-28,
                    font=dict(size=9, color=color), bgcolor='rgba(255,255,255,0.75)'
                )

    bb_pts = chunk_ist[chunk_ist['BB_Signal'].notna()]
    if not bb_pts.empty:
        colors = ['blue' if s == 'BUY' else 'magenta' for s in bb_pts['BB_Signal']]
        fig.add_trace(go.Scatter(x=bb_pts.index, y=bb_pts['close'], mode='markers',
                                 marker=dict(color=colors, size=12, symbol='star'), name='BB Signal'), row=1, col=1)

    fig.add_vline(x=confirm_date_ist, line_dash="dash", line_color="orange", row=1, col=1)
    fig.add_vline(x=confirm_date_ist, line_dash="dash", line_color="orange", row=2, col=1)

    # --- Entry marker ---
    entry_color = 'green' if direction == 'bullish' else 'red'
    entry_symbol = 'triangle-up' if direction == 'bullish' else 'triangle-down'
    fig.add_trace(go.Scatter(
        x=[confirm_date_ist], y=[entry_price], mode='markers+text',
        marker=dict(color=entry_color, size=18, symbol=entry_symbol, line=dict(color='black', width=1)),
        text=['ENTRY'], textposition='bottom center',
        name=f'Entry ({direction})'
    ), row=1, col=1)

    # --- Exit marker + connecting line ---
    if exit_date_ist is not None and exit_price is not None:
        exit_color = 'green' if (pnl_pct is not None and pnl_pct > 0) else 'red'
        exit_symbol_map = {
            'CLOSED_TRAIL': 'x', 'CLOSED_TARGET': 'star', 'CLOSED_STOP': 'x',
            'CLOSED_BB': 'diamond', 'OPEN': 'circle-open',
        }
        exit_name_map = {
            'CLOSED_TRAIL': 'Exit (trailing stop)', 'CLOSED_TARGET': 'Exit (fixed target hit)',
            'CLOSED_STOP': 'Exit (fixed stop hit)', 'CLOSED_BB': 'Exit (opposite BB signal)',
            'OPEN': 'Exit (still open, last close)',
        }
        exit_symbol = exit_symbol_map.get(trail_status, 'circle-open')
        exit_label = f"EXIT ({pnl_pct:+.2f}%)" if pnl_pct is not None else "EXIT"

        fig.add_trace(go.Scatter(
            x=[confirm_date_ist, exit_date_ist], y=[entry_price, exit_price],
            mode='lines', line=dict(color=exit_color, dash='dash', width=1.5),
            showlegend=False
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=[exit_date_ist], y=[exit_price], mode='markers+text',
            marker=dict(color=exit_color, size=16, symbol=exit_symbol, line=dict(color='black', width=1)),
            text=[exit_label], textposition='top center',
            name=exit_name_map.get(trail_status, 'Exit')
        ), row=1, col=1)

    fig.add_trace(go.Scatter(x=chunk_ist.index, y=chunk_ist['RSI'], name='RSI', line=dict(color='blue')), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.update_xaxes(title_text="Time (IST)", row=2, col=1)
    fig.update_layout(height=600, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)


# --------------------------
# Portfolio Tracker - storage & engine (separate CSV file from the
# main rsiscanner_portfolio_tracker.py app - fully independent)
# --------------------------
PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "confluence_portfolio_positions.csv")

PORTFOLIO_COLUMNS = [
    "id", "ticker", "signal", "direction", "timeframe", "entry_date", "entry_price",
    "sl_price", "target_price", "qty", "status", "exit_date", "exit_price",
    "exit_reason", "pnl", "pnl_pct", "notes", "created_at"
]

TEXT_COLUMNS = ["ticker", "signal", "direction", "timeframe", "entry_date", "status",
                "exit_date", "exit_reason", "notes", "id", "created_at"]
NUMERIC_COLUMNS = ["entry_price", "sl_price", "target_price", "qty", "exit_price", "pnl", "pnl_pct"]


def _enforce_dtypes(df):
    df = df.copy()
    for col in TEXT_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(object)
            df[col] = df[col].where(df[col].notna(), "")
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            df = pd.read_csv(PORTFOLIO_FILE, dtype=str)
            for col in PORTFOLIO_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            df = df[PORTFOLIO_COLUMNS]
            return _enforce_dtypes(df)
        except Exception:
            pass
    df = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    return _enforce_dtypes(df)


def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False)


def compute_pnl(direction, entry_price, exit_price, qty):
    if direction == "LONG":
        pnl = (exit_price - entry_price) * qty
    else:
        pnl = (entry_price - exit_price) * qty
    pnl_pct = (pnl / (entry_price * qty)) * 100 if entry_price and qty else 0.0
    return pnl, pnl_pct


def fetch_last_price(ticker):
    """Best-effort latest close for a ticker (Yahoo Finance only - not for
    positions sourced from an uploaded CSV, which won't have a live feed)."""
    try:
        hist = yf.download(ticker, period="5d", interval="1d", progress=False, timeout=15)
        hist = _normalize_ohlc_columns(hist)
        if not hist.empty:
            return float(hist["close"].iloc[-1])
    except Exception:
        pass
    return None


def check_and_update_positions(df):
    """
    Walks daily bars from entry_date onward for each OPEN position and checks
    for SL/Target hits. If SL and Target are both breached on the same bar,
    SL is assumed to trigger first (conservative convention, same as the
    main portfolio tracker app).
    Returns (updated_df, list_of_close_events).
    """
    df = _enforce_dtypes(df)
    close_events = []

    open_mask = df["status"] == "OPEN"
    for idx in df[open_mask].index:
        row = df.loc[idx]
        ticker = row["ticker"]
        direction = row["direction"]
        entry_price = float(row["entry_price"])
        sl_price = float(row["sl_price"])
        target_price = float(row["target_price"])
        qty = float(row["qty"])
        entry_date_str = str(row["entry_date"])

        try:
            hist = yf.download(ticker, start=entry_date_str, interval="1d", progress=False, timeout=15)
            hist = _normalize_ohlc_columns(hist)
        except Exception:
            continue

        if hist.empty:
            continue

        hit = None
        for bar_date, bar in hist.iterrows():
            bar_low = float(bar["low"])
            bar_high = float(bar["high"])

            if direction == "LONG":
                sl_breach = bar_low <= sl_price
                target_breach = bar_high >= target_price
            else:  # SHORT
                sl_breach = bar_high >= sl_price
                target_breach = bar_low <= target_price

            if sl_breach:
                hit = ("CLOSED_SL", sl_price, bar_date)
                break
            elif target_breach:
                hit = ("CLOSED_TARGET", target_price, bar_date)
                break

        if hit:
            status, exit_price, exit_date = hit
            pnl, pnl_pct = compute_pnl(direction, entry_price, exit_price, qty)
            df.loc[idx, "status"] = status
            df.loc[idx, "exit_date"] = pd.Timestamp(exit_date).strftime("%Y-%m-%d")
            df.loc[idx, "exit_price"] = round(exit_price, 2)
            df.loc[idx, "exit_reason"] = "Stop-loss hit" if status == "CLOSED_SL" else "Target hit"
            df.loc[idx, "pnl"] = round(pnl, 2)
            df.loc[idx, "pnl_pct"] = round(pnl_pct, 2)
            close_events.append({"ticker": ticker, "status": status, "exit_price": exit_price, "pnl": pnl})

    return df, close_events


def close_position_manual(df, position_id, exit_price):
    df = _enforce_dtypes(df)
    idx = df[df["id"] == position_id].index
    if len(idx) == 0:
        return df
    idx = idx[0]
    direction = df.loc[idx, "direction"]
    entry_price = float(df.loc[idx, "entry_price"])
    qty = float(df.loc[idx, "qty"])
    pnl, pnl_pct = compute_pnl(direction, entry_price, exit_price, qty)
    df.loc[idx, "status"] = "CLOSED_MANUAL"
    df.loc[idx, "exit_date"] = date.today().strftime("%Y-%m-%d")
    df.loc[idx, "exit_price"] = round(exit_price, 2)
    df.loc[idx, "exit_reason"] = "Manually closed"
    df.loc[idx, "pnl"] = round(pnl, 2)
    df.loc[idx, "pnl_pct"] = round(pnl_pct, 2)
    return df


# --------------------------
# Streamlit UI
# --------------------------
st.set_page_config(page_title="Triple Signal Confluence Scanner", layout="wide")
st.title("🔬 Triple Signal Confluence Scanner")
st.caption("RSI cross count + RSI divergence + BB signal, clustering within a small trailing window. "
           "Standalone research tool - does not touch the portfolio tracker app.")

# --------------------------
# Page / navigation state
# --------------------------
SCANNER_PAGES = ["15 Min Scanner", "1 Hour Scanner", "Daily Scanner"]
ALL_PAGES = SCANNER_PAGES + ["Portfolio Setup", "Portfolio Tracker"]

if "app_page" not in st.session_state:
    st.session_state["app_page"] = "Daily Scanner"
if "portfolio_draft" not in st.session_state:
    st.session_state["portfolio_draft"] = []
if "last_scanner_page" not in st.session_state:
    st.session_state["last_scanner_page"] = "Daily Scanner"
if "last_scanner_page_label" not in st.session_state:
    st.session_state["last_scanner_page_label"] = "Daily Scanner"

st.sidebar.header("📍 Navigation")
nav_choice = st.sidebar.radio("Go to", ALL_PAGES, index=ALL_PAGES.index(st.session_state["app_page"]))
st.session_state["app_page"] = nav_choice

INTERVAL_PERIOD_LIMITS = {
    "1m":  ["1d", "5d", "7d"],
    "2m":  ["1d", "5d", "1mo", "60d"],
    "5m":  ["1d", "5d", "1mo", "60d"],
    "15m": ["1d", "5d", "1mo", "60d"],
    "30m": ["1d", "5d", "1mo", "60d"],
    "1h":  ["5d", "1mo", "3mo", "6mo", "1y", "2y"],
    "1d":  ["1mo", "3mo", "6mo", "1y", "2y", "5y"],

}
RESAMPLE_RULE_BY_INTERVAL = {"15m": "15min", "1h": "1h", "1d": "1D","1w": "1W" }


def render_scanner_page(page_key, fixed_interval, page_label):
    """Renders a full scanner page fixed to one timeframe. page_key namespaces
    all session-state keys and widget keys so the three scanner pages (15 Min,
    1 Hour, Daily) each keep their own independent results and settings."""

    st.session_state["last_scanner_page"] = page_key
    st.session_state["last_scanner_page_label"] = f"{page_label} Scanner"

    st.sidebar.divider()
    st.sidebar.header(f"Settings — {page_label}")

    data_source = st.sidebar.radio("Data Source", ["Yahoo Finance", "Upload CSV"], key=f"{page_key}_data_source")

    if data_source == "Yahoo Finance":
        valid_periods = INTERVAL_PERIOD_LIMITS.get(fixed_interval, ["1y"])
        period = st.sidebar.selectbox("Period", valid_periods, index=len(valid_periods) - 1, key=f"{page_key}_period")
        if fixed_interval in ("15m",):
            st.sidebar.caption(f"⚠️ {fixed_interval} data is limited to a max lookback of {valid_periods[-1]} by the data provider.")
        custom_tickers = st.sidebar.text_area("Custom tickers (one per line, blank = full Nifty F&O list)",
                                               value="", key=f"{page_key}_tickers")
        uploaded_files = None
    else:
        st.sidebar.caption(f"CSV needs a date/datetime column plus open, high, low, close (volume optional). "
                            f"Automatically resampled to {page_label} bars if it's finer-grained (e.g. 5-min data).")
        uploaded_files = st.sidebar.file_uploader("Upload OHLC CSV(s)", type=["csv"], accept_multiple_files=True,
                                                    key=f"{page_key}_uploader")
        period, custom_tickers = None, ""

    interval = fixed_interval

    wilder = st.sidebar.checkbox("Use Wilder's smoothing", value=False, key=f"{page_key}_wilder")
    window_bars = st.sidebar.slider("Confluence window (bars)", min_value=1, max_value=20, value=5,
                                     help="How close together (in bars) the 3 signals must occur to count as confluence.",
                                     key=f"{page_key}_window")

    require_divergence = st.sidebar.checkbox(
        "Require Divergence for Confluence", value=True,
        help="Untick to test RSI cross-count + BB signal alone, without needing divergence to also align.",
        key=f"{page_key}_reqdiv"
    )

    rsi_cross_threshold = st.sidebar.slider(
        "RSI Cross Count Threshold", min_value=1, max_value=6, value=1,
        help="How many times RSI must re-enter the 70/30 zone (with reset) before it counts as a hit. "
             "Default is 1 - a single zone re-entry is enough, per backtesting.",
        key=f"{page_key}_rsithresh"
    )

    divergence_filter = st.sidebar.selectbox(
        "Divergence Direction Filter", ["Both", "Bullish only", "Bearish only"],
        help="Restrict the confluence scan to only bullish setups, only bearish, or both.",
        key=f"{page_key}_dirfilter"
    )
    if divergence_filter == "Bullish only":
        directions = ("bullish",)
    elif divergence_filter == "Bearish only":
        directions = ("bearish",)
    else:
        directions = ("bullish", "bearish")

    with st.sidebar.expander("Divergence Parameters (advanced)", expanded=False):
        div_method_label = st.radio(
            "Divergence Method",
            ["Swing Pivot (5-bar highs/lows)", "RSI Zone Extremum (60/40)"],
            index=0,
            help="Swing Pivot: compares consecutive local price/RSI swing highs or lows, "
                 "wherever they occur, regardless of RSI level. "
                 "RSI Zone Extremum: after RSI crosses above the overbought level, tracks the "
                 "highest RSI reached until it drops back below that level (and symmetrically "
                 "for oversold/lowest RSI) - then compares that excursion's extreme against "
                 "the previous excursion's extreme, same idea as the standard "
                 "'RSI/CCI/Momentum trend-line divergence' Pine Script indicator.",
            key=f"{page_key}_divmethod"
        )
        div_method = 'zone_extremum' if div_method_label.startswith('RSI Zone') else 'swing_pivot'

        if div_method == 'swing_pivot':
            div_window = st.slider(
                "Pivot window (bars)", min_value=2, max_value=20, value=5,
                help="Bars on each side a swing high/low must beat to count as a pivot. "
                     "Larger = fewer, more significant pivots (less noise, later signals). "
                     "Smaller = more pivots (more signals, more noise).",
                key=f"{page_key}_divwindow"
            )
            div_ob_level, div_os_level, div_max_gap_bars = 60, 40, 20  # unused in this method
        else:
            div_window = 5  # unused in this method
            div_ob_level = st.slider(
                "Overbought level (bearish div trigger)", min_value=50, max_value=85, value=60,
                help="RSI must cross above this to start tracking an overbought excursion. "
                     "The highest RSI reached before it drops back below this level becomes "
                     "that excursion's peak, compared against the previous excursion's peak.",
                key=f"{page_key}_divoblevel"
            )
            div_os_level = st.slider(
                "Oversold level (bullish div trigger)", min_value=15, max_value=50, value=40,
                help="RSI must cross below this to start tracking an oversold excursion. "
                     "The lowest RSI reached before it rises back above this level becomes "
                     "that excursion's trough, compared against the previous excursion's trough.",
                key=f"{page_key}_divoslevel"
            )
            div_max_gap_bars = st.slider(
                "Max bar gap between compared pivots", min_value=0, max_value=200, value=20,
                help="Maximum bar distance allowed between the two excursion extremes being "
                     "compared. 0 = no limit. Prevents pairing two excursions so far apart in "
                     "time that comparing them isn't meaningful - same 'Maximum bar gap between "
                     "pivot points' control as the reference Pine Script.",
                key=f"{page_key}_divmaxgap"
            )
        div_min_price_pct = st.slider(
            "Min price move between pivots (%)", min_value=0.0, max_value=5.0, value=0.0, step=0.05,
            help="Minimum % price change between the two compared pivots for a divergence "
                 "to be counted. 0 = no filter (original behaviour). Raise this to drop divergences "
                 "formed by two nearly-flat price pivots.",
            key=f"{page_key}_divminprice"
        )
        div_min_rsi_pts = st.slider(
            "Min RSI move between pivots (points)", min_value=0.0, max_value=20.0, value=0.0, step=0.5,
            help="Minimum absolute RSI point change between the two compared pivots for a "
                 "divergence to be counted. 0 = no filter (original behaviour). Raise this to drop "
                 "divergences where RSI barely moved.",
            key=f"{page_key}_divminrsi"
        )

    horizons_input = st.sidebar.text_input("Forward return horizons (bars, comma-separated)", value="1,3,5,10",
                                            key=f"{page_key}_horizons")
    horizons = tuple(int(h.strip()) for h in horizons_input.split(",") if h.strip())

    exit_method_label = st.sidebar.selectbox(
        "Exit / Target Method",
        ["Trailing Stop %", "Fixed Target %", "Bollinger Opposite Band Signal"],
        index=0,
        help="Trailing Stop: exits when price retraces a fixed % from the best close since entry. "
             "Fixed Target: exits at a fixed % profit target, optionally with a fixed % protective stop. "
             "Bollinger Opposite Band: exits on the first opposite-direction Bollinger Band signal after "
             "entry (a long exits on the next SELL/upper-band signal, a short on the next BUY/lower-band signal).",
        key=f"{page_key}_exitmethod"
    )
    if exit_method_label == "Fixed Target %":
        exit_method = 'fixed_target'
        trail_pct = 1.0  # unused
        target_pct = st.sidebar.number_input("Target %", min_value=0.1, max_value=50.0, value=2.0, step=0.1,
                                              help="Exits once price moves this % in the trade's favor from entry.",
                                              key=f"{page_key}_targetpct")
        stop_pct = st.sidebar.number_input("Protective stop % (0 = no stop)", min_value=0.0, max_value=50.0,
                                            value=0.0, step=0.1,
                                            help="Exits once price moves this % against the trade from entry. "
                                                 "Set to 0 to disable - trade then only exits on target hit "
                                                 "or runs to the end of available data.",
                                            key=f"{page_key}_stoppct")
    elif exit_method_label == "Bollinger Opposite Band Signal":
        exit_method = 'bb_opposite'
        trail_pct = 1.0  # unused
        target_pct, stop_pct = 2.0, 0.0  # unused
        st.sidebar.caption("Exits on the first opposite Bollinger Band signal after entry. No extra parameters.")
    else:
        exit_method = 'trailing_stop'
        target_pct, stop_pct = 2.0, 0.0  # unused
        trail_pct = st.sidebar.number_input("Trailing stop %", min_value=0.1, max_value=20.0, value=1.0, step=0.1,
                                             help="Exits when price retraces this % from the best close since entry.",
                                             key=f"{page_key}_trail")

    scan_button = st.sidebar.button("🔍 Run Confluence Scan", key=f"{page_key}_scanbtn")
    compare_button = st.sidebar.button(
        "⚖️ Compare With vs Without Divergence",
        help="Runs the scan twice (divergence required, divergence not required) and shows both side by side.",
        key=f"{page_key}_comparebtn"
    )

    resample_rule = RESAMPLE_RULE_BY_INTERVAL[fixed_interval]

    def _scan_uploaded_resampled(ticker_name, f):
        raw = load_csv_data(f)
        if raw is None:
            return None
        resampled = raw.resample(resample_rule).agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        ).dropna()
        return process_dataframe(ticker_name, resampled, window_bars, wilder, horizons, trail_pct,
                                  directions, require_divergence, rsi_cross_threshold,
                                  div_method, div_window, div_min_price_pct, div_min_rsi_pts,
                                  div_ob_level, div_os_level, div_max_gap_bars,
                                  exit_method, target_pct, stop_pct)

    ev_key = f"{page_key}_confluence_events"
    data_key = f"{page_key}_confluence_ticker_data"
    window_key = f"{page_key}_confluence_window_bars"
    horizons_key = f"{page_key}_confluence_horizons"
    trail_key = f"{page_key}_confluence_trail_pct"

    if scan_button:
        all_events = []
        per_ticker_data = {}

        if data_source == "Yahoo Finance":
            ticker_list = [t.strip() for t in custom_tickers.split('\n') if t.strip()] if custom_tickers.strip() else NIFTY_FO_TICKERS
            st.subheader(f"Scanning {len(ticker_list)} tickers for confluence...")
            progress = st.progress(0)
            for i, ticker in enumerate(ticker_list):
                result = scan_ticker(ticker, period, interval, window_bars, wilder, horizons, trail_pct,
                                      directions, require_divergence, rsi_cross_threshold,
                                      div_method, div_window, div_min_price_pct, div_min_rsi_pts,
                                      div_ob_level, div_os_level, div_max_gap_bars,
                                      exit_method, target_pct, stop_pct)
                if result:
                    per_ticker_data[ticker] = result['data']
                    if not result['events'].empty:
                        all_events.append(result['events'])
                progress.progress((i + 1) / len(ticker_list))
            progress.empty()
        else:
            if not uploaded_files:
                st.warning("Upload at least one CSV file to scan.")
            else:
                progress = st.progress(0)
                for i, f in enumerate(uploaded_files):
                    ticker_name = f.name.rsplit(".", 1)[0]
                    result = _scan_uploaded_resampled(ticker_name, f)
                    if result is None:
                        st.error(f"Could not parse {f.name} - check it has date/open/high/low/close columns.")
                        continue
                    per_ticker_data[ticker_name] = result['data']
                    if not result['events'].empty:
                        all_events.append(result['events'])
                    progress.progress((i + 1) / len(uploaded_files))
                progress.empty()

        events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
        events_df = normalize_event_date_columns(events_df)

        st.session_state[ev_key] = events_df
        st.session_state[data_key] = per_ticker_data
        st.session_state[window_key] = window_bars
        st.session_state[horizons_key] = horizons
        st.session_state[trail_key] = trail_pct

    if compare_button:
        def _run_variant(require_div):
            variant_events = []
            if data_source == "Yahoo Finance":
                ticker_list = [t.strip() for t in custom_tickers.split('\n') if t.strip()] if custom_tickers.strip() else NIFTY_FO_TICKERS
                for ticker in ticker_list:
                    result = scan_ticker(ticker, period, interval, window_bars, wilder, horizons, trail_pct,
                                          directions, require_div, rsi_cross_threshold,
                                          div_method, div_window, div_min_price_pct, div_min_rsi_pts,
                                          div_ob_level, div_os_level, div_max_gap_bars,
                                          exit_method, target_pct, stop_pct)
                    if result and not result['events'].empty:
                        variant_events.append(result['events'])
            else:
                if uploaded_files:
                    for f in uploaded_files:
                        ticker_name = f.name.rsplit(".", 1)[0]
                        f.seek(0)
                        raw = load_csv_data(f)
                        if raw is None:
                            continue
                        resampled = raw.resample(resample_rule).agg(
                            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
                        ).dropna()
                        result = process_dataframe(ticker_name, resampled, window_bars, wilder, horizons, trail_pct,
                                                    directions, require_div, rsi_cross_threshold,
                                                    div_method, div_window, div_min_price_pct, div_min_rsi_pts,
                                                    div_ob_level, div_os_level, div_max_gap_bars,
                                                    exit_method, target_pct, stop_pct)
                        if result and not result['events'].empty:
                            variant_events.append(result['events'])
            return normalize_event_date_columns(pd.concat(variant_events, ignore_index=True) if variant_events else pd.DataFrame())

        if data_source == "Upload CSV" and not uploaded_files:
            st.warning("Upload at least one CSV file to compare.")
        else:
            with st.spinner("Running scan with divergence required..."):
                events_with_div = _run_variant(True)
            with st.spinner("Running scan without divergence required..."):
                events_without_div = _run_variant(False)

            st.subheader("⚖️ With Divergence vs Without Divergence")

            def _variant_stats(ev):
                if ev.empty:
                    return {'Events': 0, 'Total PnL %': np.nan, 'Win Rate %': np.nan, 'Avg PnL %': np.nan,
                            'Median PnL %': np.nan, 'Profit Factor': np.nan, 'Avg Hold (bars)': np.nan}
                wins = ev[ev['trail_pnl_pct'] > 0]
                gross_profit = ev.loc[ev['trail_pnl_pct'] > 0, 'trail_pnl_pct'].sum()
                gross_loss = abs(ev.loc[ev['trail_pnl_pct'] < 0, 'trail_pnl_pct'].sum())
                pf = gross_profit / gross_loss if gross_loss > 0 else np.nan
                return {
                    'Events': len(ev),
                    'Total PnL %': round(ev['trail_pnl_pct'].sum(), 3),
                    'Win Rate %': round(len(wins) / len(ev) * 100, 1),
                    'Avg PnL %': round(ev['trail_pnl_pct'].mean(), 3),
                    'Median PnL %': round(ev['trail_pnl_pct'].median(), 3),
                    'Profit Factor': round(pf, 2) if not np.isnan(pf) else np.nan,
                    'Avg Hold (bars)': round(ev['trail_holding_bars'].mean(), 1),
                }

            stats_with = _variant_stats(events_with_div)
            stats_without = _variant_stats(events_without_div)
            compare_df = pd.DataFrame({
                'Metric': list(stats_with.keys()),
                'With Divergence': list(stats_with.values()),
                'Without Divergence': list(stats_without.values()),
            })
            st.dataframe(compare_df, use_container_width=True, hide_index=True)

            extra_events = len(events_without_div) - len(events_with_div)
            if extra_events > 0:
                st.caption(f"Dropping divergence as a requirement surfaces {extra_events} additional event(s) "
                           f"(RSI cross-count + BB signal only). Compare the Win Rate / PF rows above to see "
                           f"whether those extra events help or dilute the edge.")
            elif extra_events == 0 and len(events_with_div) > 0:
                st.caption("Same event count either way - divergence wasn't the binding constraint in this sample.")

            st.session_state[ev_key] = events_with_div if not events_with_div.empty else events_without_div
            st.session_state[data_key] = {}
            if data_source == "Yahoo Finance":
                for ticker in ([t.strip() for t in custom_tickers.split('\n') if t.strip()] if custom_tickers.strip() else NIFTY_FO_TICKERS):
                    d = fetch_yf_data(ticker, period, interval)
                    if d is not None:
                        st.session_state[data_key][ticker] = d
            st.session_state[window_key] = window_bars
            st.session_state[horizons_key] = horizons
            st.session_state[trail_key] = trail_pct

    if ev_key in st.session_state:
        events_df = st.session_state[ev_key]
        horizons = st.session_state.get(horizons_key, horizons)

        if events_df.empty:
            st.warning("No confluence events found with the current settings. Try widening the window, period, or divergence filter.")
        else:
            st.subheader("📊 Numerical Summary")

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Confluence Events", len(events_df))
            c2.metric("Bullish Events", int((events_df['direction'] == 'bullish').sum()))
            c3.metric("Bearish Events", int((events_df['direction'] == 'bearish').sum()))

            exit_method_desc = {
                'trailing_stop': f"Trailing {st.session_state.get(trail_key, trail_pct)}% Stop Exit",
                'fixed_target': f"Fixed {target_pct}% Target" + (f" / {stop_pct}% Stop" if stop_pct > 0 else " (no stop)") + " Exit",
                'bb_opposite': "Bollinger Opposite Band Signal Exit",
            }
            st.markdown(f"#### {exit_method_desc.get(exit_method, 'Exit')}")
            trail_wins = events_df[events_df['trail_pnl_pct'] > 0]
            trail_win_rate = len(trail_wins) / len(events_df) * 100 if len(events_df) else np.nan
            gross_profit = events_df.loc[events_df['trail_pnl_pct'] > 0, 'trail_pnl_pct'].sum()
            gross_loss = abs(events_df.loc[events_df['trail_pnl_pct'] < 0, 'trail_pnl_pct'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else np.nan
            total_pnl_pct = events_df['trail_pnl_pct'].sum()

            t1, t2, t3, t4, t5, t6 = st.columns(6)
            t1.metric("Total PnL", f"{total_pnl_pct:+.2f}%")
            t2.metric("Win Rate", f"{trail_win_rate:.1f}%")
            t3.metric("Avg PnL", f"{events_df['trail_pnl_pct'].mean():.2f}%")
            t4.metric("Median PnL", f"{events_df['trail_pnl_pct'].median():.2f}%")
            t5.metric("Avg Holding (bars)", f"{events_df['trail_holding_bars'].mean():.1f}")
            t6.metric("Profit Factor", f"{pf:.2f}" if not np.isnan(pf) else "—")
            st.caption(
                f"Total PnL is the simple sum of each trade's % return (not compounded), "
                f"across {len(events_df)} event(s). Gross profit {gross_profit:.2f}% / gross loss {gross_loss:.2f}%."
            )

            still_open = (events_df['trail_status'] == 'OPEN').sum()
            if still_open:
                st.caption(f"{still_open} event(s) never hit the trailing stop within available data - still open, using last close as mark.")

            with st.expander("Trailing-stop breakdown by direction"):
                for direction in ['bullish', 'bearish']:
                    sub = events_df[events_df['direction'] == direction]
                    if sub.empty:
                        continue
                    sub_wins = sub[sub['trail_pnl_pct'] > 0]
                    wr = len(sub_wins) / len(sub) * 100 if len(sub) else np.nan
                    st.write(f"**{direction.capitalize()}** ({len(sub)} events) — "
                             f"Win rate {wr:.1f}% | Avg PnL {sub['trail_pnl_pct'].mean():.2f}% | "
                             f"Avg hold {sub['trail_holding_bars'].mean():.1f} bars")

            st.divider()
            st.markdown("#### Fixed-Horizon Forward Returns (for comparison)")

            summary_rows = []
            for h in horizons:
                col = f'fwd_ret_{h}d_pct'
                if col in events_df.columns:
                    vals = events_df[col].dropna()
                    win_rate = (vals > 0).mean() * 100 if len(vals) else np.nan
                    summary_rows.append({
                        'Horizon (bars)': h,
                        'N': len(vals),
                        'Avg Return %': round(vals.mean(), 3) if len(vals) else np.nan,
                        'Median Return %': round(vals.median(), 3) if len(vals) else np.nan,
                        'Win Rate %': round(win_rate, 1) if len(vals) else np.nan,
                        'Std Dev %': round(vals.std(), 3) if len(vals) else np.nan,
                    })
            if summary_rows:
                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            st.caption(
                f"Avg bar-gap between earliest and latest component signal: "
                f"{events_df['max_gap_bars'].mean():.1f} bars (window setting: {window_bars})"
            )

            with st.expander("Breakdown by direction"):
                for direction in ['bullish', 'bearish']:
                    sub = events_df[events_df['direction'] == direction]
                    if sub.empty:
                        continue
                    st.markdown(f"**{direction.capitalize()}** ({len(sub)} events)")
                    rows = []
                    for h in horizons:
                        col = f'fwd_ret_{h}d_pct'
                        if col in sub.columns:
                            vals = sub[col].dropna()
                            rows.append({
                                'Horizon (bars)': h,
                                'N': len(vals),
                                'Avg Return %': round(vals.mean(), 3) if len(vals) else np.nan,
                                'Win Rate %': round((vals > 0).mean() * 100, 1) if len(vals) else np.nan,
                            })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            display_cols = ['trail_status', 'ticker', 'confirm_date', 'direction', 'close_at_confirm',
                             'rsi_cross_date', 'divergence_date', 'bb_signal_date', 'max_gap_bars',
                             'trail_exit_date', 'trail_exit_price', 'trail_pnl_pct', 'trail_holding_bars']
            display_cols += [f'fwd_ret_{h}d_pct' for h in horizons if f'fwd_ret_{h}d_pct' in events_df.columns]

            def _build_draft(rows_df):
                draft = []
                for _, r in rows_df.iterrows():
                    draft.append({
                        "ticker": r['ticker'],
                        "signal": f"Confluence-{page_label}-{r['direction']}",
                        "timeframe": page_label,
                        "last_close": r['close_at_confirm'],
                        "direction": "LONG" if r['direction'] == 'bullish' else "SHORT",
                    })
                return draft

            # --------------------------
            # Recent Events (Last 7 Days) - quick-select, kept separate from
            # the full history table so picking events to track is fast.
            # --------------------------
            tz = events_df['confirm_date'].dt.tz
            now_ts = pd.Timestamp.now(tz=tz) if tz is not None else pd.Timestamp.now()
            cutoff = now_ts - pd.Timedelta(days=7)
            recent_df = events_df[events_df['confirm_date'] >= cutoff].sort_values('confirm_date', ascending=False)

            st.subheader(f"🕐 Recent Events (Last 7 Days) — {len(recent_df)} event(s), quick-select for tracking")
            if recent_df.empty:
                st.caption("No confluence events in the last 7 days with current settings.")
            else:
                recent_select_df = to_ist_display(recent_df)[display_cols].copy()
                recent_select_df.insert(0, 'Select', False)

                edited_recent = st.data_editor(
                    recent_select_df,
                    column_config={"Select": st.column_config.CheckboxColumn("Select", default=False)},
                    disabled=[c for c in recent_select_df.columns if c != "Select"],
                    hide_index=True,
                    use_container_width=True,
                    key=f"{page_key}_recent_events_editor"
                )
                selected_recent = recent_df.loc[edited_recent[edited_recent["Select"]].index]

                rcol_a, rcol_b = st.columns([1, 3])
                with rcol_a:
                    proceed_recent = st.button("➡️ Setup Portfolio for Selected (Recent)",
                                                disabled=len(selected_recent) == 0, key=f"{page_key}_proceed_recent")
                with rcol_b:
                    if len(selected_recent):
                        st.caption(f"{len(selected_recent)} recent event(s) selected.")
                    else:
                        st.caption("Tick Select above to send just these recent events to portfolio setup.")

                if proceed_recent:
                    st.session_state['portfolio_draft'] = _build_draft(selected_recent)
                    st.session_state['confluence_default_trail_pct'] = st.session_state.get(trail_key, trail_pct)
                    st.session_state['app_page'] = "Portfolio Setup"
                    st.rerun()

            st.divider()
            st.subheader("📋 All Confluence Events (Full History) — select to track as a portfolio")

            select_df = to_ist_display(events_df)[display_cols].copy()
            select_df.insert(0, 'Select', False)

            edited_events = st.data_editor(
                select_df,
                column_config={"Select": st.column_config.CheckboxColumn("Select", default=False)},
                disabled=[c for c in select_df.columns if c != "Select"],
                hide_index=True,
                use_container_width=True,
                key=f"{page_key}_events_editor"
            )

            selected_rows = events_df.loc[edited_events[edited_events["Select"]].index]

            col_a, col_b = st.columns([1, 3])
            with col_a:
                proceed = st.button("➡️ Setup Portfolio for Selected", disabled=len(selected_rows) == 0,
                                     key=f"{page_key}_proceed")
            with col_b:
                if len(selected_rows):
                    st.caption(f"{len(selected_rows)} event(s) selected.")
                else:
                    st.caption("Tick Select on one or more events to proceed to portfolio setup.")

            if proceed:
                st.session_state['portfolio_draft'] = _build_draft(selected_rows)
                st.session_state['confluence_default_trail_pct'] = st.session_state.get(trail_key, trail_pct)
                st.session_state['app_page'] = "Portfolio Setup"
                st.rerun()

            csv_bytes = to_ist_display(events_df)[display_cols].to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download events CSV", csv_bytes, f"confluence_events_{page_key}.csv", "text/csv",
                                key=f"{page_key}_download")

            st.divider()
            st.subheader("📈 Inspect an Event")
            events_df_sorted_ist = to_ist_display(events_df.sort_values('confirm_date', ascending=False))
            events_df_sorted = events_df.sort_values('confirm_date', ascending=False)
            event_labels = [
                f"{row['ticker']} | {row['confirm_date'].date()} {row['confirm_date'].strftime('%H:%M')} IST | {row['direction']}"
                for _, row in events_df_sorted_ist.iterrows()
            ]

            select_key = f"{page_key}_event_select"
            # Guard against a stale selection: if the event list changed since
            # the last run (new scan, different settings, etc.) and the
            # previously-picked label no longer exists, some Streamlit
            # versions raise instead of silently resetting - clear it first.
            if select_key in st.session_state and st.session_state[select_key] not in event_labels:
                del st.session_state[select_key]

            sel_label = st.selectbox("Select event", event_labels, key=select_key)
            if sel_label:
                sel_idx = event_labels.index(sel_label)
                sel_row = events_df_sorted.iloc[sel_idx]
                ticker_data = st.session_state[data_key].get(sel_row['ticker'])
                if ticker_data is not None:
                    try:
                        render_event_chart(ticker_data, sel_row['ticker'], sel_row,
                                            st.session_state.get(window_key, window_bars))
                    except Exception as e:
                        st.error(f"Couldn't render this event's chart: {type(e).__name__}: {e}")
                        st.caption("The rest of the app is unaffected - try a different event, or report this exact message.")
                else:
                    st.warning(f"No cached chart data for {sel_row['ticker']} - try re-running the scan.")
    else:
        st.info("Set your parameters in the sidebar and click **Run Confluence Scan** to begin.")


# --------------------------
# ROUTE TO THE RIGHT PAGE
# --------------------------
if st.session_state["app_page"] == "15 Min Scanner":
    st.header("⏱️ 15 Minute Confluence Scanner")
    render_scanner_page("15min", "15m", "15 Min")

elif st.session_state["app_page"] == "1 Hour Scanner":
    st.header("🕐 1 Hour Confluence Scanner")
    render_scanner_page("1hour", "1h", "1 Hour")

elif st.session_state["app_page"] == "Daily Scanner":
    st.header("📅 Daily Confluence Scanner")
    render_scanner_page("daily", "1d", "Daily")

elif st.session_state["app_page"] == "Daily Scanner":
    st.header("📅 Daily Confluence Scanner")
    render_scanner_page("daily", "1d", "Daily")
# --------------------------
# PORTFOLIO SETUP PAGE
# --------------------------
elif st.session_state["app_page"] == "Portfolio Setup":

    st.header("🛠️ Portfolio Setup — define rules before freezing")

    draft = st.session_state.get('portfolio_draft', [])

    if not draft:
        st.warning("No events selected yet. Go to a Scanner page, run a scan, select events, then come back here.")
        if st.button("⬅️ Back to Scanner"):
            st.session_state["app_page"] = st.session_state.get("last_scanner_page_label", "Daily Scanner")
            st.rerun()
    else:
        st.caption(f"{len(draft)} event(s) staged for portfolio tracking. Edit rules below, then freeze to start tracking.")

        default_trail = st.session_state.get('confluence_default_trail_pct', 1.0)

        st.subheader("Global defaults")
        gcol1, gcol2, gcol3, gcol4 = st.columns(4)
        with gcol1:
            default_sl_pct = st.number_input("Default SL %", min_value=0.1, max_value=50.0, value=float(default_trail), step=0.1,
                                              help="Pre-filled with the trailing stop %% used in the scan.")
        with gcol2:
            default_target_pct = st.number_input("Default Target %", min_value=0.1, max_value=100.0, value=float(default_trail) * 3, step=0.1)
        with gcol3:
            default_qty = st.number_input("Default Qty", min_value=1, value=1, step=1)
        with gcol4:
            apply_defaults = st.button("↻ Apply defaults to all rows")

        setup_rows = []
        for d in draft:
            entry_price = d['last_close']
            direction = d['direction']
            if direction == "LONG":
                sl_price = round(entry_price * (1 - default_sl_pct / 100), 2)
                target_price = round(entry_price * (1 + default_target_pct / 100), 2)
            else:
                sl_price = round(entry_price * (1 + default_sl_pct / 100), 2)
                target_price = round(entry_price * (1 - default_target_pct / 100), 2)

            setup_rows.append({
                "Ticker": d['ticker'],
                "Signal": d['signal'],
                "Timeframe": d.get('timeframe', ''),
                "Direction": direction,
                "Entry Price": round(entry_price, 2),
                "SL Price": sl_price,
                "Target Price": target_price,
                "Qty": int(default_qty),
                "Notes": ""
            })

        setup_key = "confluence_portfolio_setup_editor"
        if apply_defaults or setup_key not in st.session_state:
            st.session_state[setup_key] = pd.DataFrame(setup_rows)

        edited_setup = st.data_editor(
            st.session_state[setup_key],
            column_config={
                "Direction": st.column_config.SelectboxColumn("Direction", options=["LONG", "SHORT"]),
                "Entry Price": st.column_config.NumberColumn("Entry Price", format="%.2f"),
                "SL Price": st.column_config.NumberColumn("SL Price", format="%.2f"),
                "Target Price": st.column_config.NumberColumn("Target Price", format="%.2f"),
                "Qty": st.column_config.NumberColumn("Qty", min_value=1, step=1),
            },
            disabled=["Ticker", "Signal", "Timeframe"],
            hide_index=True,
            use_container_width=True,
            key=setup_key + "_widget"
        )

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅️ Back to Scanner"):
                st.session_state["app_page"] = st.session_state.get("last_scanner_page_label", "Daily Scanner")
                st.rerun()
        with col2:
            freeze = st.button("🔒 Freeze Portfolio & Start Tracking", type="primary")

        if freeze:
            errors = []
            for _, row in edited_setup.iterrows():
                if row["Direction"] == "LONG" and row["SL Price"] >= row["Entry Price"]:
                    errors.append(f"{row['Ticker']}: SL must be below Entry for LONG")
                if row["Direction"] == "LONG" and row["Target Price"] <= row["Entry Price"]:
                    errors.append(f"{row['Ticker']}: Target must be above Entry for LONG")
                if row["Direction"] == "SHORT" and row["SL Price"] <= row["Entry Price"]:
                    errors.append(f"{row['Ticker']}: SL must be above Entry for SHORT")
                if row["Direction"] == "SHORT" and row["Target Price"] >= row["Entry Price"]:
                    errors.append(f"{row['Ticker']}: Target must be below Entry for SHORT")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                portfolio_df = load_portfolio()
                today_str = date.today().strftime("%Y-%m-%d")
                new_rows = []
                for _, row in edited_setup.iterrows():
                    new_rows.append({
                        "id": str(uuid.uuid4())[:8],
                        "ticker": row["Ticker"],
                        "signal": row["Signal"],
                        "direction": row["Direction"],
                        "timeframe": row["Timeframe"],
                        "entry_date": today_str,
                        "entry_price": row["Entry Price"],
                        "sl_price": row["SL Price"],
                        "target_price": row["Target Price"],
                        "qty": row["Qty"],
                        "status": "OPEN",
                        "exit_date": "",
                        "exit_price": "",
                        "exit_reason": "",
                        "pnl": "",
                        "pnl_pct": "",
                        "notes": row["Notes"],
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                portfolio_df = pd.concat([portfolio_df, pd.DataFrame(new_rows)], ignore_index=True)
                save_portfolio(portfolio_df)

                st.session_state['portfolio_draft'] = []
                if setup_key in st.session_state:
                    del st.session_state[setup_key]
                st.session_state["app_page"] = "Portfolio Tracker"
                st.success(f"🔒 {len(new_rows)} position(s) frozen and now being tracked.")
                st.rerun()

# --------------------------
# PORTFOLIO TRACKER PAGE
# --------------------------
elif st.session_state["app_page"] == "Portfolio Tracker":

    st.header("📒 Portfolio Tracker")

    portfolio_df = load_portfolio()

    if portfolio_df.empty:
        st.info("No positions tracked yet. Scan → select events → Portfolio Setup → Freeze to create your first positions.")
        if st.button("⬅️ Back to Scanner"):
            st.session_state["app_page"] = st.session_state.get("last_scanner_page_label", "Daily Scanner")
            st.rerun()
    else:
        top1, top2 = st.columns([1, 1])
        with top1:
            refresh = st.button("🔄 Refresh & Check SL/Target", type="primary")
        with top2:
            if st.button("⬅️ Back to Scanner"):
                st.session_state["app_page"] = st.session_state.get("last_scanner_page_label", "Daily Scanner")
                st.rerun()

        if refresh:
            with st.spinner("Checking daily bars for SL/Target hits..."):
                portfolio_df, close_events = check_and_update_positions(portfolio_df)
            save_portfolio(portfolio_df)
            if close_events:
                for ev in close_events:
                    tag = "🟢 TARGET" if ev["status"] == "CLOSED_TARGET" else "🔴 SL"
                    st.write(f"{tag} — **{ev['ticker']}** closed at {ev['exit_price']:.2f} | PnL: {ev['pnl']:.2f}")
            else:
                st.info("No SL/Target hits since last check.")

        open_df = portfolio_df[portfolio_df["status"] == "OPEN"].copy()
        closed_df = portfolio_df[portfolio_df["status"] != "OPEN"].copy()

        st.subheader("Summary")
        total = len(portfolio_df)
        n_open = len(open_df)
        n_closed = len(closed_df)
        closed_pnls = pd.to_numeric(closed_df["pnl"], errors="coerce").dropna()
        wins = closed_pnls[closed_pnls > 0]
        losses = closed_pnls[closed_pnls < 0]
        win_rate = (len(wins) / len(closed_pnls) * 100) if len(closed_pnls) > 0 else 0.0
        total_pnl = closed_pnls.sum()
        gross_profit = wins.sum()
        gross_loss = abs(losses.sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.nan

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Positions", total)
        m2.metric("Open", n_open)
        m3.metric("Closed", n_closed)
        m4.metric("Win Rate", f"{win_rate:.1f}%" if n_closed else "—")
        m5.metric("Realized PnL", f"{total_pnl:.2f}" if n_closed else "—")
        if not np.isnan(profit_factor):
            st.caption(f"Profit Factor: {profit_factor:.2f}")

        # --------------------------
        # OPEN TRADES - split into separate tables per timeframe, shown
        # ABOVE the history, so each basket (15 Min / 1 Hour / Daily) is
        # easy to scan independently.
        # --------------------------
        st.divider()
        st.subheader("🟡 Open Trades")

        TIMEFRAME_GROUPS = ["15 Min", "1 Hour", "Daily"]

        if open_df.empty:
            st.caption("No open positions.")
        else:
            with st.spinner("Fetching live prices..."):
                open_df["current_price"] = open_df["ticker"].apply(fetch_last_price)
            open_df["unrealized_pnl"] = open_df.apply(
                lambda r: compute_pnl(r["direction"], float(r["entry_price"]),
                                       float(r["current_price"]) if r["current_price"] else float(r["entry_price"]),
                                       float(r["qty"]))[0],
                axis=1
            )

            known_tf_open = open_df[open_df["timeframe"].isin(TIMEFRAME_GROUPS)]
            legacy_open = open_df[~open_df["timeframe"].isin(TIMEFRAME_GROUPS)]

            for tf in TIMEFRAME_GROUPS:
                tf_df = known_tf_open[known_tf_open["timeframe"] == tf]
                st.markdown(f"**{tf}**")
                if tf_df.empty:
                    st.caption(f"No open {tf} positions.")
                    continue
                display_open = tf_df[[
                    "id", "ticker", "direction", "entry_date", "entry_price",
                    "sl_price", "target_price", "qty", "current_price", "unrealized_pnl"
                ]].round(2)
                st.dataframe(display_open, use_container_width=True, hide_index=True)

            if not legacy_open.empty:
                st.markdown("**Unspecified / Legacy (frozen before timeframe tracking was added)**")
                display_legacy = legacy_open[[
                    "id", "ticker", "direction", "entry_date", "entry_price",
                    "sl_price", "target_price", "qty", "current_price", "unrealized_pnl"
                ]].round(2)
                st.dataframe(display_legacy, use_container_width=True, hide_index=True)

            with st.expander("Manually close a position at current market price"):
                close_id = st.selectbox("Position ID", open_df["id"].tolist())
                if st.button("Close this position now"):
                    row = open_df[open_df["id"] == close_id].iloc[0]
                    exit_price = row["current_price"] if row["current_price"] else float(row["entry_price"])
                    portfolio_df = close_position_manual(portfolio_df, close_id, exit_price)
                    save_portfolio(portfolio_df)
                    st.success(f"Closed {row['ticker']} at {exit_price:.2f}")
                    st.rerun()

        # --------------------------
        # TRADE HISTORY - same per-timeframe split, below the open trades
        # --------------------------
        st.divider()
        st.subheader("📜 Trade History (Closed Positions)")
        if closed_df.empty:
            st.caption("No closed positions yet.")
        else:
            known_tf_closed = closed_df[closed_df["timeframe"].isin(TIMEFRAME_GROUPS)]
            legacy_closed = closed_df[~closed_df["timeframe"].isin(TIMEFRAME_GROUPS)]

            def _style_closed(df):
                return df.style.map(
                    lambda x: 'background-color: #ccffcc' if isinstance(x, (int, float)) and x > 0 else
                              'background-color: #ffcccc' if isinstance(x, (int, float)) and x < 0 else '',
                    subset=['pnl']
                )

            cols = ["id", "ticker", "direction", "entry_date", "entry_price",
                    "exit_date", "exit_price", "status", "exit_reason", "pnl", "pnl_pct"]

            for tf in TIMEFRAME_GROUPS:
                tf_df = known_tf_closed[known_tf_closed["timeframe"] == tf]
                st.markdown(f"**{tf}**")
                if tf_df.empty:
                    st.caption(f"No closed {tf} positions yet.")
                    continue
                st.dataframe(_style_closed(tf_df[cols]), use_container_width=True, hide_index=True)

            if not legacy_closed.empty:
                st.markdown("**Unspecified / Legacy (frozen before timeframe tracking was added)**")
                st.dataframe(_style_closed(legacy_closed[cols]), use_container_width=True, hide_index=True)

            csv_bytes = closed_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download closed trades CSV", csv_bytes, "confluence_closed_trades.csv", "text/csv")