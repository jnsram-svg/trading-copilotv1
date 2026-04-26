import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re

st.set_page_config(layout="centered")

DRAFT_FILE = "draft_state.csv"

#━━━━━━━━━━━━━━━━━━━
# INIT DEFAULTS
#━━━━━━━━━━━━━━━━━━━
defaults = {
    "entry": 0.0,
    "sl": 0.0,
    "target": 0.0,
    "plan_text": "Bias: \nKey Levels: \nHTF Trend: "
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

#━━━━━━━━━━━━━━━━━━━
# LOAD DRAFT (ONLY ON FIRST LOAD)
#━━━━━━━━━━━━━━━━━━━
if "draft_loaded" not in st.session_state:
    if os.path.exists(DRAFT_FILE):
        try:
            draft = pd.read_csv(DRAFT_FILE).iloc[0].to_dict()
            for k in defaults.keys():
                if k in draft:
                    st.session_state[k] = draft[k]
            st.session_state.draft_loaded = True
            st.info("Draft restored ✔")
        except:
            pass
    else:
        st.session_state.draft_loaded = True

#━━━━━━━━━━━━━━━━━━━
# HEADER
#━━━━━━━━━━━━━━━━━━━
st.markdown("## 📱 Trading Copilot")

#━━━━━━━━━━━━━━━━━━━
# MODE
#━━━━━━━━━━━━━━━━━━━
mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

#━━━━━━━━━━━━━━━━━━━
# PLAN
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🧠 Plan (CRT)")
plan_text = st.text_area("", key="plan_text", height=90)

def extract_plan(plan_text):
    lines = plan_text.split("\n")
    bias = lines[0].replace("Bias:", "").strip() if len(lines) > 0 else ""
    levels = lines[1].replace("Key Levels:", "").strip() if len(lines) > 1 else ""
    htf_trend = lines[2].replace("HTF Trend:", "").strip() if len(lines) > 2 else ""
    return bias, levels, htf_trend

bias_plan, key_levels_plan, htf_trend = extract_plan(plan_text)

#━━━━━━━━━━━━━━━━━━━
# VOICE INPUT (ENTRY/SL/TARGET)
#━━━━━━━━━━━━━━━━━━━
voice_input = st.text_input("🎤 Voice Input")

def extract_trade_levels(text):
    text = text.lower()
    numbers = list(map(float, re.findall(r"\d+\.?\d*", text)))

    entry, sl, target = None, None, None

    sl_match = re.search(r"(sl|stop)[^\d]*(\d+\.?\d*)", text)
    if sl_match:
        sl = float(sl_match.group(2))

    tgt_match = re.search(r"(target|tgt)[^\d]*(\d+\.?\d*)", text)
    if tgt_match:
        target = float(tgt_match.group(2))

    used = {sl, target}
    for n in numbers:
        if n not in used:
            entry = n
            break

    return entry, sl, target

if voice_input:
    e, s, t = extract_trade_levels(voice_input)
    if e is not None:
        st.session_state.entry = e
    if s is not None:
        st.session_state.sl = s
    if t is not None:
        st.session_state.target = t

#━━━━━━━━━━━━━━━━━━━
# TSL
#━━━━━━━━━━━━━━━━━━━
tsl = st.checkbox("TSL Flip Required")

#━━━━━━━━━━━━━━━━━━━
# INPUTS
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":
    cons = st.selectbox("Cons", ["No","1T","2T","3T"])
    bb = st.selectbox("BB", ["No","Yes"])
    retr = st.selectbox("Ret", ["No","0.6","0.78"])

elif mode == "Breakout":
    tl = st.selectbox("Trendline", ["No","Yes"])
    sq = st.selectbox("Squeeze", ["No","Yes"])
    htf = st.selectbox("HTF", ["Neutral","Above 0.786","Below 0.214"])

else:
    prev = st.selectbox("Prev", ["Buy","Sell"])
    gap = st.selectbox("Gap", ["Up","Down","None"])
    op_cons = st.selectbox("Opening Consolidation", ["No","Yes"])
    op_bb = st.selectbox("Opening BB", ["No","Yes"])

#━━━━━━━━━━━━━━━━━━━
# TRADE LEVELS
#━━━━━━━━━━━━━━━━━━━
entry = st.number_input("Entry", key="entry")
sl = st.number_input("Stop Loss", key="sl")
target = st.number_input("Target", key="target")

#━━━━━━━━━━━━━━━━━━━
# EVALUATE
#━━━━━━━━━━━━━━━━━━━
if st.button("🚀 Evaluate Trade"):

    tsl_condition = True if mode == "Opening" else tsl
    score = 0

    if tsl_condition:
        if mode == "Range":
            score = (
                {"No":0,"1T":1,"2T":2,"3T":3}[cons] +
                {"No":0,"Yes":2}[bb] +
                {"No":0,"0.6":1,"0.78":2}[retr]
            )

        elif mode == "Breakout":
            score = (
                {"No":0,"Yes":2}[tl] +
                {"No":0,"Yes":2}[sq] +
                {"Neutral":0,"Above 0.786":2,"Below 0.214":2}[htf]
            )

        else:
            base = {
                ("Buy","Up"):3,
                ("Buy","Down"):2,
                ("Sell","Down"):3,
                ("Sell","Up"):2
            }.get((prev, gap), 0)

            score = base + {"No":0,"Yes":2}[op_cons] + {"No":0,"Yes":1}[op_bb]

    risk = abs(entry - sl)
    reward = abs(target - entry)
    rr = reward / risk if risk != 0 else 0

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.markdown(f"### {decision}")
    st.write(f"Score: {score} | RR: {round(rr,2)}")

    follow = st.radio("Did you take this trade?", ["Yes","No"], horizontal=True)
    outcome = st.radio("Outcome", ["Pending","Win","Loss","BE"], horizontal=True, index=0)
    review = st.text_area("🔍 Review", height=70)

    sim_mode = st.session_state.get("sim_mode", True)
    file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Score": score,
        "Decision": decision,
        "RR": rr,
        "Followed": follow,
        "Outcome": outcome,
        "Plan": plan_text,
        "BiasPlan": bias_plan,
        "KeyLevelsPlan": key_levels_plan,
        "HTFTrend": htf_trend,
        "Review": review
    }

    df = pd.DataFrame([log])

    try:
        old = pd.read_csv(file_name)
        df = pd.concat([old, df], ignore_index=True)
    except:
        pass

    df.to_csv(file_name, index=False)

    if os.path.exists(DRAFT_FILE):
        os.remove(DRAFT_FILE)

    st.success("Saved ✅")

#━━━━━━━━━━━━━━━━━━━
# AUTO SAVE DRAFT
#━━━━━━━━━━━━━━━━━━━
pd.DataFrame([{
    "entry": st.session_state.entry,
    "sl": st.session_state.sl,
    "target": st.session_state.target,
    "plan_text": st.session_state.plan_text
}]).to_csv(DRAFT_FILE, index=False)

#━━━━━━━━━━━━━━━━━━━
# ANALYTICS (RESTORED)
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 📊 Analytics")

file_name = "simulation_trades.csv"

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