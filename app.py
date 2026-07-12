"""
app.py
------
Rapid-prototype front end (Streamlit) for the Intelligent, Emotion-Aware,
Multilingual Conversational Contact Center Engine.

Run with:
    streamlit run app.py
"""

import sqlite3
import time
from pathlib import Path

import streamlit as st

from nlp_engine import analyze_caller_input
from optimizer import (
    calculate_best_agent,
    score_agent,
    _get_agents,
    SCORE_THRESHOLD,
)
from session_store import set_session, append_sentiment, backend as session_backend

DB_PATH = Path(__file__).parent / "sbi_contact_centre.db"

LANGUAGES = [
    "Hindi", "English", "Bengali", "Marathi", "Tamil", "Telugu",
    "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia",
    "Konkani", "Dogri", "Nepali",
]
# Preset scenarios: dropdown to instantly load an example transcript for
# each service, so evaluators can see every intent (including the 4 new
# mentor-suggested services) without hand-typing test sentences.
SCENARIO_PRESETS = {
    "Fraud — card stolen": "I lost my wallet at the station and my bank details are gone, block everything!",
    "Loans — EMI query": "I need to know the interest rate and EMI schedule for my personal loan application.",
    "Balance Inquiry": "Can you tell me my current account balance please?",
    "Pension — payment delay": "My monthly pension has not arrived this month, please check.",
    "General": "I have a general question about my account services.",
    "🆕 Deceased Claim Facilitation": "My father passed away last month and I need to claim his account as legal heir. I have the death certificate ready.",
    "🆕 YONO Companion (Co-Browsing)": "I'm confused using the YONO app, can you guide me through UPI registration? I don't want to make a mistake.",
    "🆕 Proactive Fraud Lock (outbound)": "I got a call saying I made a transaction but I did not authorize this at all, please freeze my account now.",
    "🆕 Video Banking Advisory": "I want to speak to a specialist about home loan planning and mutual fund investment options.",
}

st.set_page_config(page_title="SBI Contact Centre Engine", layout="wide")

st.title("📞 Intelligent Multilingual Contact Centre Engine")
st.caption("Proof-of-Concept Simulator — NLP intent/sentiment + predictive routing")

# ---------------------------------------------------------------------
# Sidebar: routing weight controls (bank-configurable per the brief)
# ---------------------------------------------------------------------
st.sidebar.header("Routing Weights (w1 + w2 + w3 = 1.0)")
w1 = st.sidebar.slider("w1 — Skill Match", 0.0, 1.0, 0.4, 0.05)
w2 = st.sidebar.slider("w2 — Language Match", 0.0, 1.0, 0.4, 0.05)
w3 = st.sidebar.slider("w3 — Occupancy Penalty", 0.0, 1.0, 0.2, 0.05)
weight_sum = round(w1 + w2 + w3, 2)
if weight_sum != 1.0:
    st.sidebar.warning(f"Weights sum to {weight_sum}, brief requires 1.0")
weights = {"w1": w1, "w2": w2, "w3": w3}

st.sidebar.divider()
st.sidebar.metric("SLA Failsafe", "80 seconds")
st.sidebar.metric("Optimal Score Threshold", f"{SCORE_THRESHOLD}")
st.sidebar.metric("Session Store Backend", session_backend().upper())
if session_backend() == "in_memory":
    st.sidebar.caption("⚠️ Redis not reachable — using in-memory fallback")
else:
    st.sidebar.caption("✅ Redis session cache active")

# ---------------------------------------------------------------------
# Panel 1: Customer Simulator Panel
# ---------------------------------------------------------------------
st.header("1. Customer Simulator Panel")

scenario = st.selectbox("Quick scenario preset", list(SCENARIO_PRESETS.keys()))
if st.session_state.get("last_scenario") != scenario:
    st.session_state["transcript_text"] = SCENARIO_PRESETS[scenario]
    st.session_state["last_scenario"] = scenario

col1, col2 = st.columns([3, 1])
with col1:
    transcript = st.text_area(
        "Call transcript (editable)",
        key="transcript_text",
        height=100,
    )
with col2:
    language = st.selectbox("Native language", LANGUAGES, index=0)

initiate = st.button("🎙️ Initiate Call", type="primary")

