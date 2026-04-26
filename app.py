import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# STYLE
#━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
header {visibility: hidden;}
.block-container {padding-top: 0.8rem;}

.top-bar {
    position: fixed;
    top: 0; left: 0; right: 0;
    background: #111827;
    z-index: 999;
    padding: 8px 12px;
    border-bottom: 1px solid #2f3542;
}

.card {
    background-color: #111827;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #2a2f3a;
}

.summary-box {
    padding: 6px;
    border-radius: 6px;
    text-align: center;
    border: 1px solid #333;
}

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
    "score": 0,
    "last_mode": "Range"
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_inputs():
    for k in defaults:
        if k != "last_mode":
            st.session_state[k] = defaults[k]

#━━━━━━━━━━━━━━━━━━━
# 🔥 INLINE SELECT (FIXED)
#━━━━━━━━━━━━━━━━━━━
def inline_select(label, options, key):
    unique_key = f"{key}_{st.session_state.last_mode}"

    c1, c2 = st.columns([1,2])
    c1.markdown(f"**{label}**")

    value = c2.selectbox(
        "",
        options,
        key=unique_key,
        label_visibility="collapsed"
    )

    # sync to main state
    st.session_state[key] = value

#━━━━━━━━━━━━━━━━━━━
# TOP BAR
#━━━━━━━━━━━━━━━━━━━
st.markdown('<div class="top-bar">', unsafe_allow_html=True)

c1, c2, c3 = st.columns([2,2,1.2])

with c1:
    st.radio("TSL", ["Yes","No"], horizontal=True, key="tsl")

with c2:
    mode = st.radio("Mode", ["Range","Breakout","Opening"], horizontal=True)

with c3:
    decision = st.session_state.decision
    score = st.session_state.score

    color = "green" if decision=="STRONG" else "yellow" if decision=="MODERATE" else "red"

    st.markdown(f"""
    <div class="summary-box">
        <div class="{color}">{decision}</div>
        <div class="small">Score: {score}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

#━━━━━━━━━━━━━━━━━━━
# MODE RESET
#━━━━━━━━━━━━━━━━━━━
if mode != st.session_state.last_mode:
    for k in ["cons","bb","retr","tl","sq","htf","prev","gap"]:
        st.session_state[k] = defaults[k]
    st.session_state.last_mode = mode

#━━━━━━━━━━━━━━━━━━━
# INPUT PANEL
#━━━━━━━━━━━━━━━━━━━
left, right = st.columns([1.2,1])

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if mode == "Range":
        inline_select("Cons", ["No","Yes","1T","2T","3T"], "cons")
        inline_select("BB", ["Yes","No"], "bb")
        inline_select("Ret", ["No","0.6","0.78"], "retr")

    elif mode == "Breakout":
        inline_select("Trendline", ["No","Yes"], "tl")
        inline_select("Squeeze", ["Yes","No"], "sq")
        inline_select("HTF", ["Above 0.786","Below 0.214","Neutral"], "htf")

    else:
        inline_select("Prev", ["Buy","Sell"], "prev")
        inline_select("Gap", ["Up","Down","None"], "gap")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.text_area("Note", height=100, key="note")

#━━━━━━━━━━━━━━━━━━━
# ENTRY
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

c1, c2, c3, c4 = st.columns(4)
st.number_input("Entry", key="entry")
st.number_input("SL", key="sl")
st.number_input("Target", key="target")
st.number_input("Exit", key="exit")

#━━━━━━━━━━━━━━━━━━━
# 🔥 PURE SCORING
#━━━━━━━━━━━━━━━━━━━
if st.session_state.tsl == "No":
    score = 0
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

#━━━━━━━━━━━━━━━━━━━
# RESULT
#━━━━━━━━━━━━━━━━━━━
e = st.session_state.entry
s = st.session_state.sl
x = st.session_state.exit

status = ""
pnl = 0

if e and s and x:
    if e > s:
        status = "LOSS" if x <= s else "WIN" if x > e else "BE"
        pnl = (x - e) if status == "WIN" else (s - e)
    else:
        status = "LOSS" if x >= s else "WIN" if x < e else "BE"
        pnl = (e - x) if status == "WIN" else (e - s)

if status:
    st.write(f"{status} | {round(pnl,2)}")

#━━━━━━━━━━━━━━━━━━━
# SAVE
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

sim_mode = st.toggle("Simulation Mode", True)
file_name = "simulation_trades.csv" if sim_mode else "live_trades.csv"

if st.button("SAVE TRADE"):

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Decision": decision,
        "Score": score,
        "Entry": e,
        "SL": s,
        "Target": st.session_state.target,
        "Exit": x,
        "Status": status,
        "PnL": pnl,
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
    reset_inputs()