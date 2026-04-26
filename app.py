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
# TOP BAR (V2 STYLE)
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
# INPUTS (ENUM SAFE)
#━━━━━━━━━━━━━━━━━━━
if mode == "Range":

    cons_label, cons_val = st.selectbox(
        "Cons",
        [("No",0), ("Yes",1), ("1T",1), ("2T",2), ("3T",3)],
        format_func=lambda x: x[0]
    )

    bb_label, bb_val = st.selectbox(
        "BB",
        [("No",0), ("Yes",1)],
        format_func=lambda x: x[0]
    )

    retr_label, retr_val = st.selectbox(
        "Ret",
        [("No",0), ("0.6",1), ("0.78",2)],
        format_func=lambda x: x[0]
    )

elif mode == "Breakout":

    tl_label, tl_val = st.selectbox(
        "Trendline",
        [("No",0), ("Yes",2)],
        format_func=lambda x: x[0]
    )

    sq_label, sq_val = st.selectbox(
        "Squeeze",
        [("No",0), ("Yes",2)],
        format_func=lambda x: x[0]
    )

    htf_label, htf_val = st.selectbox(
        "HTF",
        [("Neutral",0), ("Above 0.786",1), ("Below 0.214",1)],
        format_func=lambda x: x[0]
    )

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
# 🔥 SCORING (PURE — NO += ANYWHERE)
#━━━━━━━━━━━━━━━━━━━
if run:

    # ALWAYS RESET SCORE (CRITICAL)
    score = 0

    if tsl == "No":
        decision = "NO TRADE"

    else:
        if mode == "Range":

            # PURE CALCULATION (NO ACCUMULATION)
            score = cons_val + bb_val + retr_val

        elif mode == "Breakout":

            score = tl_val + sq_val + htf_val

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

    # 🔥 OVERWRITE (NOT ADD)
    st.session_state.score = int(score)
    st.session_state.decision = decision

#━━━━━━━━━━━━━━━━━━━
# SAVE (UNCHANGED)
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