import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# STATE INIT
#━━━━━━━━━━━━━━━━━━━
if "score" not in st.session_state:
    st.session_state.score = 0

if "decision" not in st.session_state:
    st.session_state.decision = "—"

#━━━━━━━━━━━━━━━━━━━
# TOP BAR (V2)
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
# INPUTS (LOCAL VARIABLES ONLY)
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
# TRADE INPUTS
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3, c4 = st.columns(4)

entry = st.number_input("Entry")
sl = st.number_input("SL")
target = st.number_input("Target")
exit_price = st.number_input("Exit")

note = st.text_area("Notes")

#━━━━━━━━━━━━━━━━━━━
# 🔥 CORRECT SCORING (PURE)
#━━━━━━━━━━━━━━━━━━━
if run:

    # ALWAYS RESET
    score = 0

    if tsl == "No":
        decision = "NO TRADE"

    else:
        if mode == "Range":

            cons_map = {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}
            bb_map = {"No":0,"Yes":1}
            retr_map = {"No":0,"0.6":1,"0.78":2}

            score = cons_map[cons] + bb_map[bb] + retr_map[retr]

        elif mode == "Breakout":

            tl_map = {"No":0,"Yes":2}
            sq_map = {"No":0,"Yes":2}
            htf_map = {"Neutral":0,"Above 0.786":1,"Below 0.214":1}

            score = tl_map[tl] + sq_map[sq] + htf_map[htf]

        else:

            score = {
                ("Buy","Up"):3,
                ("Buy","Down"):2,
                ("Sell","Down"):3,
                ("Sell","Up"):2
            }.get((prev, gap), 0)

        # DECISION
        if score >= 6:
            decision = "STRONG"
        elif score >= 3:
            decision = "MODERATE"
        else:
            decision = "NO TRADE"

    # 🔥 OVERWRITE ONLY
    st.session_state.score = score
    st.session_state.decision = decision

#━━━━━━━━━━━━━━━━━━━
# SAVE
#━━━━━━━━━━━━━━━━━━━
sim_mode = st.toggle("Simulation Mode", True)
file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

if st.button("SAVE TRADE"):

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Decision": st.session_state.decision,
        "Score": st.session_state.score,
        "Entry": entry,
        "SL": sl,
        "Target": target,
        "Exit": exit_price,
        "Note": note
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
try:
    df = pd.read_csv(file_name)

    st.write(f"Trades: {len(df)}")
    st.dataframe(df.tail(10), use_container_width=True)

except:
    st.caption("No data yet")