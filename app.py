import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# STYLE (TABLE LOOK)
#━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
.block-container {padding-top: 0.5rem;}
label {font-size: 0.8rem !important;}
</style>
""", unsafe_allow_html=True)

#━━━━━━━━━━━━━━━━━━━
# SESSION
#━━━━━━━━━━━━━━━━━━━
if "decision" not in st.session_state:
    st.session_state.decision = ""
if "score" not in st.session_state:
    st.session_state.score = 0

#━━━━━━━━━━━━━━━━━━━
# TOP ROW
#━━━━━━━━━━━━━━━━━━━
c1, c2, c3 = st.columns([1,1,1])

with c1:
    tsl_flip = st.selectbox("TSL Flip", ["Yes","No"])

with c2:
    mode = st.selectbox("Mode", ["Range","Breakout","Opening"])

with c3:
    sim_mode = st.toggle("Sim Mode", True)

file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

#━━━━━━━━━━━━━━━━━━━
# TABLE BODY
#━━━━━━━━━━━━━━━━━━━
left, right = st.columns([1.2,1])

# LEFT SIDE (SETUP)
with left:

    if mode == "Range":
        cons = st.selectbox("Cons", ["No","Yes","2T","3T"])
        bb = st.selectbox("BB", ["Yes","No"])
        retr = st.selectbox("Ret", ["No","0.6","0.78"])

    elif mode == "Breakout":
        tl = st.selectbox("Trendline", ["No","Yes"])
        sq = st.selectbox("Squeeze", ["Yes","No"])
        htf = st.selectbox("HTF", ["Above 0.786","Below 0.214","Neutral"])

    else:
        prev = st.selectbox("Prev", ["Buy","Sell"])
        gap = st.selectbox("Gap", ["Up","Down","None"])

# RIGHT SIDE (SUMMARY + NOTE)
with right:

    st.markdown("**Summary**")

    st.markdown(f"**{st.session_state.decision}**")
    st.caption(f"Score: {st.session_state.score}")

    note = st.text_area("Note", height=100)

#━━━━━━━━━━━━━━━━━━━
# ENTRY / TARGET ROW
#━━━━━━━━━━━━━━━━━━━
c1, c2 = st.columns(2)

entry = c1.number_input("Entry")
target = c2.number_input("Target")

#━━━━━━━━━━━━━━━━━━━
# SL / EXIT ROW
#━━━━━━━━━━━━━━━━━━━
c1, c2 = st.columns(2)

sl = c1.number_input("SL")
exit_price = c2.number_input("Exit")

#━━━━━━━━━━━━━━━━━━━
# AUTO EVALUATION
#━━━━━━━━━━━━━━━━━━━
score = 0

if tsl_flip == "No":
    st.session_state.decision = "NO TRADE"

else:
    if mode == "Range":
        if cons == "3T": score += 3
        elif cons == "2T": score += 2
        elif cons == "Yes": score += 1
        if bb == "Yes": score += 1
        if retr == "0.78": score += 2
        elif retr == "0.6": score += 1

    elif mode == "Breakout":
        if tl == "Yes": score += 2
        if sq == "Yes": score += 2
        if htf != "Neutral": score += 1

    else:
        if prev == "Buy" and gap == "Up": score += 3
        elif prev == "Buy" and gap == "Down": score += 2
        elif prev == "Sell" and gap == "Down": score += 3
        elif prev == "Sell" and gap == "Up": score += 2

# RR
if entry and sl and target and entry != sl:
    rr = abs(target - entry) / abs(entry - sl)
    if rr >= 2: score += 2
    elif rr >= 1: score += 1

st.session_state.score = score

if score >= 6:
    st.session_state.decision = "STRONG"
elif score >= 3:
    st.session_state.decision = "MODERATE"
else:
    st.session_state.decision = "NO TRADE"

#━━━━━━━━━━━━━━━━━━━
# RESULT
#━━━━━━━━━━━━━━━━━━━
status = ""
pnl = 0

if entry and sl and exit_price:

    if entry > sl:
        if exit_price <= sl:
            status = "LOSS"
            pnl = sl - entry
        elif exit_price > entry:
            status = "WIN"
            pnl = exit_price - entry
        else:
            status = "BE"
    else:
        if exit_price >= sl:
            status = "LOSS"
            pnl = entry - sl
        elif exit_price < entry:
            status = "WIN"
            pnl = entry - exit_price
        else:
            status = "BE"

if status:
    st.write(f"{status} | {round(pnl,2)}")

#━━━━━━━━━━━━━━━━━━━
# SAVE
#━━━━━━━━━━━━━━━━━━━
if st.button("Save"):

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Entry": entry,
        "SL": sl,
        "Target": target,
        "Exit": exit_price,
        "Status": status,
        "PnL": pnl,
        "Decision": st.session_state.decision,
        "Score": st.session_state.score,
        "Note": note
    }

    df = pd.DataFrame([log])

    try:
        old = pd.read_csv(file_name)
        df = pd.concat([old, df], ignore_index=True)
    except:
        pass

    df.to_csv(file_name, index=False)
    st.success("Saved")

#━━━━━━━━━━━━━━━━━━━
# ANALYTICS
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

mode_view = st.selectbox("Data", ["Simulation","Live"])
file_name_view = "simulation_trades.csv" if mode_view == "Simulation" else "live_trades.csv"

try:
    df = pd.read_csv(file_name_view)

    wins = len(df[df["Status"] == "WIN"])
    losses = len(df[df["Status"] == "LOSS"])
    closed = wins + losses

    win_rate = (wins / closed * 100) if closed > 0 else 0

    st.write(f"Trades: {len(df)} | Win%: {round(win_rate,1)}")

    summary = df.groupby("Decision").agg(
        Trades=("Decision","count"),
        AvgPnL=("PnL","mean"),
        WinRate=("Status", lambda x: (x=="WIN").sum()/len(x)*100)
    )

    st.dataframe(summary, use_container_width=True)

except:
    st.caption("No data")