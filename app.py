import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re

st.set_page_config(layout="centered")

st.markdown("## 📱 Trading Copilot")

# SESSION
if "entry" not in st.session_state:
    st.session_state.entry = 0.0

if "sim_mode" not in st.session_state:
    st.session_state.sim_mode = True

# MODE
mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

# QUICK INPUT
quick_input = st.text_input("🎤 Quick Input", placeholder="Buy 210 SL 205 TGT 220")

entry = st.session_state.entry
sl_price = 0.0
tgt_price = 0.0

if quick_input:
    nums = list(map(float, re.findall(r'\d+\.?\d*', quick_input)))
    if len(nums) > 0:
        entry = nums[0]
        st.session_state.entry = entry
    if len(nums) > 1:
        sl_price = nums[1]
    if len(nums) > 2:
        tgt_price = nums[2]

# PLAN
plan = st.text_area("🧠 Plan", height=60)

#━━━━━━━━━━━━━━━━━━━
# TSL BUY / SELL
#━━━━━━━━━━━━━━━━━━━
tsl_buy = False
tsl_sell = False
brk078 = False
trade_type = None

if mode == "Range":
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        tsl_buy = st.toggle("TSL Buy")

    with col_t2:
        tsl_sell = st.toggle("TSL Sell")

    if tsl_buy and tsl_sell:
        trade_type = None
    elif tsl_buy:
        trade_type = "BUY"
    elif tsl_sell:
        trade_type = "SELL"
    else:
        trade_type = None

    if trade_type is None:
        st.warning("Select only one: TSL Buy or TSL Sell")
        st.stop()

elif mode == "Breakout":
    # ✅ UPDATED LOGIC
    brk_buy = st.toggle("0.78 BUY")
    brk_sell = st.toggle("0.78 SELL")

    if brk_buy and not brk_sell:
        trade_type = "BUY"
        brk078 = True
    elif brk_sell and not brk_buy:
        trade_type = "SELL"
        brk078 = True
    else:
        trade_type = None
        brk078 = False

else:
    trade_type = "BUY" if st.toggle("BUY", True) else "SELL"

# INPUTS
if mode == "Range":
    cons = st.selectbox("Cons", ["No","2T","3T"])
    bb = st.selectbox("BB", ["No","Yes"])
    retr = st.selectbox("Ret", ["No","0.6","0.78"])

elif mode == "Breakout":
    tl = st.selectbox("Trendline", ["No","Yes"])
    sq = st.selectbox("Squeeze", ["No","Yes"])
    htf = st.selectbox("HTF", ["Neutral","Above 0.786","Below 0.214"])

else:
    prev = st.selectbox("Prev", ["Buy","Sell"])
    gap = st.selectbox("Gap", ["Up","Down","None"])

# ENTRY + SL + TARGET
entry = st.number_input("Entry", value=entry)

# ✅ CONDITIONAL DISPLAY
show_sl = False
show_tgt = False

if mode == "Range":
    show_sl = True
    show_tgt = True
elif mode == "Breakout":
    if brk078:
        show_sl = True
        show_tgt = True
else:
    show_sl = True
    show_tgt = True

c1, c2 = st.columns(2)

with c1:
    if show_sl:
        sl_manual = st.number_input("SL Price", value=sl_price)
    else:
        sl_manual = 0.0

with c2:
    if show_tgt:
        tgt_manual = st.number_input("Target Price", value=tgt_price)
    else:
        tgt_manual = 0.0

#━━━━━━━━━━━━━━━━━━━
# SL / TARGET CONTEXT (MATCHES EXISTING INPUTS)
#━━━━━━━━━━━━━━━━━━━

if show_sl:

    # RANGE MODE (aligned with Cons / BB / Ret)
    if mode == "Range":
        st.info(
            f"Range Context → Cons: {cons} | BB: {bb} | Ret: {retr}\n\n"
            "SL: Structure / Pivot based\n"
            "Target: Zone or RR based"
        )

    # BREAKOUT MODE (aligned with TL / SQ / HTF)
    elif mode == "Breakout" and brk078:
        st.info(
            f"Breakout Context → TL: {tl} | SQ: {sq} | HTF: {htf}\n\n"
            "SL: Break candle / Structure\n"
            "Target: Expansion / Trail"
        )

    # OPENING MODE (aligned with Prev / Gap)
    elif mode == "Opening":
        st.info(
            f"Opening Context → Prev: {prev} | Gap: {gap}\n\n"
            "SL: Previous level / Tight\n"
            "Target: Quick move / RR"
        )
# RR FIX
planned_rr = 0
if entry != 0 and sl_manual != 0 and tgt_manual != 0 and sl_manual != entry:
    planned_rr = abs(tgt_manual - entry) / abs(entry - sl_manual)

