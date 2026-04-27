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
quick_input = st.text_input("🎤 Quick Input", placeholder="Buy 210 SL 205 Target 230")

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
# ENTRY
#━━━━━━━━━━━━━━━━━━━
entry = st.number_input("Entry", key="entry")

#━━━━━━━━━━━━━━━━━━━
# 🧭 REQUIRED INPUTS (TRAINER MODE)
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🧭 Required Inputs")

range_low = range_high = prev_mean = 0
bcl = bch = 0
first_low = first_high = 0

if mode == "Range" and tsl:
    st.info("Feed: Range Low + Range High + Previous Range Mean")

    range_low = st.number_input("Range Low")
    range_high = st.number_input("Range High")
    prev_mean = st.number_input("Previous Range Mean")

elif mode == "Breakout":
    st.info("Feed: Breakout Candle Low / High")

    bcl = st.number_input("Breakout Candle Low")
    bch = st.number_input("Breakout Candle High")

elif mode == "Opening":
    st.info("Feed: First 5-min Candle Levels")

    first_low = st.number_input("First Candle Low")
    first_high = st.number_input("First Candle High")

#━━━━━━━━━━━━━━━━━━━
# 🔥 RULE ENGINE
#━━━━━━━━━━━━━━━━━━━
def derive_sl_target(mode, entry, tsl,
                     cons=None, bb=None, retr=None,
                     tl=None, sq=None, htf=None,
                     prev=None, gap=None,
                     range_low=0, range_high=0, prev_mean=0,
                     bcl=0, bch=0,
                     first_low=0, first_high=0):

    sl = 0
    target = 0

    #━━━━━━━━ RANGE (TSL LOGIC)
    if mode == "Range" and tsl:

        if range_low > 0 and prev_mean > 0:

            sl = range_low
            target = prev_mean

            # Retracement → 0.384 logic
            if retr in ["0.6", "0.78"] and range_high > 0:
                target = range_low + (range_high - range_low) * 0.384

            # Strong → extend
            if retr in ["0.6", "0.78"] and bb == "Yes":
                target = range_high

    #━━━━━━━━ BREAKOUT
    elif mode == "Breakout":

        if bcl > 0 or bch > 0:

            sl = bcl if entry > bcl else bch
            risk = abs(entry - sl)

            if sq == "Yes" and tl == "Yes":
                target = entry + 3 * risk
            else:
                target = entry + 2 * risk

    #━━━━━━━━ OPENING
    elif mode == "Opening":

        if first_low > 0 or first_high > 0:

            if entry > first_low:
                sl = first_low
                risk = entry - sl
                target = entry + (1.5 * risk if (prev=="Buy" and gap=="Up") else 1*risk)

            else:
                sl = first_high
                risk = sl - entry
                target = entry - (1.5 * risk if (prev=="Sell" and gap=="Down") else 1*risk)

    return round(sl,2), round(target,2)

#━━━━━━━━━━━━━━━━━━━
# AUTO APPLY
#━━━━━━━━━━━━━━━━━━━
if entry > 0:

    sl_auto, target_auto = derive_sl_target(
        mode, entry, tsl,
        cons if mode=="Range" else None,
        bb if mode=="Range" else None,
        retr if mode=="Range" else None,
        tl if mode=="Breakout" else None,
        sq if mode=="Breakout" else None,
        htf if mode=="Breakout" else None,
        prev if mode=="Opening" else None,
        gap if mode=="Opening" else None,
        range_low, range_high, prev_mean,
        bcl, bch,
        first_low, first_high
    )

    if sl_auto > 0:
        st.session_state.sl = sl_auto
        st.session_state.target = target_auto

#━━━━━━━━━━━━━━━━━━━
# FINAL LEVELS
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