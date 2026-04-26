import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# STATE
#━━━━━━━━━━━━━━━━━━━
if "score" not in st.session_state:
    st.session_state.score = 0

if "decision" not in st.session_state:
    st.session_state.decision = "—"

if "run_eval" not in st.session_state:
    st.session_state.run_eval = False

#━━━━━━━━━━━━━━━━━━━
# TOP BAR
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3, c4 = st.columns([2,2,1,1])

with c1:
    st.radio("TSL", ["Yes","No"], horizontal=True, key="tsl")

with c2:
    st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True, key="mode")

with c3:
    st.markdown(f"**{st.session_state.decision}**")
    st.caption(f"Score: {st.session_state.score}")

with c4:
    if st.button("⚡ Evaluate"):
        st.session_state.run_eval = True

mode = st.session_state.mode

#━━━━━━━━━━━━━━━━━━━
# INPUTS
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":
    cons = st.selectbox("Cons", ["No","Yes","1T","2T","3T"], key="cons")
    bb = st.selectbox("BB", ["Yes","No"], key="bb")
    retr = st.selectbox("Ret", ["No","0.6","0.78"], key="retr")

elif mode == "Breakout":
    tl = st.selectbox("Trendline", ["No","Yes"], key="tl")
    sq = st.selectbox("Squeeze", ["Yes","No"], key="sq")
    htf = st.selectbox("HTF", ["Above 0.786","Below 0.214","Neutral"], key="htf")

else:
    prev = st.selectbox("Prev", ["Buy","Sell"], key="prev")
    gap = st.selectbox("Gap", ["Up","Down","None"], key="gap")

#━━━━━━━━━━━━━━━━━━━
# TRADE INPUTS
#━━━━━━━━━━━━━━━━━━━
st.number_input("Entry", key="entry")
st.number_input("SL", key="sl")
st.number_input("Target", key="target")
st.number_input("Exit", key="exit")

#━━━━━━━━━━━━━━━━━━━
# 🔥 FREEZE + SCORE
#━━━━━━━━━━━━━━━━━━━
if st.session_state.run_eval:

    # 🔥 SNAPSHOT (CRITICAL)
    data = dict(st.session_state)

    score = 0

    if data["tsl"] == "No":
        decision = "NO TRADE"

    else:
        if data["mode"] == "Range":
            score = (
                {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}[data["cons"]]
                + {"No":0,"Yes":1}[data["bb"]]
                + {"No":0,"0.6":1,"0.78":2}[data["retr"]]
            )

        elif data["mode"] == "Breakout":
            score = (
                {"No":0,"Yes":2}[data["tl"]]
                + {"No":0,"Yes":2}[data["sq"]]
                + {"Neutral":0,"Above 0.786":1,"Below 0.214":1}[data["htf"]]
            )

        else:
            score = {
                ("Buy","Up"):3,
                ("Buy","Down"):2,
                ("Sell","Down"):3,
                ("Sell","Up"):2
            }.get((data["prev"], data["gap"]), 0)

        decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.session_state.score = score
    st.session_state.decision = decision

    # reset trigger
    st.session_state.run_eval = False

#━━━━━━━━━━━━━━━━━━━
# SAVE + ANALYTICS (UNCHANGED)
#━━━━━━━━━━━━━━━━━━━
sim_mode = st.toggle("Simulation Mode", True)
file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

if st.button("SAVE TRADE"):

    log = {
        "Time": datetime.now(),
        "Mode": st.session_state.mode,
        "Decision": st.session_state.decision,
        "Score": st.session_state.score,
        "Entry": st.session_state.entry,
        "SL": st.session_state.sl,
        "Target": st.session_state.target,
        "Exit": st.session_state.exit
    }

    df = pd.DataFrame([log])

    try:
        old = pd.read_csv(file_name)
        df = pd.concat([old, df], ignore_index=True)
    except:
        pass

    df.to_csv(file_name, index=False)

    st.success("Saved")

try:
    df = pd.read_csv(file_name)
    st.write(f"Trades: {len(df)}")
    st.dataframe(df.tail(10), use_container_width=True)
except:
    st.caption("No data yet")