import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# 🎨 STYLE (BIG SWITCH)
#━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
header {visibility:hidden;}

div[data-testid="stToggle"] {
    border: 1px solid #333;
    padding: 12px;
    border-radius: 10px;
    background-color: #111827;
    margin-top: 6px;
}

div[data-testid="stToggle"] label p {
    font-size: 18px !important;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

#━━━━━━━━━━━━━━━━━━━
# STATE
#━━━━━━━━━━━━━━━━━━━
if "score" not in st.session_state:
    st.session_state.score = 0
if "decision" not in st.session_state:
    st.session_state.decision = "—"

#━━━━━━━━━━━━━━━━━━━
# TOP BAR (UNCHANGED V2)
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
    evaluate_clicked = st.toggle("⚡ Evaluate", key="eval_toggle")

mode = st.session_state.mode

#━━━━━━━━━━━━━━━━━━━
# INPUTS (UNCHANGED)
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":
    st.selectbox("Cons", ["No","Yes","1T","2T","3T"], key="cons")
    st.selectbox("BB", ["Yes","No"], key="bb")
    st.selectbox("Ret", ["No","0.6","0.78"], key="retr")

elif mode == "Breakout":
    st.selectbox("Trendline", ["No","Yes"], key="tl")
    st.selectbox("Squeeze", ["Yes","No"], key="sq")
    st.selectbox("HTF", ["Above 0.786","Below 0.214","Neutral"], key="htf")

else:
    st.selectbox("Prev", ["Buy","Sell"], key="prev")
    st.selectbox("Gap", ["Up","Down","None"], key="gap")

#━━━━━━━━━━━━━━━━━━━
# TRADE INPUTS (UNCHANGED)
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3, c4 = st.columns(4)
st.number_input("Entry", key="entry")
st.number_input("SL", key="sl")
st.number_input("Target", key="target")
st.number_input("Exit", key="exit")

st.text_area("Notes", key="note")

#━━━━━━━━━━━━━━━━━━━
# 🔥 SCORING (ONLY WHEN TOGGLED)
#━━━━━━━━━━━━━━━━━━━
if evaluate_clicked:

    score = 0

    if st.session_state.tsl == "No":
        decision = "NO TRADE"

    else:
        if mode == "Range":
            score = (
                {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}[st.session_state.cons]
                + {"No":0,"Yes":1}[st.session_state.bb]
                + {"No":0,"0.6":1,"0.78":2}[st.session_state.retr]
            )

        elif mode == "Breakout":
            score = (
                {"No":0,"Yes":2}[st.session_state.tl]
                + {"No":0,"Yes":2}[st.session_state.sq]
                + {"Neutral":0,"Above 0.786":1,"Below 0.214":1}[st.session_state.htf]
            )

        else:
            score = {
                ("Buy","Up"):3,
                ("Buy","Down"):2,
                ("Sell","Down"):3,
                ("Sell","Up"):2
            }.get((st.session_state.prev, st.session_state.gap), 0)

        decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.session_state.score = score
    st.session_state.decision = decision

    # reset toggle (important)
    st.session_state.eval_toggle = False

#━━━━━━━━━━━━━━━━━━━
# SAVE (UNCHANGED)
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
        "Exit": st.session_state.exit,
        "Note": st.session_state.note
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
# ANALYTICS (UNCHANGED)
#━━━━━━━━━━━━━━━━━━━
try:
    df = pd.read_csv(file_name)

    total = len(df)
    strong = len(df[df["Decision"] == "STRONG"])

    st.write(f"Trades: {total}")
    st.write(f"Strong Trades: {strong}")

    st.dataframe(df.tail(10), use_container_width=True)

except:
    st.caption("No data yet")