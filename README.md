# 📞 Intelligent Multilingual Contact Centre Engine

A proof-of-concept simulator for an AI-powered, emotion-aware, multilingual contact centre routing system — combining NLP-driven intent/sentiment analysis with a predictive agent-matching engine.

**🔗 Live demo:** [Streamlit Cloud link here once deployed]

---

## 🩺 The Problem

SBI's contact centre handles a massive volume of calls — but customers routinely face:
- Confusing DTMF keypad menus ("press 1 for this, press 2 for that")
- Language mismatches with available agents
- Long wait times leading to call abandonment
- Repeated calls to resolve a single issue (poor First-Call Resolution)

A primary survey of 65 real respondents (see `/data`) found **83% had abandoned a call** due to wait time or menu confusion, and **43% had faced language friction** when speaking to a representative — directly motivating this system's design.

## 💡 The Solution

This engine simulates an intelligent front-end for the contact centre that:
1. **Transcribes and translates** caller input in real time (mocked Bhashini AI pipeline)
2. **Classifies intent** across 9 service categories, including 5 new services added mid-project by the SBI mentor (Deceased Claim Facilitation, YONO Co-Browsing, Proactive Fraud Lock, Video Banking Advisory, Passive Voice Biometrics)
3. **Analyzes sentiment** to detect distress/urgency and trigger appropriate escalation
4. **Predictively routes** each call to the best-matched human agent using a weighted scoring formula, with a fallback/failsafe mechanism for edge cases

## 🏗️ Architecture

```
Customer Simulator (Streamlit UI)
        │
        ▼
Voice Biometric Auth (mocked) ──► Bhashini Translation (mocked, Google Translate-backed)
        │
        ▼
Intent Classification + Slot Filling
        │
        ▼
Sentiment Analysis (Hugging Face transformer + keyword safety-net override)
        │
        ▼
Predictive Routing Engine:  Score = w1·Skill + w2·Language − w3·Occupancy
        │
        ▼
Agent Warm-Handoff Interface (with Emotional Alert banners + Analog Escape Hatch failsafe)
```

Session state is tracked via Redis (with automatic in-memory fallback if Redis isn't reachable — this is expected behavior in the deployed cloud version).

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| Database | SQLite |
| NLP / Intent | Keyword-based classifier (LLM-classifier stand-in) |
| Translation | Google Translate (`deep-translator`), mocking Bhashini's ASR+NMT pipeline |
| Sentiment | Hugging Face Transformers (`tabularisai/multilingual-sentiment-analysis`) + rule-based fallback |
| Session Store | Redis, with in-memory fallback |
| Analytics | Faker (synthetic data generation), Matplotlib/Power BI (dashboards) |

## 📂 Repository Structure

```
├── app.py                      # Streamlit front-end, main entry point
├── nlp_engine.py                # Translation + intent + sentiment pipeline
├── optimizer.py                  # Predictive routing / agent-matching algorithm
├── database_setup.py             # SQLite schema + synthetic seed data
├── session_store.py              # Redis-backed session/state tracker
├── generate_analytics.py         # Synthetic 1,000-row operational log generator
├── requirements.txt
├── data/
│   └── sbi_operational_logs.csv  # Synthetic operational call log (1,000 rows)
├── testing/
│   └── sbi_test_transcripts.csv  # 25-case manual validation test set
└── docs/
    ├── architecture_diagram.png
    ├── sbi_survey_dashboard.png
    ├── sbi_operational_dashboard.png
    └── ui_screenshots/
```

## 🚀 Running Locally

```bash
git clone https://github.com/<your-username>/sbi-multilingual-contact-centre.git
cd sbi-multilingual-contact-centre
pip install -r requirements.txt
python database_setup.py      # seeds the SQLite database
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

## 📊 Results

Validated against a 1,000-row synthetic operational simulation comparing this system's "Conversational AI" channel against a Traditional IVR baseline:

- **First-Call Resolution:** 47.8% (Traditional IVR) → **78.9%** (this system)
- **Churn risk rate:** 13.6% → **3.3%**
- **Branch visits prevented:** 10.8% → **17.3%**

Manual validation against a 25-case test set spanning 6 languages and 9 intent categories showed strong accuracy on intent classification and routing, with sentiment analysis as the primary area for future refinement (see Limitations).

## ⚠️ Known Limitations

- **Translation reliability on romanized input:** The mocked translation layer (Google Translate, standing in for Bhashini) translates native-script text (Devanagari, etc.) reliably, but romanized regional-language text (Latin script, e.g. "Mujhe madad chahiye") is harder to auto-detect and may pass through untranslated. A keyword-based safety net partially compensates for this.
- **Sentiment model calibration:** The Hugging Face sentiment model occasionally misreads polite phrasing alongside genuine distress (e.g. "please lock everything, I'm scared") as positive. A high-confidence keyword override was added to catch these cases; broader fine-tuning on banking-domain text would improve this further.
- **Proof-of-concept scope:** Voice biometrics, Bhashini integration, and live telephony are simulated/mocked, not connected to production systems. Two-tier buffering and WebSocket streaming are represented conceptually.

## 🔮 Future Scope

- Replace mocked translation with Bhashini's actual ASR+NMT API
- Fine-tune sentiment model on banking/customer-service domain data
- Real-time WebSocket-based call streaming
- A/B testing framework for routing weight optimization

## 📄 License

This project was built as part of an SBI Summer Internship (2026) and is intended for academic/demonstration purposes.
