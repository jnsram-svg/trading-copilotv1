import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="centered")

#━━━━━━━━━━━━━━━━━━━
# MOBILE TOGGLE (can remove later)
#━━━━━━━━━━━━━━━━━━━
is_mobile = st.checkbox("Mobile View", value=True)

#━━━━━━━━━━━━━━━━━━━
# SESSION
#━━━━━━━━━━━━━━━━━━━
if "decision" not in st.session_state:
    st.session_state.decision = ""
if "score" not in st.session_state:
    st.session_state.score = 0

#━━━━━━━━━━━━━━━━━━━
# TOP LAYOUT
#━━━━━━━━━━━━━━━━━━━
if not is_mobile:
    colL, colM, colR = st.columns(3)
else:
    colL = st.container()
    colM = st.container()
    colR = st.container()

# LEFT
with colL:
    trade_type = st.radio("Trade", ["TSL", "Opening"])

    if trade_type == "TSL":
        tsl_flip = st.checkbox("TSL Flip")
        mode = st.radio("Setup", ["Range", "Breakout"])

# RIGHT
with colR:
    sim_mode = st.checkbox("Sim Mode", True)
    review = st.text_area("Note", height=120 if is_mobile else 160)

file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

#━━━━━━━━━━━━━━━━━━━
# SETUP ROW
#━━━━━━━━━━━━━━━━━━━
if trade_type == "TSL":

    if not is_mobile:
        c1, c2, c3 = st.columns(3)
    else:
        c1 = st.container()
        c2 = st.container()
        c3 = st.container()

    if mode == "Range":
        cons = c1.selectbox("Consolidation", ["No","Yes","2T","3T"], key="cons")
        bb = c2.selectbox("Bollinger", ["Yes","No"], key="bb")
        retr = c3.selectbox("Retracement", ["No","0.6","0.78"], key="retr")

    else:
        tl = c1.selectbox("Trendline", ["No","Yes"], key="tl")
        sq = c2.selectbox("Squeeze", ["Yes","No"], key="sq")
        htf = c3.selectbox("HTF", ["Above 0.786","Below 0.214","Neutral"], key="htf")

else:
    if not is_mobile:
        c1, c2 = st.columns(2)
    else:
        c1 = st.container()
        c2 = st.container()

    prev = c1.selectbox("Prev", ["Buy","Sell"], key="prev")
    gap = c2.selectbox("Gap", ["Up","Down","None"], key="gap")

#━━━━━━━━━━━━━━━━━━━
# TRADE INPUT
#━━━━━━━━━━━━━━━━━━━
if not is_mobile:
    c1, c2, c3 = st.columns(3)
else:
    c1 = st.container()
    c2 = st.container()
    c3 = st.container()

entry = c1.number_input("Entry")
sl = c2.number_input("SL")
target = c3.number_input("Target")

exit_price = st.number_input("Exit")

#━━━━━━━━━━━━━━━━━━━
# AUTO EVALUATION
#━━━━━━━━━━━━━━━━━━━
score = 0

if trade_type == "TSL":

    if not tsl_flip:
        st.session_state.decision = "NO TRADE"

    else:
        if mode == "Range":
            if cons == "3T": score += 3
            elif cons == "2T": score += 2
            elif cons == "Yes": score += 1
            if bb == "Yes": score += 1
            if retr == "0.78": score += 2
            elif retr == "0.6": score += 1

        else:
            if tl == "Yes": score += 2
            if sq == "Yes": score += 2
            if htf != "Neutral": score += 1

else:
    if prev == "Buy" and gap == "Up": score += 3
    elif prev == "Buy" and gap == "Down": score += 2
    elif prev == "Sell" and gap == "Down": score += 3
    elif prev == "Sell" and gap == "Up": score += 2

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
# SUMMARY
#━━━━━━━━━━━━━━━━━━━
with colM:
    st.markdown("**Summary**")
    st.markdown(f"**{st.session_state.decision}**")
    st.caption(f"Score: {st.session_state.score}")

    if entry and sl and target and entry != sl:
        rr = abs(target - entry) / abs(entry - sl)
        st.caption(f"RR: {round(rr,2)}")

        if rr < 1:
            st.warning("Low RR")

#━━━━━━━━━━━━━━━━━━━
# RESULT
#━━━━━━━━━━━━━━━━━━━
status = ""
pnl = 0

if entry and sl and target and exit_price:

    if entry > sl:
        if exit_price <= sl:
            status = "LOSS"
            pnl = sl - entry
        elif exit_price > entry:
            status = "WIN"
            pnl = exit_price - entry
        else:
            status = "BREAKEVEN"
    else:
        if exit_price >= sl:
            status = "LOSS"
            pnl = entry - sl
        elif exit_price < entry:
            status = "WIN"
            pnl = entry - exit_price
        else:
            status = "BREAKEVEN"

if status:
    st.write(f"{status} | PnL: {round(pnl,2)}")

#━━━━━━━━━━━━━━━━━━━
# SAVE
#━━━━━━━━━━━━━━━━━━━
if st.button("Save"):

    log = {
        "Time": datetime.now(),
        "Entry": entry,
        "SL": sl,
        "Target": target,
        "Exit": exit_price,
        "Status": status,
        "PnL": pnl,
        "Decision": st.session_state.decision,
        "Score": st.session_state.score,
        "Review": review,
        "Mode": "Simulation" if sim_mode else "Live"
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
# DASHBOARD
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

mode_view = st.selectbox("Data View", ["Simulation", "Live"])
file_name_view = "simulation_trades.csv" if mode_view == "Simulation" else "live_trades.csv"

try:
    df = pd.read_csv(file_name_view)

    wins = len(df[df["Status"] == "WIN"])
    losses = len(df[df["Status"] == "LOSS"])
    closed = wins + losses

    win_rate = (wins / closed * 100) if closed > 0 else 0

    st.write(f"Trades: {len(df)} | Win%: {round(win_rate,1)}")

    summary = df.groupby("Decision").agg(
        Trades=("Decision", "count"),
        AvgPnL=("PnL", "mean"),
        WinRate=("Status", lambda x: (x == "WIN").sum()/len(x)*100)
    )

    st.dataframe(summary)

except:
    st.caption("No data yet")