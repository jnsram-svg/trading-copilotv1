import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Trading Copilot", layout="centered")

st.title("📱 Trading Copilot (Stable Version)")

#━━━━━━━━━━━━━━━━━━━
# STEP 1 — TSL
#━━━━━━━━━━━━━━━━━━━
tsl_flip = st.checkbox("🔁 TSL Flip (Required for Range/Breakout only)")

#━━━━━━━━━━━━━━━━━━━
# STEP 2 — MODE
#━━━━━━━━━━━━━━━━━━━
mode = st.radio("Mode", ["Range", "Breakout", "Opening"], horizontal=True)

#━━━━━━━━━━━━━━━━━━━
# RANGE SETUP
#━━━━━━━━━━━━━━━━━━━
range_setups = []
touch_count = 0

if mode == "Range":
    st.subheader("Range Setup")

    cons = st.selectbox("Consolidation", ["No","Yes","1T","2T","3T"])
    bb = st.selectbox("Bollinger", ["No","Yes"])
    retr = st.selectbox("Retracement", ["No","0.6","0.78"])

#━━━━━━━━━━━━━━━━━━━
# BREAKOUT SETUP
#━━━━━━━━━━━━━━━━━━━
if mode == "Breakout":
    st.subheader("Breakout Setup")

    tl = st.selectbox("Trendline Break", ["No","Yes"])
    sq = st.selectbox("Squeeze", ["No","Yes"])
    htf_position = st.selectbox(
        "HTF Position",
        ["Neutral","Above 0.786","Below 0.214"]
    )

#━━━━━━━━━━━━━━━━━━━
# OPENING SETUP
#━━━━━━━━━━━━━━━━━━━
if mode == "Opening":
    st.subheader("Opening Setup")

    prev_break = st.checkbox("Prev Day Trendline Break")

    break_dir = st.radio(
        "Break Direction",
        ["Buy","Sell"],
        horizontal=True
    )

    gap_type = st.radio(
        "Gap Type",
        ["Up","Down","None"],
        horizontal=True
    )

#━━━━━━━━━━━━━━━━━━━
# TRADE INPUTS
#━━━━━━━━━━━━━━━━━━━
st.subheader("Trade Levels")

entry = st.number_input("Entry", value=0.0)
stop = st.number_input("Stop Loss", value=0.0)
target = st.number_input("Final Target", value=0.0)

nearest_target = st.number_input(
    "Nearest Structure Target",
    value=0.0
)

view = st.text_area("Your View (optional)")

#━━━━━━━━━━━━━━━━━━━
# EVALUATION FUNCTION
#━━━━━━━━━━━━━━━━━━━
def evaluate():

    score = 0
    reasons = []

    # TSL filter
    if mode in ["Range","Breakout"]:
        if not tsl_flip:
            return "❌ REJECTED", ["No TSL Flip"], 0, 0
        reasons.append("✔ TSL Flip")

    if mode == "Opening":
        reasons.append("✔ Opening Mode")

    #━━━━━━━━ RANGE
    if mode == "Range":

        score += {"No":0,"Yes":1,"1T":1,"2T":2,"3T":3}[cons]
        score += {"No":0,"Yes":1}[bb]
        score += {"No":0,"0.6":1,"0.78":2}[retr]

    #━━━━━━━━ BREAKOUT
    if mode == "Breakout":

        score += {"No":0,"Yes":2}[tl]
        score += {"No":0,"Yes":2}[sq]
        score += {"Neutral":0,"Above 0.786":1,"Below 0.214":1}[htf_position]

    #━━━━━━━━ OPENING
    if mode == "Opening":

        if not prev_break:
            return "❌ REJECTED", ["No prior break"], 0, 0

        score += {
            ("Buy","Up"):3,
            ("Buy","Down"):2,
            ("Sell","Down"):3,
            ("Sell","Up"):2
        }.get((break_dir, gap_type), 0)

    #━━━━━━━━ RR
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = reward / risk if risk != 0 else 0

    if rr >= 2:
        score += 2
        reasons.append("✔ Good RR")
    elif rr >= 1.5:
        score += 1
        reasons.append("⚠ Moderate RR")
    else:
        reasons.append("❌ Poor RR")

    #━━━━━━━━ STRUCTURE
    structure_dist = abs(nearest_target - entry)

    if structure_dist < risk * 1.2:
        score -= 3
        reasons.append("❌ No room")
    elif structure_dist < risk * 1.8:
        score -= 1
        reasons.append("⚠ Tight")
    else:
        score += 1
        reasons.append("✔ Space")

    #━━━━━━━━ FINAL
    if score >= 7:
        decision = "🔥 STRONG"
    elif score >= 4:
        decision = "⚠ MODERATE"
    else:
        decision = "❌ WEAK"

    return decision, reasons, rr, score

#━━━━━━━━━━━━━━━━━━━
# EXECUTE (BUTTON BASED - STABLE)
#━━━━━━━━━━━━━━━━━━━
if st.button("🚀 Evaluate Trade", use_container_width=True):

    decision, reasons, rr, score = evaluate()

    st.markdown(f"## {decision}")
    st.write(f"Score: {score} | RR: {round(rr,2)}")

    for r in reasons:
        st.write(r)

    follow = st.radio("Follow?", ["Yes", "No"], horizontal=True)

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Decision": decision,
        "Score": score,
        "RR": rr,
        "Followed": follow
    }

    df = pd.DataFrame([log])

    try:
        old = pd.read_csv("log.csv")
        df = pd.concat([old, df])
    except:
        pass

    df.to_csv("log.csv", index=False)

    st.success("Trade saved!")

#━━━━━━━━━━━━━━━━━━━
# STATS
#━━━━━━━━━━━━━━━━━━━
st.subheader("📈 Stats")

try:
    log = pd.read_csv("log.csv")
    st.write("Total Trades:", len(log))
    st.write("Follow Rate:", round((log["Followed"] == "Yes").mean(), 2))
except:
    st.write("No data yet")