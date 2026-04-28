import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re

st.set_page_config(layout="centered")

#━━━━━━━━━━━━━━━━━━━
# HEADER
#━━━━━━━━━━━━━━━━━━━
st.markdown("## 📱 Trading Copilot")

#━━━━━━━━━━━━━━━━━━━
# SESSION STATE
#━━━━━━━━━━━━━━━━━━━
for key in ["entry"]:
    if key not in st.session_state:
        st.session_state[key] = 0.0

#━━━━━━━━━━━━━━━━━━━
# MODE
#━━━━━━━━━━━━━━━━━━━
mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

#━━━━━━━━━━━━━━━━━━━
# QUICK INPUT
#━━━━━━━━━━━━━━━━━━━
quick_input = st.text_input("🎤 Quick Input", placeholder="Buy 210 SL 205 TGT 220")

entry = st.session_state.get("entry", 0.0)
sl_price = 0.0
tgt_price = 0.0

if quick_input:
    try:
        numbers = list(map(float, re.findall(r'\d+\.?\d*', quick_input)))
        if len(numbers) >= 1:
            entry = numbers[0]
            st.session_state.entry = entry
        if len(numbers) >= 2:
            sl_price = numbers[1]
        if len(numbers) >= 3:
            tgt_price = numbers[2]
    except:
        pass

#━━━━━━━━━━━━━━━━━━━
# PLAN
#━━━━━━━━━━━━━━━━━━━
plan = st.text_area("🧠 Plan", height=60)

#━━━━━━━━━━━━━━━━━━━
# TSL (used for both modes)
#━━━━━━━━━━━━━━━━━━━
tsl = st.toggle("TSL Flip / 0.78 Break")

#━━━━━━━━━━━━━━━━━━━
# MODE INPUTS
#━━━━━━━━━━━━━━━━━━━
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

#━━━━━━━━━━━━━━━━━━━
# ENTRY
#━━━━━━━━━━━━━━━━━━━
entry = st.number_input("Entry", value=entry)

#━━━━━━━━━━━━━━━━━━━
# SL & TARGET
#━━━━━━━━━━━━━━━━━━━
st.markdown("### ⚙️ Manual SL & Target")

col1, col2 = st.columns(2)

with col1:
    sl_manual = st.number_input("SL Price", value=sl_price)

with col2:
    tgt_manual = st.number_input("Target Price", value=tgt_price)

#━━━━━━━━━━━━━━━━━━━
# RR AUTO TARGET
#━━━━━━━━━━━━━━━━━━━
use_rr = st.toggle("Auto Target (RR based)")

if use_rr and entry and sl_manual:
    rr_sel = st.selectbox("RR", [1, 1.5, 2, 3], index=2)

    risk = abs(entry - sl_manual)

    if entry > sl_manual:
        tgt_manual = entry + (risk * rr_sel)
    else:
        tgt_manual = entry - (risk * rr_sel)

    st.success(f"Auto Target: {round(tgt_manual,2)}")

#━━━━━━━━━━━━━━━━━━━
# PLANNED RR (IMPORTANT FIX)
#━━━━━━━━━━━━━━━━━━━
planned_rr = 0

if entry and sl_manual and tgt_manual and sl_manual != entry:
    planned_rr = abs(tgt_manual - entry) / abs(entry - sl_manual)
    st.info(f"📊 Planned RR = {round(planned_rr,2)}")

#━━━━━━━━━━━━━━━━━━━
# EXIT INPUT
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🚪 Exit")
exit_price = st.number_input("Exit Price", value=0.0)

#━━━━━━━━━━━━━━━━━━━
# DISPLAY OPTIONS
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🎯 SL & Target Options")

sl_options = []
target_options = []

if mode == "Range":

    if not tsl:
        st.warning("TSL Flip required → No Trade")
    else:
        sl_options = ["Range Low (TSL flip level)"]

        if retr in ["0.6", "0.78"]:
            target_options = ["0.384 Retracement"]

            if bb == "Yes":
                target_options.append("Range High")
            else:
                target_options.append("Previous High")
        else:
            target_options = ["Range Mean"]

elif mode == "Breakout":

    if not tsl:
        st.warning("0.78 level not broken → No Trade")
    else:
        sl_options = ["Breakout Candle Low/High"]
        target_options = ["1.618 Extension"]

elif mode == "Opening":

    sl_options = ["First 5-min Candle"]

    if (prev == "Buy" and gap == "Up") or (prev == "Sell" and gap == "Down"):
        target_options = ["1.5R","Continuation"]
    else:
        target_options = ["1R"]

if sl_options:
    st.info("**SL Options:**\n" + "\n".join([f"• {x}" for x in sl_options]))

if target_options:
    st.info("**Target Options:**\n" + "\n".join([f"• {x}" for x in target_options]))

#━━━━━━━━━━━━━━━━━━━
# EVALUATE
#━━━━━━━━━━━━━━━━━━━
if st.button("🚀 Evaluate Trade"):

    # MODE VALIDATION
    if mode == "Range" and not tsl:
        st.warning("TSL not satisfied → No Trade")
        st.stop()

    if mode == "Breakout" and not tsl:
        st.warning("0.78 break not satisfied → No Trade")
        st.stop()

    # RR FILTER (FIXED)
    min_rr = 0.7 if mode == "Range" else 1

    if planned_rr < min_rr:
        st.error(f"Planned RR < {min_rr} → NO TRADE")
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
        score = {
            ("Buy","Up"):3,
            ("Buy","Down"):2,
            ("Sell","Down"):3,
            ("Sell","Up"):2
        }.get((prev, gap), 0)

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.markdown(f"### {decision}")
    st.write(f"Score: {score}")

    # REALIZED RESULT
    trade_type = "BUY" if entry > sl_manual else "SELL"

    pnl = 0
    rr = 0
    outcome = "NA"

    if entry and sl_manual and exit_price:

        risk = abs(entry - sl_manual)

        pnl = (exit_price - entry) if trade_type == "BUY" else (entry - exit_price)
        rr = pnl / risk if risk != 0 else 0

        outcome = "Win" if pnl > 0 else "Loss" if pnl < 0 else "BE"

        st.success(f"Outcome: {outcome}")
        st.write(f"PnL: {round(pnl,2)}")
        st.write(f"RR: {round(rr,2)}")

    review = st.text_area("🔍 Review", height=60)

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
        "Score": score,
        "Decision": decision,
        "Plan": plan,
        "Review": review
    }

    df = pd.DataFrame([log])

    try:
        old = pd.read_csv(file_name)
        df = pd.concat([old, df], ignore_index=True)
    except:
        pass

    df.to_csv(file_name, index=False)
    st.success("Saved ✅")

#━━━━━━━━━━━━━━━━━━━
# ANALYTICS
#━━━━━━━━━━━━━━━━━━━
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