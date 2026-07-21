import time

import pandas as pd
import streamlit as st

import engine

st.set_page_config(page_title="Scanner", page_icon="📡", layout="wide")

st.title("📡 Pivot Confluence Scanner")

# ============================================================
# SIDEBAR SETTINGS
# ============================================================

st.sidebar.header("Scan Settings")

tolerance_pct = st.sidebar.number_input(
    "Proximity tolerance (± %)",
    min_value=0.01, max_value=5.0, value=0.20, step=0.05, format="%.2f",
    help="Flag a stock as 'near pivot' when current price is within this % of a "
         "confirmed Pivot High / Pivot Low.",
)

st.sidebar.subheader("Timeframes to scan")
tf_selected = []
for tf_label in engine.TIMEFRAMES.keys():
    if st.sidebar.checkbox(tf_label, value=True, key=f"tf_{tf_label}"):
        tf_selected.append(tf_label)

with st.sidebar.expander("Timeframe data windows (advanced)"):
    for tf_label in tf_selected:
        cfg = engine.TIMEFRAMES[tf_label]
        col1, col2 = st.columns(2)
        new_period = col1.text_input(
            f"{tf_label} period", value=cfg["period"], key=f"period_{tf_label}"
        )
        col2.text_input(
            f"{tf_label} interval", value=cfg["interval"], key=f"interval_{tf_label}",
            disabled=True,
        )
        engine.TIMEFRAMES[tf_label]["period"] = new_period

st.sidebar.subheader("Supertrend params")
st_len = st.sidebar.number_input("ATR length", min_value=2, max_value=50, value=10)
st_factor = st.sidebar.number_input("Factor", min_value=0.5, max_value=10.0, value=3.0, step=0.1)

st.sidebar.subheader("Stock universe")
default_universe_text = ", ".join(engine.DEFAULT_FNO_STOCKS)
universe_text = st.sidebar.text_area(
    "F&O symbols (comma separated, no .NS suffix)",
    value=default_universe_text,
    height=150,
)
universe = sorted(set(
    s.strip().upper() for s in universe_text.split(",") if s.strip()
))
st.sidebar.caption(f"{len(universe)} symbols in universe")

run_scan = st.sidebar.button("🔍 Run Scan", type="primary", use_container_width=True)

# ============================================================
# RUN SCAN
# ============================================================

if run_scan:
    if not tf_selected:
        st.warning("Select at least one timeframe.")
    else:
        results = []
        progress = st.progress(0.0, text="Starting scan...")
        n = len(universe)

        for i, sym in enumerate(universe):
            progress.progress((i + 1) / n, text=f"Scanning {sym} ({i+1}/{n})")
            try:
                res = engine.scan_symbol(
                    sym, tf_selected, tolerance_pct,
                    st_len=st_len, st_factor=st_factor,
                )
            except Exception as e:
                res = None

            if res and res["confluence_count"] > 0:
                results.append(res)

        progress.empty()
        st.session_state["scan_results"] = results
        st.session_state["scan_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# DISPLAY RESULTS
# ============================================================

results = st.session_state.get("scan_results")

if results is None:
    st.info("Set your parameters in the sidebar and click **Run Scan**.")
elif len(results) == 0:
    st.warning("No stocks currently near a pivot within tolerance. Try widening the tolerance.")
else:
    st.caption(f"Last scan: {st.session_state.get('scan_timestamp', '')} · "
               f"{len(results)} symbol(s) with at least one pivot hit")
    st.caption("Regime rule: price breaks below the last two confirmed Pivot Lows → **BEARISH** "
               "(then near-PH = **SELL**) · breaks above the last two confirmed Pivot Highs → "
               "**BULLISH** (then near-PL = **BUY**). Regime persists until the opposite break.")

    only_actionable = st.checkbox("Show only actionable BUY / SELL rows", value=False)

    # Sort: highest confluence first, then tightest (smallest) distance among hits
    def min_abs_dist(r):
        return min(abs(h["distance_pct"]) for h in r["hits"]) if r["hits"] else 999

    results_sorted = sorted(
        results, key=lambda r: (-r["confluence_count"], min_abs_dist(r))
    )

    # Priority for picking the headline Signal shown per symbol:
    # a real BUY/SELL trumps a WATCH note, which trumps "-"
    _SIGNAL_RANK = {"BUY": 0, "SELL": 0, "WATCH (breakdown)": 1, "WATCH (breakout)": 1, "-": 2}

    rows = []
    for r in results_sorted:
        detail_parts = []
        ordered_hits = sorted(
            r["hits"], key=lambda h: list(engine.TIMEFRAMES.keys()).index(h["timeframe"])
        )
        for h in ordered_hits:
            sign = "+" if h["distance_pct"] >= 0 else ""
            detail_parts.append(
                f"{h['timeframe']}:{h['pivot_type']}@{h['pivot_price']} ({sign}{h['distance_pct']}%) "
                f"[{h['regime']}→{h['signal']}]"
            )

        best_hit = min(ordered_hits, key=lambda h: _SIGNAL_RANK.get(h["signal"], 3))
        headline_signal = best_hit["signal"]
        headline_regime = best_hit["regime"]

        rows.append({
            "Track": False,
            "Symbol": r["symbol"],
            "Confluence": r["confluence_count"],
            "Regime": headline_regime,
            "Signal": headline_signal,
            "Current Price": r["current_price"],
            "Pivot Detail": "  |  ".join(detail_parts),
        })

    result_df = pd.DataFrame(rows)
    if only_actionable:
        result_df = result_df[result_df["Signal"].isin(["BUY", "SELL"])].reset_index(drop=True)

    edited_df = st.data_editor(
        result_df,
        column_config={
            "Track": st.column_config.CheckboxColumn("Track", help="Select to add to Tracker"),
            "Confluence": st.column_config.NumberColumn("Confluence", help="# timeframes near a pivot"),
            "Signal": st.column_config.TextColumn("Signal", help="BEARISH regime + near PH = SELL · BULLISH regime + near PL = BUY"),
        },
        disabled=["Symbol", "Confluence", "Regime", "Signal", "Current Price", "Pivot Detail"],
        hide_index=True,
        use_container_width=True,
        key="scan_results_editor",
    )

    if st.button("➕ Add Selected to Tracker", type="primary"):
        selected_symbols = edited_df.loc[edited_df["Track"], "Symbol"].tolist()
        if not selected_symbols:
            st.warning("Tick at least one row's Track box first.")
        else:
            by_symbol = {r["symbol"]: r for r in results_sorted}
            for sym in selected_symbols:
                r = by_symbol[sym]
                engine.add_tracked(sym, r["hits"], r["current_price"])
            st.success(f"Added {len(selected_symbols)} symbol(s) to Tracker. "
                       f"Open the **Tracker** page to view.")
