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

#━━━━━━━━━━━━━━━━━━━
# TOP BAR
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3, c4 = st.columns([2,2,1,1])

with c1:
    tsl = st.radio("TSL", ["Yes","No"], horizontal=True)

with c2:
    mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

with c3:
    st.markdown(f"**{st.session_state.decision}**")
    st.caption(f"Score: {st.session_state.score}")

with c4:
    run = st.button("⚡ Evaluate")

#━━━━━━━━━━━━━━━━━━━
# INPUTS (ENUM VALUES)
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":

    cons = st.selectbox("Cons", [
        ("No",0),
        ("Yes",1),
        ("1T",1),
        ("2T",2),
        ("3T",3)
    ], format_func=lambda x: x[0])

    bb = st.selectbox("BB", [
        ("No",0),
        ("Yes",1)
    ], format_func=lambda x: x[0])

    retr = st.selectbox("Ret", [
        ("No",0),
        ("0.6",1),
        ("0.78",2)
    ], format_func=lambda x: x[0])

elif mode == "Breakout":

    tl = st.selectbox("Trendline", [
        ("No",0),
        ("Yes",2)
    ], format_func=lambda x: x[0])

    sq = st.selectbox("Squeeze", [
        ("No",0),
        ("Yes",2)
    ], format_func=lambda x: x[0])

    htf = st.selectbox("HTF", [
        ("Neutral",0),
        ("Above 0.786",1),
        ("Below 0.214",1)
    ], format_func=lambda x: x[0])

else:

    prev = st.selectbox("Prev", ["Buy","Sell"])
    gap = st.selectbox("Gap", ["Up","Down","None"])

#━━━━━━━━━━━━━━━━━━━
# SCORING (PURE NUMERIC)
#━━━━━━━━━━━━━━━━━━━
if run:

    score = 0

    if tsl == "No":
        decision = "NO TRADE"

    else:
        if mode == "Range":
            score = cons[1] + bb[1] + retr[1]

        elif mode == "Breakout":
            score = tl[1] + sq[1] + htf[1]

        else:
            mapping = {
                ("Buy","Up"):3,
                ("Buy","Down"):2,
                ("Sell","Down"):3,
                ("Sell","Up"):2
            }
            score = mapping.get((prev, gap), 0)

        decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    st.session_state.score = score
    st.session_state.decision = decision

#━━━━━━━━━━━━━━━━━━━
# DISPLAY
#━━━━━━━━━━━━━━━━━━━
st.write(f"Score: {st.session_state.score}")