"""
optimizer.py
------------
Predictive Matchmaking Core Algorithm.

Score_ij = w1*S_ij + w2*L_ij - w3*O_j

  S_ij  Skill Match      [0,1]  agent specialty vs. call intent
  L_ij  Language Match   {0,1}  agent certified languages vs. detected language
  O_j   Occupancy Rate   [0,1]  agent's current workload (penalty)
  w1,w2,w3  configurable weights, w1+w2+w3 = 1.0

Includes:
  - calculate_best_agent(): core matchmaker
  - Expanding-circle queue fallback (lowers threshold every 15s)
  - 80-second SLA failsafe -> dumps to next available general agent

Run standalone to sanity check against the seeded DB:
    python optimizer.py
"""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).parent / "sbi_contact_centre.db"

# Map call intent -> required agent specialty for skill scoring
_INTENT_TO_SPECIALTY = {
    "Fraud": "Fraud",
    "Loans": "Loans",
    "Balance Inquiry": "General",
    "Pension": "General",
    "General": "General",
    # --- New services ---
    "Deceased Claim Facilitation": "Deceased Claims",
    "Proactive Fraud Lock": "Fraud",
    "YONO Companion (Co-Browsing)": "YONO Tech",
    "Video Banking Advisory": "Video Advisory",
}

DEFAULT_WEIGHTS = {"w1": 0.4, "w2": 0.4, "w3": 0.2}  # skill, language, -occupancy
SCORE_THRESHOLD = 0.75          # optimal-match target per brief
FALLBACK_MIN_SCORE = 0.5        # below this -> fallback routing logic
SLA_TIMEOUT_SECONDS = 80        # hard failsafe from the brief
EXPANDING_CIRCLE_STEP_SECONDS = 15


@dataclass
class RoutingResult:
    agent_id: int | None
    agent_name: str | None
    score: float
    used_fallback: bool
    reason: str


def _get_agents(conn) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    return cur.execute("SELECT * FROM Agents").fetchall()


def _skill_match(agent_specialties: str, intent: str) -> float:
    """S_ij: 1.0 if the agent holds the required specialty (agents can now
    hold multiple, comma-separated), 0.5 if agent is a General-purpose
    fallback, 0.1 otherwise."""
    required_specialty = _INTENT_TO_SPECIALTY.get(intent, "General")
    specialty_list = [s.strip() for s in agent_specialties.split(",")]
    if required_specialty in specialty_list:
        return 1.0
    if "General" in specialty_list:
        return 0.5
    return 0.1


def _language_match(agent_languages: str, detected_language: str) -> float:
    """L_ij: binary language compatibility."""
    langs = [l.strip().lower() for l in agent_languages.split(",")]
    return 1.0 if detected_language.strip().lower() in langs else 0.0


def score_agent(agent_row, intent: str, detected_language: str,
                 weights: dict = DEFAULT_WEIGHTS) -> float:
    s = _skill_match(agent_row["specialties"], intent)
    l = _language_match(agent_row["languages"], detected_language)
    o = agent_row["workload_score"]
    return weights["w1"] * s + weights["w2"] * l - weights["w3"] * o


def calculate_best_agent(
    extracted_intent: str,
    language_detected: str,
    weights: dict = DEFAULT_WEIGHTS,
    db_path: Path = DB_PATH,
    elapsed_seconds: int = 0,
) -> RoutingResult:
    """Core matchmaker: queries all agents, scores each, returns the best match.

    Applies the brief's fallback rule: if the best score is below
    FALLBACK_MIN_SCORE (0.5, typically due to no language match),
    fallback routing is triggered (here: route to lowest-workload
    General agent as the "next available general agent").

    elapsed_seconds feeds the Expanding-Circle queue (Section 4.3): the
    longer a call has been waiting, the more lenient the "optimal match"
    threshold becomes, per current_expanding_circle_threshold().
    """
    conn = sqlite3.connect(db_path)
    agents = _get_agents(conn)
    conn.close()

    if not agents:
        return RoutingResult(None, None, 0.0, True, "No agents available in DB")

    scored = [
        (agent, score_agent(agent, extracted_intent, language_detected, weights))
        for agent in agents
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best_agent, best_score = scored[0]

    active_threshold = current_expanding_circle_threshold(elapsed_seconds)

    if best_score >= FALLBACK_MIN_SCORE:
        return RoutingResult(
            agent_id=best_agent["agent_id"],
            agent_name=best_agent["name"],
            score=round(best_score, 3),
            used_fallback=False,
            reason=f"Optimal match found (active threshold at t={elapsed_seconds}s: {active_threshold})"
                   if best_score >= active_threshold
                   else "Best available match (below optimal threshold)",
        )

    # Fallback: even below the confidence threshold, route to whichever
    # agent scored highest overall (preserves partial skill/language
    # credit) rather than discarding scores and picking by workload alone.
    return RoutingResult(
        agent_id=best_agent["agent_id"],
        agent_name=best_agent["name"],
        score=round(best_score, 3),
        used_fallback=True,
        reason="Below optimal-match threshold — routed to best available agent",
    )


def expanding_circle_wait_time_to_threshold(initial_threshold: float = SCORE_THRESHOLD,
                                             floor: float = FALLBACK_MIN_SCORE,
                                             step: float = 0.05) -> list[tuple[int, float]]:
    """Simulates the 'Expanding Circle' routine: every 15s, lower the
    acceptance threshold slightly, until the 80s SLA failsafe fires.
    Returns a list of (elapsed_seconds, threshold) checkpoints for UI display.
    """
    checkpoints = []
    t = 0
    threshold = initial_threshold
    while t <= SLA_TIMEOUT_SECONDS:
        checkpoints.append((t, round(threshold, 2)))
        t += EXPANDING_CIRCLE_STEP_SECONDS
        threshold = max(floor, threshold - step)
    return checkpoints


def current_expanding_circle_threshold(elapsed_seconds: int) -> float:
    """Given how long this call has been waiting for a match, returns the
    acceptance threshold that applies right now. This is what actually wires
    the expanding-circle timeline into a live routing decision, instead of
    it only existing as a standalone illustration (see calculate_best_agent).
    """
    checkpoints = expanding_circle_wait_time_to_threshold()
    active_threshold = SCORE_THRESHOLD
    for elapsed, threshold in checkpoints:
        if elapsed_seconds >= elapsed:
            active_threshold = threshold
    return active_threshold


if __name__ == "__main__":
    test_cases = [
        ("Fraud", "Marathi"),
        ("Loans", "Tamil"),
        ("Balance Inquiry", "Konkani"),   # no agent knows Konkani -> fallback
        ("Pension", "Bengali"),
        ("Deceased Claim Facilitation", "Hindi"),
        ("YONO Companion (Co-Browsing)", "Malayalam"),
        ("Proactive Fraud Lock", "English"),
        ("Video Banking Advisory", "Odia"),
    ]
    for intent, lang in test_cases:
        result = calculate_best_agent(intent, lang)
        print(f"Intent={intent:16s} Lang={lang:10s} -> "
              f"Agent={result.agent_name} (id={result.agent_id}) "
              f"score={result.score} fallback={result.used_fallback} "
              f"[{result.reason}]")

    print("\nExpanding-circle timeline (threshold decay to SLA failsafe):")
    for secs, thresh in expanding_circle_wait_time_to_threshold():
        print(f"  t={secs:3d}s  threshold={thresh}")