# ---------------------------------------------------------------------
# Panel 2: Execution Logging Stream
# ---------------------------------------------------------------------
if initiate:
    st.header("2. Execution Logging Stream")
    log = st.container(border=True)

    # Pick the "caller" once per call, used throughout (auth + handoff)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    customer = conn.execute(
    "SELECT * FROM Customers WHERE native_language = ? ORDER BY RANDOM() LIMIT 1",
    (language,)
    ).fetchone()
    if customer is None:
        customer = conn.execute("SELECT * FROM Customers ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()

    with log:
        # --- Service 2: Passive Voice Biometrics (Passwordless Auth) ----
        step0 = st.empty()
        step0.info("⏳ Step 0/4 — Passive voice biometric authentication...")
        time.sleep(0.2)
        if customer["voiceprint_enrolled"]:
            step0.success(
                f"🔐 Voice Biometric: **Verified in 2.3s** — {customer['name']}'s "
                f"voiceprint matched (100+ features, deepfake liveness check passed). "
                f"No password/PIN required."
            )
        else:
            step0.warning(
                f"🔐 Voice Biometric: {customer['name']} is **not enrolled** — "
                f"falling back to standard KBA (Knowledge-Based Authentication) questions."
            )

        step1 = st.empty()
        step1.info("⏳ Step 1/4 — Bhashini translation...")
        time.sleep(0.3)
        nlp_result = analyze_caller_input(transcript, language)
        step1.success(f"✅ Bhashini Translation: \u201c{nlp_result['translated_text']}\u201d")

        step2 = st.empty()
        step2.info("⏳ Step 2/4 — Intent & slot extraction...")
        time.sleep(0.2)
        step2.success(
            f"✅ Intent: **{nlp_result['intent']}**  |  Slots: {nlp_result['slots'] or '—'}"
        )

        step3 = st.empty()
        step3.info("⏳ Step 3/4 — Sentiment inference...")
        time.sleep(0.2)
        sentiment_color = "🔴" if nlp_result["emotional_index"] < -0.3 else (
            "🟡" if nlp_result["emotional_index"] < 0.3 else "🟢"
        )
        step3.success(
            f"{sentiment_color} Sentiment: **{nlp_result['sentiment_label']}** "
            f"(score={nlp_result['sentiment_score']}, "
            f"emotional index={nlp_result['emotional_index']}, "
            f"engine={nlp_result['engine_used']})"
        )

        # --- Session Memory & State Tracker (Redis-backed) --------------
        call_id = f"call-{int(time.time() * 1000)}"
        set_session(call_id, {
            "language": language,
            "intent": nlp_result["intent"],
            "translated_text": nlp_result["translated_text"],
            "sentiment_history": [],
        })
        sentiment_history = append_sentiment(call_id, nlp_result["emotional_index"])
        st.caption(
            f"🗄️ Session `{call_id}` written to **{session_backend()}** "
            f"— rolling sentiment history: {sentiment_history}"
        )

        step4 = st.empty()
        step4.info("⏳ Step 4/4 — Predictive routing scores...")
        time.sleep(0.2)

        conn = sqlite3.connect(DB_PATH)
        agents = _get_agents(conn)
        conn.close()

        scored_rows = []
        for agent in agents:
            s = score_agent(agent, nlp_result["intent"], language, weights)
            scored_rows.append({
                "Agent": agent["name"],
                "Specialties": agent["specialties"],
                "Languages": agent["languages"],
                "Workload": agent["workload_score"],
                "Score": round(s, 3),
            })
        scored_rows.sort(key=lambda r: r["Score"], reverse=True)
        step4.success("✅ Routing scores calculated for all agents")
        st.dataframe(scored_rows, width="stretch", hide_index=True)

    # -------------------------------------------------------------
    # Panel 3: Agent Warm-Handoff Interface
    # -------------------------------------------------------------
    st.header("3. Agent Warm-Handoff Interface")

    routing_result = calculate_best_agent(nlp_result["intent"], language, weights)

    with st.container(border=True):
        st.subheader(f"🖥️ Agent Terminal — {routing_result.agent_name}")
        if routing_result.used_fallback:
            st.warning(f"⚠️ Fallback routing triggered: {routing_result.reason}")
        else:
            st.info(routing_result.reason)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Customer Profile**")
            st.write(f"Name: {customer['name']}")
            st.write(f"Age: {customer['age']}")
            st.write(f"Balance: ₹{customer['balance']:,.2f}")
            st.write(f"Native language: {customer['native_language']}")

        with c2:
            st.markdown("**System Synthesis**")
            st.write(f"Extracted Intent: **{nlp_result['intent']}**")
            st.write(f"Transcribed Text: \u201c{nlp_result['translated_text']}\u201d")
            st.write(f"Matched Agent Score: **{routing_result.score}**")

        if nlp_result["emotional_index"] <= -0.6:
            st.error(
                f"🚨 **Emotional Alert:** Attention — customer is highly panicked "
                f"(Sentiment Score: {nlp_result['emotional_index']}). "
                f"Handle with extreme care and skip repetitive verification steps."
            )
        elif nlp_result["emotional_index"] <= -0.2:
            st.warning(
                f"⚠️ **Emotional Alert:** Customer sentiment is negative "
                f"(Sentiment Score: {nlp_result['emotional_index']}). Prioritize empathy."
            )

    # -------------------------------------------------------------
    # Service-specific panels (new mentor-suggested services)
    # -------------------------------------------------------------
    intent = nlp_result["intent"]

    if intent == "Deceased Claim Facilitation":
        st.subheader("🕊️ Compassionate Care Queue — Green Channel Facilitation")
        with st.container(border=True):
            st.write("Dedicated compassionate-care queue bypassed standard hold routing.")
            st.checkbox("Death certificate uploaded & OCR-verified", value=True, disabled=True)
            st.checkbox("Survivor KYC documents uploaded & verified", value=True, disabled=True)
            st.checkbox("Claim form digitally signed", value=False, disabled=True)
            st.success("🎫 Green Channel Fast-Track Token issued: **GCT-2026-00417** — "
                       "family visits the branch exactly once to sign the final ledger.")

    elif intent == "YONO Companion (Co-Browsing)":
        st.subheader("🖱️ YONO Companion — Secure Co-Browsing Session")
        with st.container(border=True):
            st.write("Agent view (DOM-captured — CVV, PIN, and balance fields auto-masked):")
            c1, c2, c3 = st.columns(3)
            c1.metric("Account Balance", "•••••• (masked)")
            c2.metric("CVV", "••• (masked)")
            c3.metric("UPI PIN", "•••• (masked)")
            st.info("🔴 Agent highlighted: \"See that blue button I highlighted? "
                    "Tap that to complete your UPI registration.\"")

    elif intent == "Proactive Fraud Lock":
        st.subheader("🚨 Proactive AI Fraud Callback")
        with st.container(border=True):
            st.write("**Outbound voicebot:** \"Hello, we noticed a payment of ₹10,000 "
                     "to an unknown merchant. Did you authorize this?\"")
            st.write(f"**Customer:** \u201c{nlp_result['translated_text']}\u201d")
            st.error("🔒 Real-time account freeze triggered via API gateway. "
                     "Dispute ticket drafted automatically.")

    elif intent == "Video Banking Advisory":
        st.subheader("🎥 Virtual Specialist Branch Room")
        with st.container(border=True):
            st.write("Predictive routing engine paired this customer with a "
                     f"specialized floating advisor: **{routing_result.agent_name}**")
            st.success("📅 Video consultation slot booked: Today, 4:30 PM — "
                       "Wealth Advisory & Mutual Fund Planning")

    # -------------------------------------------------------------
    # Analog escape hatch — production failsafe from the brief
    # -------------------------------------------------------------
    if routing_result.used_fallback and nlp_result["emotional_index"] <= -0.6:
        st.divider()
        st.error(
            "📵 **Analog Escape Hatch triggered:** \u201cWe are experiencing a "
            "connection delay. We have logged your request. You can also text "
            "'UNHAPPY' to 8008 20 20 20 to receive an immediate callback from a manager.\u201d"
        )

st.divider()
st.caption(
    "Proof-of-Concept Simulator · Two-tier buffering, Redis session store, and "
    "live WebSocket streaming are represented conceptually in this rapid-"
    "prototype build."
)