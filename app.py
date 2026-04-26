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
# 🧠 PLAN (CRT SINGLE BOX)
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🧠 Plan (CRT)")

plan_text = st.text_area(
    "",
    value="Bias:\nKey Levels:\nHTF Trend:",
    height=90
)

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

    # Opening does not require TSL
    tsl_condition = True if mode == "Opening" else tsl

    score = 0

    if tsl_condition:

        #━━━━━━━━ RANGE (UPDATED)
        if mode == "Range":
            score = (
                {"No":0,"1T":1,"2T":2,"3T":3}[cons] +
                {"No":0,"Yes":2}[bb] +
                {"No":0,"0.6":1,"0.78":2}[retr]
            )

        #━━━━━━━━ BREAKOUT (UPDATED)
        elif mode == "Breakout":
            score = (
                {"No":0,"Yes":2}[tl] +
                {"No":0,"Yes":2}[sq] +
                {"Neutral":0,"Above 0.786":2,"Below 0.214":2}[htf]
            )

        #━━━━━━━━ OPENING (UPDATED)
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

    #━━━━━━━━ RR
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

#━━━━━━━━━━━━━━━━━━━
# WIN RATE BY SCORE
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 📈 Win Rate by Score")

try:
    df = pd.read_csv(file_name)

    if "Score" in df.columns and "Outcome" in df.columns:

        score_stats = []

        for s in sorted(df["Score"].dropna().unique()):
            subset = df[df["Score"] == s]

            total = len(subset)
            wins = len(subset[subset["Outcome"] == "Win"])

            win_rate = round((wins / total)*100, 2) if total > 0 else 0

            score_stats.append({
                "Score": s,
                "Trades": total,
                "Wins": wins,
                "Win %": win_rate
            })

        score_df = pd.DataFrame(score_stats).sort_values(by="Score", ascending=False)

        st.dataframe(score_df, use_container_width=True)

    else:
        st.info("Score/Outcome data not available yet")

except:
    st.info("No data yet")