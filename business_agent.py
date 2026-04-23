from dotenv import load_dotenv
load_dotenv()

"""
business_agent.py
-----------------
The BUSINESS AGENT of the customer-behavior-crew.

Strict lane: this agent ONLY interprets and recommends. It never
queries the database, never writes files, never calls other agents.
It answers one question: "What does this data mean, and what should
we do about it?"

The Data Agent hands this agent a printout of numbers.
The Business Agent is the strategist who reads the printout,
spots the patterns, and tells the team what to do next.

This strict separation is what makes the crew extensible:
swap out the Business Agent's reasoning model, change its
persona, or add a second Business Agent with a different lens —
none of that touches the Data Agent or the Orchestrator.
"""

import os
import json
import requests
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"
MAX_TOKENS        = 2000

SYSTEM_PROMPT = """You are a senior customer success strategist for an e-commerce business.

You will be given raw customer behavior data collected from a Databricks lakehouse.
Your job is to interpret this data and produce actionable business recommendations.

You think in terms of:
- Customer lifetime value and spend concentration risk
- Churn signals — recency, frequency, and spend trajectory
- Segment health — are the right segments growing?
- Geographic opportunities and risks
- Immediate actions vs longer-term strategic moves

You are direct, specific, and commercial. You reference actual numbers.
You never say "it depends" without saying what it depends on.
You prioritize recommendations by business impact, not by ease of implementation.

When you spot a pattern, you name it clearly:
- "Your top 10% of customers generate X% of revenue — that's concentration risk."
- "Customers inactive for 90+ days represent $X in recoverable revenue."
- "The New segment is your largest but lowest-spend — that's a conversion problem."

Respond in this JSON format only:
{
  "health_score": <1-10, overall customer base health>,
  "key_findings": [
    {
      "finding": "specific observation with actual numbers",
      "implication": "what this means for the business",
      "severity": "HIGH | MEDIUM | LOW"
    }
  ],
  "segment_insights": [
    {
      "segment": "segment name",
      "assessment": "health assessment with numbers",
      "recommended_action": "specific action for this segment"
    }
  ],
  "immediate_actions": [
    "top 3 things to do this week, in priority order"
  ],
  "strategic_recommendations": [
    "longer-term recommendations (30-90 days)"
  ],
  "churn_risk_summary": "assessment of churn risk with specific customer counts or revenue at risk",
  "growth_opportunity": "the single biggest untapped opportunity in this customer data"
}

Return JSON only — no preamble, no markdown fences."""


# ---------------------------------------------------------------------------
# Claude API helper
# ---------------------------------------------------------------------------

def _call_claude(messages: list) -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":          ANTHROPIC_API_KEY,
            "anthropic-version":  "2023-06-01",
            "content-type":       "application/json",
        },
        json={
            "model":      CLAUDE_MODEL,
            "max_tokens": MAX_TOKENS,
            "system":     SYSTEM_PROMPT,
            "messages":   messages,
        },
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


# ---------------------------------------------------------------------------
# Core interpretation method
# ---------------------------------------------------------------------------

def interpret(data: dict, question_context: str = "") -> dict:
    """
    Interpret customer behavior data and produce business recommendations.

    data: the payload returned by data_agent.collect()
    question_context: the original business question from the Orchestrator
    """
    print("   [Business Agent] Interpreting customer signals...")

    question_note = ""
    if question_context:
        question_note = f"\nThe business question being answered is: '{question_context}'\nFocus your interpretation on answering this question specifically.\n"

    user_message = f"""Here is the raw customer behavior data from our Databricks lakehouse:

{question_note}
--- SEGMENT DISTRIBUTION ---
{json.dumps(data.get('segment_distribution', []), indent=2)}

--- TOP 10 CUSTOMERS BY SPEND ---
{json.dumps(data.get('top_customers', []), indent=2)}

--- COUNTRY DISTRIBUTION ---
{json.dumps(data.get('country_distribution', []), indent=2)}

--- RECENCY SIGNALS ---
{json.dumps(data.get('recency_signals', {}), indent=2)}

--- SPEND DISTRIBUTION (percentiles) ---
{json.dumps(data.get('spend_distribution', {}), indent=2)}

Interpret this data and provide actionable business recommendations."""

    messages      = [{"role": "user", "content": user_message}]
    response_text = _call_claude(messages)

    try:
        clean  = response_text.strip().replace("```json", "").replace("```", "")
        result = json.loads(clean)
    except json.JSONDecodeError:
        print("   [Business Agent] Warning: Could not parse response as JSON.")
        result = {"raw_response": response_text}

    result["interpreted_at"] = datetime.now(timezone.utc).isoformat()
    result["question_context"] = question_context

    print(f"   [Business Agent] Done. Health score: {result.get('health_score', 'N/A')}/10. "
          f"{len(result.get('key_findings', []))} findings, "
          f"{len(result.get('immediate_actions', []))} immediate actions.")

    return result


# ---------------------------------------------------------------------------
# Agent interface — standard contract for agent_registry.py
# ---------------------------------------------------------------------------

AGENT_NAME        = "business_agent"
AGENT_DESCRIPTION = (
    "Interprets raw customer behavior metrics and produces actionable business "
    "recommendations. Covers segment health, churn risk, spend concentration, "
    "geographic opportunities, and growth strategies. Returns analysis only — "
    "never queries the database directly."
)

def run(data: dict, question_context: str = "") -> dict:
    """Standard entry point called by the Orchestrator."""
    return interpret(data, question_context)


if __name__ == "__main__":
    from data_agent import collect
    print("Testing Business Agent standalone...\n")
    print("Step 1: Collecting data via Data Agent...")
    data   = collect("standalone business agent test")
    print("\nStep 2: Interpreting via Business Agent...")
    result = interpret(data, "Who are our most at-risk customers?")
    print("\n--- BUSINESS AGENT OUTPUT ---")
    print(json.dumps(result, indent=2, default=str))
