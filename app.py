import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(layout="centered")

#━━━━━━━━━━━━━━━━━━━
# HEADER
#━━━━━━━━━━━━━━━━━━━
st.markdown("## 📱 Trading Copilot")

#━━━━━━━━━━━━━━━━━━━
# MODE
#━━━━━━━━━━━━━━━━━━━
mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

#━━━━━━━━━━━━━━━━━━━
# 🧠 PLAN (VOICE + STRUCTURED)
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🧠 Plan (CRT)")

# Initialize plan once
if "plan_text" not in st.session_state:
    st.session_state.plan_text = "Bias: \nKey Levels: \nHTF Trend: "

# Voice input
voice_input = st.text_input(
    "🎤 Voice Input (say: Bias…, Key Levels…, HTF…)",
    placeholder="Bias buy / Key levels 210 205 / HTF uptrend"
)

# Function to update plan safely
def update_plan(plan_text, voice_input):
    lines = plan_text.split("\n")

    # ensure 3 lines exist
    while len(lines) < 3:
        lines.append("")

    text = voice_input.lower()

    if "bias" in text:
        value = voice_input.lower().replace("bias", "").strip()
        lines[0] = f"Bias: {value.capitalize()}"

    elif "key" in text:
        value = voice_input.lower().replace("key levels", "").replace("key", "").strip()
        lines[1] = f"Key Levels: {value}"

    elif "htf" in text:
        value = voice_input.lower().replace("htf", "").strip()
        lines[2] = f"HTF Trend: {value.capitalize()}"

    return "\n".join(lines)

# Apply voice update
if voice_input:
    st.session_state.plan_text = update_plan(st.session_state.plan_text, voice_input)

# Plan box
plan_text = st.text_area("", key="plan_text", height=90)

# Extract structured values
def extract_plan(plan_text):
    lines = plan_text.split("\n")

    bias = lines[0].replace("Bias:", "").strip() if len(lines) > 0 else ""
    levels = lines[1].replace("Key Levels:", "").strip() if len(lines) > 1 else ""
    htf_trend = lines[2].replace("HTF Trend:", "").strip() if len(lines) > 2 else ""

    return bias, levels, htf_trend

bias_plan, key_levels_plan, htf_trend = extract_plan(plan_text)

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
entry = st.number_input("Entry", value=0.0)
sl = st.number_input("Stop Loss", value=0.0)
target = st.number_input("Target", value=0.0)

#━━━━━━━━━━━━━━━━━━━
# EVALUATE
#━━━━━━━━━━━━━━━━━━━
if st.button("🚀 Evaluate Trade"):

    tsl_condition = True if mode == "Opening" else tsl

    score = 0

    if tsl_condition:

        # RANGE
        if mode == "Range":
            score = (
                {"No":0,"1T":1,"2T":2,"3T":3}[cons] +
                {"No":0,"Yes":2}[bb] +
                {"No":0,"0.6":1,"0.78":2}[retr]
            )

        # BREAKOUT
        elif mode == "Breakout":
            score = (
                {"No":0,"Yes":2}[tl] +
                {"No":0,"Yes":2}[sq] +
                {"Neutral":0,"Above 0.786":2,"Below 0.214":2}[htf]
            )

        # OPENING
        else:
            base = {
                ("Buy","Up"):3,
                ("Buy","Down"):2,
                ("Sell","Down"):3,
                ("Sell","Up"):2
            }.get((prev, gap), 0)

            score = (
                base +
                {"No":0,"Yes":2}[op_cons] +
                {"No":0,"Yes":1}[op_bb]
            )

    else:
        st.warning("TSL not satisfied → No Trade")

    # RR
    risk = abs(entry - sl)
    reward = abs(target - entry)
    rr = reward / risk if risk != 0 else 0

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.markdown(f"### {decision}")
    st.write(f"Score: {score} | RR: {round(rr,2)}")

    follow = st.radio("Did you take this trade?", ["Yes","No"], horizontal=True)

    outcome = st.radio(
        "Outcome",
        ["Pending","Win","Loss","BE"],
        horizontal=True,
        index=0
    )

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

    st.success("Saved ✅")

#━━━━━━━━━━━━━━━━━━━
# CONTROLS
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

file_name = "simulation_trades.csv" if st.session_state.sim_mode else "live_trades.csv"

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