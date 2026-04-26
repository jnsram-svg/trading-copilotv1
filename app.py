import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# 🎨 STYLE (STABLE + COMPACT)
#━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>

header {visibility: hidden;}

.block-container {
    padding-top: 0.6rem;
}

/* TOP BAR */
.top-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: #111827;
    z-index: 999;
    padding: 8px 10px;
    border-bottom: 1px solid #2f3542;
    box-shadow: 0px 3px 8px rgba(0,0,0,0.35);
}

/* BUTTON TABS */
.tab-btn button {
    width: 100%;
    height: 40px;
    border-radius: 6px;
}

/* CARD */
.card {
    background-color: #111827;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #2a2f3a;
}

/* SUMMARY */
.summary-box {
    padding: 6px;
    border-radius: 6px;
    text-align: center;
    border: 1px solid #333;
}

.green {color:#00ff88;}
.yellow {color:#ffaa00;}
.red {color:#ff4d4d;}

</style>
""", unsafe_allow_html=True)

#━━━━━━━━━━━━━━━━━━━
# DEFAULT STATE
#━━━━━━━━━━━━━━━━━━━
defaults = {
    "tsl": "No",
    "mode": "Range",
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
# 🔝 TOP BAR (NO WRAP)
#━━━━━━━━━━━━━━━━━━━
st.markdown('<div class="top-bar">', unsafe_allow_html=True)

c1, c2, c3 = st.columns([2.5,2,1.2])

# TSL + SIM
with c1:
    t1, t2, t3 = st.columns([1,1,1])

    if t1.button("TSL YES"):
        st.session_state.tsl = "Yes"
    if t2.button("TSL NO"):
        st.session_state.tsl = "No"

    sim_mode = t3.toggle("Sim", True)

# MODE BUTTONS
with c2:
    m1, m2, m3 = st.columns(3)

    if m1.button("Range"):
        st.session_state.mode = "Range"
    if m2.button("Breakout"):
        st.session_state.mode = "Breakout"
    if m3.button("Opening"):
        st.session_state.mode = "Opening"

mode = st.session_state.mode

# SUMMARY
with c3:
    decision = st.session_state.decision
    score = st.session_state.score

    color = "green" if decision=="STRONG" else "yellow" if decision=="MODERATE" else "red"

    st.markdown(f"""
    <div class="summary-box">
        <div class="{color}" style="font-size:14px;">{decision}</div>
        <div style="font-size:11px;">Score: {score}</div>
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

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    note = st.text_area("Note", height=100)

#━━━━━━━━━━━━━━━━━━━
# ENTRY
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

c1, c2, c3, c4 = st.columns(4)
entry = c1.number_input("Entry")
sl = c2.number_input("SL")
target = c3.number_input("Target")
exit_price = c4.number_input("Exit")

#━━━━━━━━━━━━━━━━━━━
# EVALUATION
#━━━━━━━━━━━━━━━━━━━
score = 0
tsl_flip = st.session_state.tsl

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

    decision = "STRONG" if score >= 6 else "MODERATE" if score >= 3 else "NO TRADE"

st.session_state.score = score
st.session_state.decision = decision

#━━━━━━━━━━━━━━━━━━━
# RESULT
#━━━━━━━━━━━━━━━━━━━
status = ""
pnl = 0

if entry and sl and exit_price:
    if entry > sl:
        status = "LOSS" if exit_price <= sl else "WIN" if exit_price > entry else "BE"
        pnl = (exit_price - entry) if status == "WIN" else (sl - entry)
    else:
        status = "LOSS" if exit_price >= sl else "WIN" if exit_price < entry else "BE"
        pnl = (entry - exit_price) if status == "WIN" else (entry - sl)

if status:
    st.write(f"{status} | {round(pnl,2)}")

#━━━━━━━━━━━━━━━━━━━
# SAVE
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