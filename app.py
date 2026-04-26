import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

#━━━━━━━━━━━━━━━━━━━
# STYLE
#━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
header {visibility:hidden;}
.block-container {padding-top: 0.8rem;}
.top-bar {
    position: fixed;
    top:0; left:0; right:0;
    background:#111827;
    padding:8px;
    z-index:999;
}
.summary-box {
    padding:6px;
    border-radius:6px;
    border:1px solid #333;
    text-align:center;
}
.green{color:#00ff88;}
.yellow{color:#ffaa00;}
.red{color:#ff4d4d;}
</style>
""", unsafe_allow_html=True)

#━━━━━━━━━━━━━━━━━━━
# DEFAULT STATE
#━━━━━━━━━━━━━━━━━━━
defaults = {
    "tsl":"No",
    "mode":"Range",
    "cons":"No",
    "bb":"No",
    "retr":"No",
    "tl":"No",
    "sq":"No",
    "htf":"Neutral",
    "prev":"Buy",
    "gap":"None",
    "entry":0.0,
    "sl":0.0,
    "target":0.0,
    "exit":0.0,
    "decision":"—",
    "score":0
}

for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=v

#━━━━━━━━━━━━━━━━━━━
# TOP BAR
#━━━━━━━━━━━━━━━━━━━
st.markdown('<div class="top-bar">', unsafe_allow_html=True)

c1,c2,c3 = st.columns([2,2,1])

with c1:
    st.radio("TSL",["Yes","No"],horizontal=True,key="tsl")

with c2:
    st.radio("Mode",["Range","Breakout","Opening"],horizontal=True,key="mode")

with c3:
    d = st.session_state.decision
    s = st.session_state.score
    color = "green" if d=="STRONG" else "yellow" if d=="MODERATE" else "red"

    st.markdown(f"""
    <div class="summary-box">
    <div class="{color}">{d}</div>
    <div>Score: {s}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

mode = st.session_state.mode

#━━━━━━━━━━━━━━━━━━━
# INPUTS
#━━━━━━━━━━━━━━━━━━━
st.markdown("---")

if mode=="Range":
    st.selectbox("Cons",["No","Yes","1T","2T","3T"],key="cons")
    st.selectbox("BB",["Yes","No"],key="bb")
    st.selectbox("Ret",["No","0.6","0.78"],key="retr")

elif mode=="Breakout":
    st.selectbox("Trendline",["No","Yes"],key="tl")
    st.selectbox("Squeeze",["Yes","No"],key="sq")
    st.selectbox("HTF",["Above 0.786","Below 0.214","Neutral"],key="htf")

else:
    st.selectbox("Prev",["Buy","Sell"],key="prev")
    st.selectbox("Gap",["Up","Down","None"],key="gap")

#━━━━━━━━━━━━━━━━━━━
# SCORING (PURE)
#━━━━━━━━━━━━━━━━━━━
if st.session_state.tsl == "No":
    score = 0
    decision = "NO TRADE"

else:
    if mode=="Range":
        score = (
            {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}[st.session_state.cons]
            + {"No":0,"Yes":1}[st.session_state.bb]
            + {"No":0,"0.6":1,"0.78":2}[st.session_state.retr]
        )

    elif mode=="Breakout":
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
        }.get((st.session_state.prev, st.session_state.gap),0)

    decision = "STRONG" if score>=6 else "MODERATE" if score>=3 else "NO TRADE"

st.session_state.score = score
st.session_state.decision = decision

#━━━━━━━━━━━━━━━━━━━
# RESULT
#━━━━━━━━━━━━━━━━━━━
e = st.session_state.entry
s = st.session_state.sl
x = st.session_state.exit

status=""
pnl=0

if e and s and x:
    if e>s:
        status="LOSS" if x<=s else "WIN" if x>e else "BE"
        pnl=(x-e) if status=="WIN" else (s-e)
    else:
        status="LOSS" if x>=s else "WIN" if x<e else "BE"
        pnl=(e-x) if status=="WIN" else (e-s)

if status:
    st.write(f"{status} | {round(pnl,2)}")