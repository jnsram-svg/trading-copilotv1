import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# 🎨 FINAL POLISHED STYLE
#━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>

/* Hide default header */
header {visibility: hidden;}

/* 🔥 PERFECT TOP ALIGNMENT */
.block-container {
    padding-top: 0.8rem;
    padding-bottom: 0rem;
}

/* Remove extra vertical gaps globally */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.4rem;
}

/* 🔥 STICKY TOP BAR */
.top-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;

    background: #111827;

    z-index: 999;

    padding: 8px 12px;

    border-bottom: 1px solid #2f3542;

    box-shadow: 0px 3px 10px rgba(0,0,0,0.35);
}

/* Card panel */
.card {
    background-color: #111827;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #2a2f3a;
}

/* Summary box */
.summary-box {
    padding: 6px;
    border-radius: 6px;
    text-align: center;
    border: 1px solid #333;
}

/* Colors */
.green {color:#00ff88;}
.yellow {color:#ffaa00;}
.red {color:#ff4d4d;}

.small {font-size: 0.72rem;}

</style>
""", unsafe_allow_html=True)

#━━━━━━━━━━━━━━━━━━━
# DEFAULT STATE
#━━━━━━━━━━━━━━━━━━━
defaults = {
    "tsl": "No",
    "cons": "No",
    "bb": "No",
    "retr": "No",
    "tl": "No",
    "sq": "No",
    "htf": "Neutral",
    "prev": "Buy",
    "gap": "None",
    "entry": 0.0,
    "target": 0.0,
    "sl": 0.0,
    "exit": 0.0,
    "note": "",
    "decision": "—",
    "score": 0
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_inputs():
    for k, v in defaults.items():
        st.session_state[k] = v

#━━━━━━━━━━━━━━━━━━━
# 🔝 TOP BAR
#━━━━━━━━━━━━━━━━━━━
st.markdown('<div class="top-bar">', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1,2,1,1.2])

with c1:
    tsl_flip = st.radio("TSL", ["Yes","No"], horizontal=True, key="tsl")

with c2:
    mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

with c3:
    sim_mode = st.toggle("Sim", True)

with c4:
    decision = st.session_state.decision
    score = st.session_state.score

    color = "green" if decision=="STRONG" else "yellow" if decision=="MODERATE" else "red"

    st.markdown(f"""
    <div class="summary-box">
        <div class="{color}" style="font-size:15px;">{decision}</div>
        <div class="small">Score: {score}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

#━━━━━━━━━━━━━━━━━━━
# MAIN PANEL
#━━━━━━━━━━━━━━━━━━━
left, right = st.columns([1.2,1])

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if mode == "Range":
        cons = st.selectbox("Cons", ["No","Yes","2T","3T"], key="cons")
        bb = st.selectbox("BB", ["Yes","No"], key="bb")
        retr = st.selectbox("Ret", ["No","0.6","0.78"], key="retr")

    elif mode == "Breakout":
        tl = st.selectbox("Trendline", ["No","Yes"], key="tl")
        sq = st.selectbox("Squeeze", ["Yes","No"], key="sq")
        htf = st.selectbox("HTF", ["Above 0.786","Below 0.214","Neutral"], key="htf")

    else:
        prev = st.selectbox("Prev", ["Buy","Sell"], key="prev")
        gap = st.selectbox("Gap", ["Up","Down","None"], key="gap")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    note = st.text_area("Note", height=110, key="note")

#━━━━━━━━━━━━━━━━━━━
# ENTRY
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

c1, c2 = st.columns(2)
entry = c1.number_input("Entry", key="entry")
target = c2.number_input("Target", key="target")

c1, c2 = st.columns(2)
sl = c1.number_input("SL", key="sl")
exit_price = c2.number_input("Exit", key="exit")

#━━━━━━━━━━━━━━━━━━━
# EVALUATION
#━━━━━━━━━━━━━━━━━━━
score = 0

if tsl_flip == "No":
    decision = "NO TRADE"
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

    if score >= 6:
        decision = "STRONG"
    elif score >= 3:
        decision = "MODERATE"
    else:
        decision = "NO TRADE"

st.session_state.score = score
st.session_state.decision = decision

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
# SAVE + RESET
#━━━━━━━━━━━━━━━━━━━
if st.button("SAVE TRADE"):

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Decision": decision,
        "Score": score,
        "Entry": entry,
        "SL": sl,
        "Target": target,
        "Exit": exit_price,
        "Status": status,
        "PnL": pnl,
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

    reset_inputs()

#━━━━━━━━━━━━━━━━━━━
# ANALYTICS
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

try:
    df = pd.read_csv(file_name)

    wins = len(df[df["Status"] == "WIN"])
    losses = len(df[df["Status"] == "LOSS"])
    closed = wins + losses

    win_rate = (wins / closed * 100) if closed else 0

    st.write(f"Trades: {len(df)} | Win%: {round(win_rate,1)}")
    st.dataframe(df.tail(10), use_container_width=True)

except:
    st.caption("No data yet")