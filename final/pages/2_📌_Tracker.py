import pandas as pd
import streamlit as st

import engine

st.set_page_config(page_title="Tracker", page_icon="📌", layout="wide")

st.title("📌 Pivot Tracker")

tracked = engine.load_tracked()

if not tracked:
    st.info("Nothing tracked yet. Go to **Scanner**, tick stocks, and click "
             "'Add Selected to Tracker'.")
    st.stop()

col_a, col_b, col_c = st.columns([1, 1, 4])
refresh = col_a.button("🔄 Refresh (live)", type="primary")
if col_b.button("🗑️ Clear All"):
    engine.clear_tracked()
    st.rerun()

st.caption("Refresh re-runs the pivot + regime engine on each tracked stock's original "
           "timeframe(s) to get the live current price, regime, and signal. "
           "Without refreshing, this shows the snapshot captured when you added it.")

st.divider()

rows = []
for entry in tracked:
    symbol = entry["symbol"]
    hits_at_add = entry.get("hits_at_add", [])
    tfs_for_symbol = sorted(set(h["timeframe"] for h in hits_at_add)) or list(engine.TIMEFRAMES.keys())

    current_price = entry.get("added_price")
    live_hits = hits_at_add
    live_note = ""

    if refresh:
        try:
            # tolerance set huge so we always get back the nearest PH/PL levels
            # (not filtered) - we just want the live regime/signal/distance
            res = engine.scan_symbol(symbol, tfs_for_symbol, tolerance_pct=1e9)
            if res:
                current_price = res["current_price"]
                live_hits = res["hits"]
        except Exception:
            live_note = " (live fetch failed)"

    detail_parts = []
    for h in live_hits:
        sign = "+" if h["distance_pct"] >= 0 else ""
        regime = h.get("regime", "-")
        signal = h.get("signal", "-")
        detail_parts.append(
            f"{h['timeframe']}:{h['pivot_type']}@{h['pivot_price']} ({sign}{h['distance_pct']}%) "
            f"[{regime}→{signal}]"
        )

    # headline signal = best across timeframes (BUY/SELL beats WATCH beats -)
    _SIGNAL_RANK = {"BUY": 0, "SELL": 0, "WATCH (breakdown)": 1, "WATCH (breakout)": 1, "-": 2}
    if live_hits:
        best_hit = min(live_hits, key=lambda h: _SIGNAL_RANK.get(h.get("signal", "-"), 3))
        headline_signal = best_hit.get("signal", "-")
        headline_regime = best_hit.get("regime", "-")
    else:
        headline_signal, headline_regime = "-", "-"

    rows.append({
        "Remove": False,
        "Symbol": symbol,
        "Added At": entry.get("added_at", ""),
        "Price @ Add": entry.get("added_price"),
        "Current Price": current_price,
        "Regime": headline_regime,
        "Signal": headline_signal,
        "Pivot Detail": "  |  ".join(detail_parts) + live_note,
    })

tracked_df = pd.DataFrame(rows)

edited_df = st.data_editor(
    tracked_df,
    column_config={
        "Remove": st.column_config.CheckboxColumn("Remove"),
    },
    disabled=["Symbol", "Added At", "Price @ Add", "Current Price",
              "Regime", "Signal", "Pivot Detail"],
    hide_index=True,
    use_container_width=True,
    key="tracker_editor",
)

if st.button("Remove Selected"):
    to_remove = edited_df.loc[edited_df["Remove"], "Symbol"].tolist()
    if not to_remove:
        st.warning("Tick at least one row's Remove box first.")
    else:
        for sym in to_remove:
            engine.remove_tracked(sym)
        st.success(f"Removed {len(to_remove)} symbol(s).")
        st.rerun()