# EXIT
st.markdown("### 🚪 Exit")
exit_price = st.number_input("Exit Price", value=0.0)

# BUTTONS
col1, col2 = st.columns(2)

# TRADE EVALUATION
with col1:
    if st.button("🚀 Evaluate Trade"):

        if trade_type is None:
            st.error("Select trade direction")
            st.stop()

        if mode == "Breakout":
            if not brk078:
                st.warning("0.78 break required")
                st.stop()

        min_rr = 0.7 if mode == "Range" else 1
        if planned_rr < min_rr:
            st.error("RR too low → NO TRADE")
            st.stop()

        if mode == "Range":
            score = (
                {"No":0,"2T":2,"3T":3}[cons] +
                {"No":0,"Yes":1}[bb] +
                {"No":0,"0.6":1,"0.78":2}[retr]
            )
        elif mode == "Breakout":
            score = (
                {"No":0,"Yes":2}[tl] +
                {"No":0,"Yes":2}[sq] +
                {"Neutral":0,"Above 0.786":1,"Below 0.214":1}[htf]
            )
        else:
            score = 2

        max_score = 6 if mode == "Range" else 5 if mode == "Breakout" else 2
        ratio = score / max_score if max_score != 0 else 0

        if ratio >= 0.8:
            strength = "🔥 STRONG"
        elif ratio >= 0.5:
            strength = "⚡ MODERATE"
        else:
            strength = "❌ WEAK"

        st.success("VALID TRADE")
        st.write(f"Strength: {strength}")
        st.write(f"Score: {score}")

# RESULT EVALUATION
with col2:
    if st.button("📊 Evaluate Result"):

        if exit_price == 0:
            st.warning("Enter exit price")
            st.stop()

        if trade_type is None:
            st.warning("Select trade direction")
            st.stop()

        if trade_type == "BUY" and sl_manual >= entry:
            st.error("BUY: SL must be below Entry")
            st.stop()

        if trade_type == "SELL" and sl_manual <= entry:
            st.error("SELL: SL must be above Entry")
            st.stop()

        risk = abs(entry - sl_manual)

        if risk == 0:
            st.error("Invalid SL (same as entry)")
            st.stop()

        pnl = (exit_price - entry) if trade_type == "BUY" else (entry - exit_price)
        rr = pnl / risk if risk != 0 else 0

        outcome = "Win" if pnl > 0 else "Loss" if pnl < 0 else "BE"

        st.success(f"Outcome: {outcome}")
        st.write(f"PnL: {round(pnl,2)}")
        st.write(f"RR: {round(rr,2)}")

        file_name = "simulation_trades.csv" if st.session_state.get("sim_mode", True) else "live_trades.csv"

        log = {
            "Time": datetime.now(),
            "Mode": mode,
            "Type": trade_type,
            "Entry": entry,
            "SL": sl_manual,
            "Target": tgt_manual,
            "Exit": exit_price,
            "PnL": round(pnl, 2),
            "RR": round(rr, 2),
            "Outcome": outcome,
            "Plan": plan
        }

        df = pd.DataFrame([log])

        if os.path.exists(file_name) and os.path.getsize(file_name) > 0:
            old = pd.read_csv(file_name)
            df = pd.concat([old, df], ignore_index=True)

        df.to_csv(file_name, index=False)
        st.success("Saved ✅")

# SIMULATION CONTROLS
st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    sim_mode_input = st.toggle("Simulation Mode", st.session_state.sim_mode)
    st.session_state.sim_mode = sim_mode_input

with c2:
    if st.button("🗑 Clear Simulation Data"):
        if os.path.exists("simulation_trades.csv"):
            os.remove("simulation_trades.csv")
            st.success("Simulation data cleared")
        else:
            st.info("No simulation data found")

# ANALYTICS
st.markdown("### 📊 Analytics")

file_name = "simulation_trades.csv" if st.session_state.get("sim_mode", True) else "live_trades.csv"

if os.path.exists(file_name) and os.path.getsize(file_name) > 0:
    df = pd.read_csv(file_name)

    total = len(df)
    wins = len(df[df["Outcome"] == "Win"])

    win_rate = round((wins / total)*100, 2) if total > 0 else 0
    avg_rr = round(df["RR"].mean(), 2)
    total_pnl = round(df["PnL"].sum(), 2)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades", total)
    c2.metric("Win %", win_rate)
    c3.metric("Avg RR", avg_rr)
    c4.metric("Total PnL", total_pnl)

    st.dataframe(df.tail(10), use_container_width=True)
else:
    st.info("No data yet")