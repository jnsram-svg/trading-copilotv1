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
# TSL BUY / SELL (FIXED COLUMN NAMES)
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
        st.warning("Select only one: TSL Buy or TSL Sell")
        st.stop()

    if tsl_buy:
        trade_type = "BUY"
    elif tsl_sell:
        trade_type = "SELL"
    else:
        trade_type = None

elif mode == "Breakout":
    brk078 = st.toggle("0.78 Break")
    trade_type = "BUY" if st.toggle("BUY", True) else "SELL"

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

c1, c2 = st.columns(2)
with c1:
    sl_manual = st.number_input("SL Price", value=sl_price)
with c2:
    tgt_manual = st.number_input("Target Price", value=tgt_price)

# PLANNED RR (internal)
planned_rr = 0
if entry and sl_manual and tgt_manual and sl_manual != entry:
    planned_rr = abs(tgt_manual - entry) / abs(entry - sl_manual)

# EXIT
st.markdown("### 🚪 Exit")
exit_price = st.number_input("Exit Price", value=0.0)

# BUTTONS
col1, col2 = st.columns(2)

# TRADE EVALUATION
with col1:
    if st.button("🚀 Evaluate Trade"):

        if mode == "Range" and trade_type is None:
            st.warning("Select TSL Buy or TSL Sell")
            st.stop()

        if mode == "Breakout" and not brk078:
            st.warning("0.78 break required")
            st.stop()

        min_rr = 0.7 if mode == "Range" else 1
        if planned_rr < min_rr:
            st.error("RR too low → NO TRADE")
            st.stop()

        # SCORE
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

        if score >= 6:
            strength = "🔥 STRONG"
        elif score >= 3:
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

        # SAFETY CHECK
        if trade_type == "BUY" and sl_manual >= entry:
            st.error("BUY: SL must be below Entry")
            st.stop()

        if trade_type == "SELL" and sl_manual <= entry:
            st.error("SELL: SL must be above Entry")
            st.stop()

        risk = abs(entry - sl_manual)

        pnl = (exit_price - entry) if trade_type == "BUY" else (entry - exit_price)
        rr = pnl / risk if risk != 0 else 0

        outcome = "Win" if pnl > 0 else "Loss" if pnl < 0 else "BE"

        st.success(f"Outcome: {outcome}")
        st.write(f"PnL: {round(pnl,2)}")
        st.write(f"RR: {round(rr,2)}")

        # SAVE TRADE
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

        try:
            old = pd.read_csv(file_name)
            df = pd.concat([old, df], ignore_index=True)
        except:
            pass

        df.to_csv(file_name, index=False)
        st.success("Saved ✅")

# SIMULATION CONTROLS
st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.session_state.sim_mode = st.toggle("Simulation Mode", True)

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

try:
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

except:
    st.info("No data yet")