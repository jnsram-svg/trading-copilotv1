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
quick_input = st.text_input("🎤 Quick Input", placeholder="Buy 210")

#━━━━━━━━━━━━━━━━━━━
# PLAN
#━━━━━━━━━━━━━━━━━━━
plan = st.text_area("🧠 Plan", height=60)

#━━━━━━━━━━━━━━━━━━━
# TSL
#━━━━━━━━━━━━━━━━━━━
tsl = st.toggle("TSL Flip Required")

#━━━━━━━━━━━━━━━━━━━
# MODE INPUTS
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":
    cons = st.selectbox("Cons", ["No","Yes","1T","2T","3T"])
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
# ENTRY (optional)
#━━━━━━━━━━━━━━━━━━━
entry = st.number_input("Entry (optional)", key="entry")

#━━━━━━━━━━━━━━━━━━━
# 🎯 SL & TARGET OPTIONS ENGINE
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🎯 SL & Target Options")

sl_options = []
target_options = []

#━━━━━━━━ RANGE (TSL BASED)
if mode == "Range" and tsl:

    sl_options = [
        "Range Low (broken level during TSL flip)"
    ]

    target_options = [
        "Previous Range Mean"
    ]

    if retr in ["0.6", "0.78"]:
        target_options.append("0.384 Retracement Level")
        target_options.append("Previous Range High")

    if retr in ["0.6", "0.78"] and bb == "Yes":
        target_options.append("Range High (extended move)")

#━━━━━━━━ RANGE (NO TSL)
elif mode == "Range" and not tsl:

    sl_options = [
        "Range Low (Buy) / Range High (Sell)"
    ]

    target_options = [
        "Opposite Range Boundary",
        "Mid Range (optional)"
    ]

#━━━━━━━━ BREAKOUT
elif mode == "Breakout":

    sl_options = [
        "Breakout Candle Low (Buy)",
        "Breakout Candle High (Sell)",
        "Retest Level (advanced)"
    ]

    if sq == "Yes" and tl == "Yes":
        target_options = [
            "3R",
            "Structure High/Low",
            "Measured Move"
        ]
    else:
        target_options = [
            "1R",
            "2R",
            "Structure High/Low"
        ]

#━━━━━━━━ OPENING
elif mode == "Opening":

    sl_options = [
        "First 5-min Candle Low (Buy)",
        "First 5-min Candle High (Sell)"
    ]

    if (prev == "Buy" and gap == "Up") or (prev == "Sell" and gap == "Down"):
        target_options = [
            "1.5R",
            "Structure Continuation"
        ]
    else:
        target_options = [
            "1R",
            "Gap Fill (if applicable)"
        ]

#━━━━━━━━ DISPLAY (BLUE BOX STYLE)
if sl_options:
    sl_text = "\n".join([f"• {opt}" for opt in sl_options])
    st.info(f"**SL Options:**\n{sl_text}")

if target_options:
    tgt_text = "\n".join([f"• {opt}" for opt in target_options])
    st.info(f"**Target Options:**\n{tgt_text}")

#━━━━━━━━━━━━━━━━━━━
# EVALUATE
#━━━━━━━━━━━━━━━━━━━
if st.button("🚀 Evaluate Trade"):

    score = 0

    if tsl:
        if mode == "Range":
            score = (
                {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}[cons] +
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
    else:
        st.warning("TSL not satisfied → No Trade")

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.markdown(f"### {decision}")
    st.write(f"Score: {score}")

    outcome = st.radio("Outcome", ["Win","Loss","BE"], horizontal=True)
    review = st.text_area("🔍 Review", height=60)

    file_name = "simulation_trades.csv" if st.session_state.get("sim_mode", True) else "live_trades.csv"

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Score": score,
        "Decision": decision,
        "Outcome": outcome,
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
# BOTTOM CONTROLS
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.session_state.sim_mode = st.toggle("Simulation Mode", True)

with c2:
    if st.button("🗑 Clear Simulation Data"):
        if os.path.exists("simulation_trades.csv"):
            os.remove("simulation_trades.csv")
            st.success("Simulation data cleared ✅")
        else:
            st.info("No simulation data found")

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

    c1, c2, c3 = st.columns(3)
    c1.metric("Trades", total)
    c2.metric("Wins", wins)
    c3.metric("Win %", win_rate)

    st.dataframe(df.tail(10), use_container_width=True)

except:
    st.info("No data yet")