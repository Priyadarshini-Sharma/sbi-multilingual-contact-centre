"""
generate_analytics.py
----------------------
Generates sbi_operational_logs.csv — 1,000 synthetic call history records
calibrated with real-world patterns for Power BI dashboarding:

  - Elderly customers (age > 60) get higher wait times and lower FCR on
    the traditional system, improving markedly on the conversational
    regional-language interface.
  - Churn correlates with wait_time > 90s AND fcr_status == False.

Run with:
    python generate_analytics.py
"""

import random
import csv
from pathlib import Path
from faker import Faker

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)

N_ROWS = 1000
OUTPUT_PATH = Path(__file__).parent / "sbi_operational_logs.csv"

REGIONS = ["North", "South", "East", "West", "Central", "North-East"]
INTENTS = [
    "Fraud", "Loans", "Balance Inquiry", "Pension", "General",
    "Deceased Claim Facilitation", "YONO Companion (Co-Browsing)",
    "Proactive Fraud Lock", "Video Banking Advisory",
]
# Which of the new services actually prevent a physical branch visit
# (per the mentor's brief, part C) — used to calibrate Branch_Visits_Prevented
BRANCH_DEFLECTING_INTENTS = {"YONO Companion (Co-Browsing)", "Deceased Claim Facilitation"}
CHANNELS = ["Conversational AI (Regional)", "Traditional IVR (DTMF)"]
AGE_GROUPS = [(18, 30), (31, 45), (46, 60), (61, 75), (76, 95)]


def sample_age():
    group = random.choice(AGE_GROUPS)
    return random.randint(*group)


def age_group_label(age):
    if age <= 30:
        return "18-30"
    if age <= 45:
        return "31-45"
    if age <= 60:
        return "46-60"
    if age <= 75:
        return "61-75"
    return "76+"


def generate_row(row_id):
    age = sample_age()
    is_elderly = age > 60
    channel = random.choice(CHANNELS)
    region = random.choice(REGIONS)
    intent = random.choice(INTENTS)

    # --- Wait time modeling -------------------------------------------------
    base_wait = random.gauss(45, 20)  # seconds
    if is_elderly:
        base_wait += 25  # elderly struggle more, especially on IVR
    if channel == "Traditional IVR (DTMF)":
        base_wait += 20
    else:
        # conversational regional interface reduces wait notably for elderly
        if is_elderly:
            base_wait -= 30
    wait_time = max(5, round(base_wait))

    # --- Handle time ---------------------------------------------------------
    aht = max(20, round(random.gauss(180, 60)))

    # --- Sentiment -------------------------------------------------------
    initial_sentiment = round(random.uniform(-1.0, 0.3), 2)
    sentiment_recovery = random.uniform(0.1, 1.2)
    if wait_time > 90:
        sentiment_recovery *= 0.3  # long waits erode the recovery
    final_sentiment = round(max(-1.0, min(1.0, initial_sentiment + sentiment_recovery)), 2)

    # --- FCR modeling ------------------------------------------------------
    fcr_prob = 0.75
    if channel == "Traditional IVR (DTMF)":
        fcr_prob -= 0.15
    if is_elderly and channel == "Traditional IVR (DTMF)":
        fcr_prob -= 0.20
    if is_elderly and channel != "Traditional IVR (DTMF)":
        fcr_prob += 0.10
    if wait_time > 90:
        fcr_prob -= 0.25
    fcr_prob = max(0.05, min(0.97, fcr_prob))
    fcr_status = random.random() < fcr_prob

    # --- Churn modeling (correlated: wait > 90s AND not FCR) ----------------
    churn = (wait_time > 90 and not fcr_status and random.random() < 0.65) or (
        random.random() < 0.03  # small baseline churn noise
    )

    # --- Branch visits prevented (mentor brief, part C) ---------------------
    # Only counts when the query actually resolved (fcr_status) under one of
    # the two branch-deflecting new services; ~90% of those resolved cases
    # genuinely skip a branch visit (some customers still choose to visit anyway).
    branch_visit_prevented = (
        intent in BRANCH_DEFLECTING_INTENTS and fcr_status and random.random() < 0.9
    )

    return {
        "call_id": row_id,
        "customer_name": fake.name(),
        "age": age,
        "age_group": age_group_label(age),
        "region": region,
        "channel": channel,
        "intent": intent,
        "wait_time_seconds": wait_time,
        "avg_handle_time_seconds": aht,
        "initial_sentiment": initial_sentiment,
        "final_sentiment": final_sentiment,
        "fcr_status": fcr_status,
        "churned": churn,
        "branch_visit_prevented": branch_visit_prevented,
    }


def main():
    rows = [generate_row(i + 1) for i in range(N_ROWS)]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    fcr_rate = sum(r["fcr_status"] for r in rows) / len(rows)
    churn_rate = sum(r["churned"] for r in rows) / len(rows)
    elderly_ivr_fcr = [
        r["fcr_status"] for r in rows
        if r["age"] > 60 and r["channel"] == "Traditional IVR (DTMF)"
    ]
    elderly_ai_fcr = [
        r["fcr_status"] for r in rows
        if r["age"] > 60 and r["channel"] != "Traditional IVR (DTMF)"
    ]

    print(f"Generated {len(rows)} rows -> {OUTPUT_PATH}")
    print(f"Overall FCR rate:   {fcr_rate:.1%}")
    print(f"Overall churn rate: {churn_rate:.1%}")
    if elderly_ivr_fcr:
        print(f"Elderly FCR on Traditional IVR:      {sum(elderly_ivr_fcr)/len(elderly_ivr_fcr):.1%}  (n={len(elderly_ivr_fcr)})")
    if elderly_ai_fcr:
        print(f"Elderly FCR on Conversational AI:     {sum(elderly_ai_fcr)/len(elderly_ai_fcr):.1%}  (n={len(elderly_ai_fcr)})")

    n_deflected = sum(r["branch_visit_prevented"] for r in rows)
    n_deflecting_calls = sum(1 for r in rows if r["intent"] in BRANCH_DEFLECTING_INTENTS)
    print(f"\nBranch Visits Prevented: {n_deflected} out of {len(rows)} total calls "
          f"({n_deflected/len(rows):.1%} of ALL calls)")
    if n_deflecting_calls:
        print(f"  Within YONO/Deceased-Claim calls specifically: "
              f"{n_deflected/n_deflecting_calls:.1%} resulted in a prevented branch visit "
              f"(n={n_deflecting_calls} such calls)")


if __name__ == "__main__":
    main()