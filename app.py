import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Trading Copilot", layout="centered")

st.title("📱 Trading Copilot (Stable + Debug)")

#━━━━━━━━━━━━━━━━━━━
# INPUTS
#━━━━━━━━━━━━━━━━━━━
tsl_flip = st.checkbox("🔁 TSL Flip (Required for Range/Breakout only)")
mode = st.radio("Mode", ["Range", "Breakout", "Opening"], horizontal=True)

# Range
if mode == "Range":
    st.subheader("Range Setup")
    cons = st.selectbox("Consolidation", ["No","Yes","1T","2T","3T"])
    bb = st.selectbox("Bollinger", ["No","Yes"])
    retr = st.selectbox("Retracement", ["No","0.6","0.78"])

# Breakout
if mode == "Breakout":
    st.subheader("Breakout Setup")
    tl = st.selectbox("Trendline Break", ["No","Yes"])
    sq = st.selectbox("Squeeze", ["No","Yes"])
    htf_position = st.selectbox("HTF Position", ["Neutral","Above 0.786","Below 0.214"])

# Opening
if mode == "Opening":
    st.subheader("Opening Setup")
    prev_break = st.checkbox("Prev Day Trendline Break")
    break_dir = st.radio("Break Direction", ["Buy","Sell"], horizontal=True)
    gap_type = st.radio("Gap Type", ["Up","Down","None"], horizontal=True)

# Trade
st.subheader("Trade Levels")
entry = st.number_input("Entry", value=0.0)
stop = st.number_input("Stop Loss", value=0.0)
target = st.number_input("Final Target", value=0.0)
nearest_target = st.number_input("Nearest Structure Target", value=0.0)
view = st.text_area("Your View (optional)")

#━━━━━━━━━━━━━━━━━━━
# 🔍 DEBUG PANEL
#━━━━━━━━━━━━━━━━━━━
st.markdown("### 🔍 Debug Inputs")

if mode == "Range":
    st.write({
        "TSL": tsl_flip,
        "Cons (raw)": repr(cons),
        "BB (raw)": repr(bb),
        "Retr (raw)": repr(retr)
    })

elif mode == "Breakout":
    st.write({
        "TSL": tsl_flip,
        "TL (raw)": repr(tl),
        "SQ (raw)": repr(sq),
        "HTF (raw)": repr(htf_position)
    })

else:
    st.write({
        "Prev Break": prev_break,
        "Dir (raw)": repr(break_dir),
        "Gap (raw)": repr(gap_type)
    })

#━━━━━━━━━━━━━━━━━━━
# EVALUATION
#━━━━━━━━━━━━━━━━━━━
def evaluate():

    score = 0
    reasons = []

    # Normalize (defensive)
    def norm(v):
        return v.strip().upper() if isinstance(v, str) else v

    # TSL filter
    if mode in ["Range","Breakout"]:
        if not tsl_flip:
            return "❌ REJECTED", ["No TSL Flip"], 0, 0
        reasons.append("✔ TSL Flip")

    if mode == "Opening":
        reasons.append("✔ Opening Mode")

    #━━━━━━━━ RANGE
    if mode == "Range":
        c = norm(cons)
        b = norm(bb)
        r = norm(retr)

        score += {"NO":0,"YES":1,"1T":1,"2T":2,"3T":3}.get(c, -999)
        score += {"NO":0,"YES":1}.get(b, -999)
        score += {"NO":0,"0.6":1,"0.78":2}.get(r, -999)

    #━━━━━━━━ BREAKOUT
    if mode == "Breakout":
        t = norm(tl)
        s = norm(sq)
        h = norm(htf_position)

        score += {"NO":0,"YES":2}.get(t, -999)
        score += {"NO":0,"YES":2}.get(s, -999)
        score += {"NEUTRAL":0,"ABOVE 0.786":1,"BELOW 0.214":1}.get(h, -999)

    #━━━━━━━━ OPENING
    if mode == "Opening":
        if not prev_break:
            return "❌ REJECTED", ["No prior break"], 0, 0

        d = norm(break_dir)
        g = norm(gap_type)

        score += {
            ("BUY","UP"):3,
            ("BUY","DOWN"):2,
            ("SELL","DOWN"):3,
            ("SELL","UP"):2
        }.get((d, g), -999)

    # Mapping error detection
    if score < -100:
        return "❌ ERROR", ["Mapping mismatch detected"], 0, score

    # RR
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

    # Structure
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

    # Final
    if score >= 7:
        decision = "🔥 STRONG"
    elif score >= 4:
        decision = "⚠ MODERATE"
    else:
        decision = "❌ WEAK"

    return decision, reasons, rr, score

#━━━━━━━━━━━━━━━━━━━
# EXECUTE
#━━━━━━━━━━━━━━━━━━━
if st.button("🚀 Evaluate Trade", use_container_width=True):

    decision, reasons, rr, score = evaluate()

    st.markdown(f"## {decision}")
    st.write(f"Score: {score} | RR: {round(rr,2)}")

    for r in reasons:
        st.write(r)

    log = {
        "Time": datetime.now(),
        "Mode": mode,
        "Decision": decision,
        "Score": score,
        "RR": rr
    }

    df = pd.DataFrame([log])

    try:
        old = pd.read_csv("log.csv")
        df = pd.concat([old, df])
    except:
        pass

    df.to_csv("log.csv", index=False)

    st.success("Saved!")