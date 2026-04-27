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
for key in ["entry","sl","target"]:
    if key not in st.session_state:
        st.session_state[key] = 0.0

#━━━━━━━━━━━━━━━━━━━
# MODE
#━━━━━━━━━━━━━━━━━━━
mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

#━━━━━━━━━━━━━━━━━━━
# QUICK INPUT
#━━━━━━━━━━━━━━━━━━━
quick_input = st.text_input(
    "🎤 Quick Input",
    placeholder="Buy 210 SL 205 Target 230"
)

#━━━━━━━━━━━━━━━━━━━
# PARSER
#━━━━━━━━━━━━━━━━━━━
def extract_trade_levels(text):
    text = text.lower()
    numbers = list(map(float, re.findall(r"\d+\.?\d*", text)))

    entry = sl = target = None

    sl_match = re.search(r"(sl|stop)[^\d]*(\d+\.?\d*)", text)
    if sl_match:
        sl = float(sl_match.group(2))

    tgt_match = re.search(r"(target|tgt|tp)[^\d]*(\d+\.?\d*)", text)
    if tgt_match:
        target = float(tgt_match.group(2))

    used = {sl, target}
    for n in numbers:
        if n not in used:
            entry = n
            break

    return entry, sl, target

if quick_input:
    e, s, t = extract_trade_levels(quick_input)
    if e and st.session_state.entry == 0.0:
        st.session_state.entry = e
    if s and st.session_state.sl == 0.0:
        st.session_state.sl = s
    if t and st.session_state.target == 0.0:
        st.session_state.target = t

#━━━━━━━━━━━━━━━━━━━
# PLAN
#━━━━━━━━━━━━━━━━━━━
plan = st.text_area("🧠 Plan", height=60)

#━━━━━━━━━━━━━━━━━━━
# TSL
#━━━━━━━━━━━━━━━━━━━
tsl = st.toggle("TSL Flip Required")

#━━━━━━━━━━━━━━━━━━━
# MODE INPUTS (COMPACT)
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
# TRADE LEVELS
#━━━━━━━━━━━━━━━━━━━
entry = st.number_input("Entry", key="entry")

#━━━━━━━━━━━━━━━━━━━
# 🔥 AUTO SL/TARGET ENGINE
#━━━━━━━━━━━━━━━━━━━
def generate_trade_plan(mode, entry):
    plans = []

    if entry == 0:
        return []

    if mode == "Breakout":
        sls = [entry - 5, entry - 8]
    elif mode == "Range":
        sls = [entry - 4, entry - 7]
    else:
        sls = [entry - 6]

    for sl in sls:
        risk = abs(entry - sl)
        targets = [entry + risk, entry + 2*risk, entry + 3*risk]

        for tgt in targets:
            rr = (tgt - entry) / risk if risk != 0 else 0
            plans.append({
                "SL": round(sl,2),
                "Target": round(tgt,2),
                "RR": round(rr,2)
            })

    return plans

#━━━━━━━━━━━━━━━━━━━
# GENERATE BUTTON
#━━━━━━━━━━━━━━━━━━━
if st.button("⚡ Generate Trade Plan"):
    plans = generate_trade_plan(mode, entry)

    if plans:
        df = pd.DataFrame(plans)

        st.markdown("### 🎯 Suggested Plans")
        st.dataframe(df, use_container_width=True)

        best = df[df["RR"] >= 2]

        if not best.empty:
            best_row = best.iloc[0]
            st.success(
                f"Best → SL: {best_row['SL']} | Target: {best_row['Target']} | RR: {best_row['RR']}"
            )
            st.session_state.sl = best_row["SL"]
            st.session_state.target = best_row["Target"]

#━━━━━━━━━━━━━━━━━━━
# SHOW FINAL VALUES
#━━━━━━━━━━━━━━━━━━━
sl = st.number_input("Stop Loss", key="sl")
target = st.number_input("Target", key="target")

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

    risk = abs(entry - sl)
    reward = abs(target - entry)
    rr = reward / risk if risk != 0 else 0

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.markdown(f"### {decision}")
    st.write(f"Score: {score} | RR: {round(rr,2)}")

    outcome = st.radio("Outcome", ["Win","Loss","BE"], horizontal=True)
    review = st.text_area("🔍 Review", height=60)

    file_name = "simulation_trades.csv"

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Score": score,
        "Decision": decision,
        "RR": rr,
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
# ANALYTICS
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 📊 Analytics")

try:
    df = pd.read_csv("simulation_trades.csv")

    total = len(df)
    wins = len(df[df["Outcome"] == "Win"])
    win_rate = round((wins / total)*100, 2) if total > 0 else 0

    st.metric("Trades", total)
    st.metric("Win %", win_rate)

except:
    st.info("No data yet")