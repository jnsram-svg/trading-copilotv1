import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# STATE
#━━━━━━━━━━━━━━━━━━━
if "score" not in st.session_state:
    st.session_state.score = 0
if "decision" not in st.session_state:
    st.session_state.decision = "—"
if "sim_mode" not in st.session_state:
    st.session_state.sim_mode = True

#━━━━━━━━━━━━━━━━━━━
# TOP BAR (OLD V2 LOOK)
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3 = st.columns([2,2,1])

with c1:
    mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

with c2:
    tsl = st.radio("TSL", ["Yes","No"], horizontal=True)

with c3:
    st.markdown(f"### {st.session_state.decision}")
    st.caption(f"Score: {st.session_state.score}")

#━━━━━━━━━━━━━━━━━━━
# FORM (KEY FIX — BUT INVISIBLE TO USER)
#━━━━━━━━━━━━━━━━━━━
with st.form("main_form"):

    #━━━━━━━━ PLAN
    plan = st.text_area("Plan", height=60)

    #━━━━━━━━ INPUTS (COMPACT LIKE V2)
    if mode == "Range":
        col1, col2, col3 = st.columns(3)
        with col1:
            cons = st.selectbox("Cons", ["No","Yes","1T","2T","3T"])
        with col2:
            bb = st.selectbox("BB", ["No","Yes"])
        with col3:
            retr = st.selectbox("Ret", ["No","0.6","0.78"])

    elif mode == "Breakout":
        col1, col2, col3 = st.columns(3)
        with col1:
            tl = st.selectbox("Trendline", ["No","Yes"])
        with col2:
            sq = st.selectbox("Squeeze", ["No","Yes"])
        with col3:
            htf = st.selectbox("HTF", ["Neutral","Above 0.786","Below 0.214"])

    else:
        col1, col2 = st.columns(2)
        with col1:
            prev = st.selectbox("Prev", ["Buy","Sell"])
        with col2:
            gap = st.selectbox("Gap", ["Up","Down","None"])

    #━━━━━━━━ TRADE LEVELS (INLINE)
    c1, c2, c3 = st.columns(3)
    entry = c1.number_input("Entry", value=0.0)
    sl = c2.number_input("SL", value=0.0)
    target = c3.number_input("Target", value=0.0)

    #━━━━━━━━ REVIEW
    review = st.text_area("Review", height=60)

    #━━━━━━━━ BIG EVALUATE BUTTON
    submitted = st.form_submit_button("🚀 Evaluate Trade")

#━━━━━━━━━━━━━━━━━━━
# SCORING (STABLE — V1 STYLE)
#━━━━━━━━━━━━━━━━━━━
if submitted:

    if tsl == "No":
        score = 0
        decision = "NO TRADE"

    else:
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

        decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    # SAVE RESULT
    st.session_state.score = score
    st.session_state.decision = decision

    # SHOW RESULT INLINE
    st.success(f"{decision} | Score: {score}")

    #━━━━━━━━ SAVE
    file_name = "simulation_trades.csv" if st.session_state.sim_mode else "live_trades.csv"

    log = {
        "Time": datetime.now(),
        "Mode": mode,
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

#━━━━━━━━━━━━━━━━━━━
# BOTTOM CONTROLS (UNCHANGED)
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.session_state.sim_mode = st.toggle("Simulation Mode", st.session_state.sim_mode)

with c2:
    if st.button("🗑 Clear Simulation Data"):
        if os.path.exists("simulation_trades.csv"):
            os.remove("simulation_trades.csv")
            st.success("Cleared ✅")
        else:
            st.info("No data")

#━━━━━━━━━━━━━━━━━━━
# ANALYTICS
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 📊 Analytics")

file_name = "simulation_trades.csv" if st.session_state.sim_mode else "live_trades.csv"

try:
    df = pd.read_csv(file_name)

    st.write(f"Trades: {len(df)}")

    st.dataframe(df.tail(10), use_container_width=True)

except:
    st.caption("No data yet")