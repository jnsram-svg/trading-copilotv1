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
# PLAN SECTION (NEW)
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🧠 Plan")

plan = st.text_area("What is your plan?", height=80)

#━━━━━━━━━━━━━━━━━━━
# TSL
#━━━━━━━━━━━━━━━━━━━
tsl = st.checkbox("TSL Flip Required")

#━━━━━━━━━━━━━━━━━━━
# INPUTS
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
entry = st.number_input("Entry", value=0.0)
sl = st.number_input("Stop Loss", value=0.0)
target = st.number_input("Target", value=0.0)

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

    follow = st.radio("Follow Trade?", ["Yes","No"], horizontal=True)

    #━━━━━━━━ REVIEW SECTION (NEW)
    st.markdown("### 🔍 Review")
    review = st.text_area("Post-trade thoughts", height=80)

    #━━━━━━━━ FILE MODE
    sim_mode = st.session_state.get("sim_mode", True)
    file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Score": score,
        "Decision": decision,
        "RR": rr,
        "Followed": follow,
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

file_name = "simulation_trades.csv" if st.session_state.sim_mode else "live_trades.csv"

try:
    df = pd.read_csv(file_name)

    total = len(df)
    strong = len(df[df["Decision"] == "STRONG"])
    followed = len(df[df["Followed"] == "Yes"])

    win_rate = round((strong / total)*100, 2) if total > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Trades", total)
    c2.metric("Strong", strong)
    c3.metric("Win %", win_rate)

    st.dataframe(df.tail(10), use_container_width=True)

except:
    st.info("No data yet")