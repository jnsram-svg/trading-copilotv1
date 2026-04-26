import streamlit as st

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# DEFAULT STATE
#━━━━━━━━━━━━━━━━━━━
if "score" not in st.session_state:
    st.session_state.score = 0
if "decision" not in st.session_state:
    st.session_state.decision = "—"

#━━━━━━━━━━━━━━━━━━━
# TOP BAR (V2)
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3 = st.columns([2,2,1])

with c1:
    tsl = st.radio("TSL", ["Yes","No"], horizontal=True)

with c2:
    mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

with c3:
    d = st.session_state.decision
    s = st.session_state.score
    st.markdown(f"**{d} | Score: {s}**")

#━━━━━━━━━━━━━━━━━━━
# INPUTS (V2 STRUCTURE)
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":
    cons = st.selectbox("Cons", ["No","Yes","1T","2T","3T"])
    bb = st.selectbox("BB", ["Yes","No"])
    retr = st.selectbox("Ret", ["No","0.6","0.78"])

elif mode == "Breakout":
    tl = st.selectbox("Trendline", ["No","Yes"])
    sq = st.selectbox("Squeeze", ["Yes","No"])
    htf = st.selectbox("HTF", ["Above 0.786","Below 0.214","Neutral"])

else:
    prev = st.selectbox("Prev", ["Buy","Sell"])
    gap = st.selectbox("Gap", ["Up","Down","None"])

#━━━━━━━━━━━━━━━━━━━
# 🔥 V1 STYLE SCORING FUNCTION
#━━━━━━━━━━━━━━━━━━━
def calculate_score():

    score = 0

    # TSL filter
    if tsl == "No":
        return 0, "NO TRADE"

    if mode == "Range":
        score = (
            {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}[cons]
            + {"No":0,"Yes":1}[bb]
            + {"No":0,"0.6":1,"0.78":2}[retr]
        )

    elif mode == "Breakout":
        score = (
            {"No":0,"Yes":2}[tl]
            + {"No":0,"Yes":2}[sq]
            + {"Neutral":0,"Above 0.786":1,"Below 0.214":1}[htf]
        )

    else:
        score = {
            ("Buy","Up"):3,
            ("Buy","Down"):2,
            ("Sell","Down"):3,
            ("Sell","Up"):2
        }.get((prev, gap), 0)

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

    return score, decision

#━━━━━━━━━━━━━━━━━━━
# 🔥 BUTTON (V1 BEHAVIOR)
#━━━━━━━━━━━━━━━━━━━
if st.button("Evaluate"):

    score, decision = calculate_score()

    st.session_state.score = score
    st.session_state.decision = decision