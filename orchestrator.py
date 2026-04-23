from dotenv import load_dotenv
load_dotenv()

"""
orchestrator.py
---------------
The ORCHESTRATOR of the customer-behavior-crew.

The Orchestrator is the partner in the consulting firm analogy.
It never touches the database. It never interprets data directly.
Its entire job is:
  1. Understand the business question
  2. Plan which agents to invoke and in what order
  3. Coordinate execution respecting agent dependencies
  4. Synthesize specialist outputs into one coherent answer

This separation is what makes the crew pattern powerful:
  - The Orchestrator is question-smart but data-blind
  - The Data Agent is data-smart but question-blind
  - The Business Agent is interpretation-smart but query-blind

Together they produce something none could produce alone.

The routing decision — which agents to call — is made by Claude,
not by hardcoded if/else logic. Claude reads the agent registry
descriptions and decides which specialists the question needs.
"""

import os
import json
import requests
from datetime import datetime, timezone

from agent_registry import get_agents, run_agent, list_agents_for_prompt

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"
MAX_TOKENS        = 1000


# ---------------------------------------------------------------------------
# Claude API helper
# ---------------------------------------------------------------------------

def _call_claude(messages: list, system: str) -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      CLAUDE_MODEL,
            "max_tokens": MAX_TOKENS,
            "system":     system,
            "messages":   messages,
        },
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


# ---------------------------------------------------------------------------
# Turn 1 — Plan: which agents does this question need?
# ---------------------------------------------------------------------------

def turn1_plan(question: str) -> tuple:
    """
    Feed the business question and agent registry to Claude.
    Claude decides which agents to invoke and in what order.
    Returns the plan and conversation history.
    """
    print("\n   [Orchestrator] Turn 1 — Planning agent routing...")

    agent_list = list_agents_for_prompt()

    system = """You are the orchestrator of a multi-agent AI crew for customer behavior analysis.

Your job is to read a business question and decide which specialist agents to invoke.

Available agents:
{agents}

Rules:
- Always invoke data_agent first if any data is needed (it has no dependencies)
- Invoke business_agent when interpretation or recommendations are needed
- Most customer behavior questions need both agents
- If a question is purely definitional (e.g. "what is churn?"), no agents needed

Respond in this JSON format only:
{{
  "agents_needed": ["data_agent", "business_agent"],
  "routing_reasoning": "one sentence explaining why these agents were selected",
  "question_focus": "what specific aspect of the question each agent should focus on"
}}

Return JSON only — no preamble, no markdown fences.""".format(agents=agent_list)

    messages = [{"role": "user", "content": f"Business question: {question}"}]
    response = _call_claude(messages, system)
    messages.append({"role": "assistant", "content": response})

    try:
        clean = response.strip().replace("```json", "").replace("```", "")
        plan  = json.loads(clean)
    except json.JSONDecodeError:
        print("   [Orchestrator] Warning: Could not parse plan. Defaulting to all agents.")
        plan = {"agents_needed": ["data_agent", "business_agent"],
                "routing_reasoning": "defaulting to full crew",
                "question_focus": question}

    print(f"   [Orchestrator] Routing to: {plan.get('agents_needed', [])}")
    print(f"   [Orchestrator] Reasoning: {plan.get('routing_reasoning', '')}")

    return plan, messages


# ---------------------------------------------------------------------------
# Turn 2 — Execute: run agents in dependency order
# ---------------------------------------------------------------------------

def turn2_execute(plan: dict, question: str) -> dict:
    """
    Execute the agents in the plan respecting dependency order.
    data_agent always runs before business_agent.
    Returns collected outputs keyed by agent name.
    """
    print("\n   [Orchestrator] Turn 2 — Executing specialist agents...")

    agents_needed = plan.get("agents_needed", [])
    outputs       = {}

    # Always run data_agent first if needed
    if "data_agent" in agents_needed:
        print("\n   [Orchestrator] Calling Data Agent...")
        outputs["data_agent"] = run_agent("data_agent", question_context=question)

    # Run business_agent with data_agent output
    if "business_agent" in agents_needed:
        if "data_agent" not in outputs:
            print("   [Orchestrator] business_agent needs data_agent — adding to plan...")
            outputs["data_agent"] = run_agent("data_agent", question_context=question)

        print("\n   [Orchestrator] Calling Business Agent...")
        outputs["business_agent"] = run_agent(
            "business_agent",
            data=outputs["data_agent"],
            question_context=question,
        )

    return outputs


# ---------------------------------------------------------------------------
# Turn 3 — Synthesize: combine specialist outputs into one answer
# ---------------------------------------------------------------------------

def turn3_synthesize(question: str, outputs: dict, messages: list) -> str:
    """
    Feed all specialist outputs back to Claude.
    Claude synthesizes them into a single coherent final answer.
    Returns the final answer as a formatted string.
    """
    print("\n   [Orchestrator] Turn 3 — Synthesizing final answer...")

    business_output = outputs.get("business_agent", {})
    data_output     = outputs.get("data_agent", {})

    synthesis_prompt = f"""The specialist agents have completed their work.
Here are their outputs:

=== DATA AGENT OUTPUT ===
Segments collected: {len(data_output.get('segment_distribution', []))}
Top customers: {len(data_output.get('top_customers', []))}
Countries: {len(data_output.get('country_distribution', []))}
Recency signals: {json.dumps(data_output.get('recency_signals', {}), indent=2)}

=== BUSINESS AGENT OUTPUT ===
Health score: {business_output.get('health_score', 'N/A')}/10
Key findings: {json.dumps(business_output.get('key_findings', []), indent=2)}
Segment insights: {json.dumps(business_output.get('segment_insights', []), indent=2)}
Immediate actions: {json.dumps(business_output.get('immediate_actions', []), indent=2)}
Strategic recommendations: {json.dumps(business_output.get('strategic_recommendations', []), indent=2)}
Churn risk: {business_output.get('churn_risk_summary', '')}
Growth opportunity: {business_output.get('growth_opportunity', '')}

Original question: "{question}"

Synthesize these specialist outputs into a single, clear, executive-ready answer
to the original question. Be direct and specific. Lead with the most important finding.
Write in clear prose — not JSON. 3-5 paragraphs maximum."""

    messages.append({"role": "user", "content": synthesis_prompt})

    system = """You are the orchestrator of a multi-agent AI crew.
Your job is to synthesize specialist agent outputs into one clear,
executive-ready answer. Be direct, specific, and commercial.
Reference actual numbers. Lead with what matters most."""

    final_answer = _call_claude(messages, system)
    print("   [Orchestrator] Synthesis complete.")
    return final_answer


# ---------------------------------------------------------------------------
# Main orchestration loop
# ---------------------------------------------------------------------------

def run(question: str) -> dict:
    """
    Orchestrate the full crew for a given business question.

    Turn 1 — Plan:     Claude decides which agents to invoke
    Turn 2 — Execute:  Run agents in dependency order
    Turn 3 — Synthesize: Claude combines outputs into final answer

    Returns a structured result with the final answer and full audit trail.
    """
    print("=" * 60)
    print("  CUSTOMER BEHAVIOR CREW — Orchestrating")
    print(f"  Question: {question}")
    print("=" * 60)

    start_time = datetime.now(timezone.utc)

    # Turn 1 — Plan
    plan, messages = turn1_plan(question)

    # Turn 2 — Execute
    outputs = turn2_execute(plan, question)

    # Turn 3 — Synthesize
    final_answer = turn3_synthesize(question, outputs, messages)

    end_time     = datetime.now(timezone.utc)
    duration_sec = round((end_time - start_time).total_seconds(), 1)

    result = {
        "run_id":         f"crew-{start_time.strftime('%Y%m%d-%H%M%S')}",
        "question":       question,
        "answered_at":    end_time.isoformat(),
        "duration_sec":   duration_sec,
        "agents_invoked": plan.get("agents_needed", []),
        "routing_reason": plan.get("routing_reasoning", ""),
        "health_score":   outputs.get("business_agent", {}).get("health_score"),
        "final_answer":   final_answer,
        "audit": {
            "plan":             plan,
            "business_summary": {
                "key_findings":             outputs.get("business_agent", {}).get("key_findings", []),
                "immediate_actions":        outputs.get("business_agent", {}).get("immediate_actions", []),
                "strategic_recommendations":outputs.get("business_agent", {}).get("strategic_recommendations", []),
                "churn_risk_summary":       outputs.get("business_agent", {}).get("churn_risk_summary", ""),
                "growth_opportunity":       outputs.get("business_agent", {}).get("growth_opportunity", ""),
            }
        }
    }

    print("\n" + "=" * 60)
    print(f"  CREW COMPLETE in {duration_sec}s")
    print(f"  Run ID: {result['run_id']}")
    print(f"  Health score: {result['health_score']}/10")
    print("=" * 60)

    return result


if __name__ == "__main__":
    question = "Who are our most at-risk customers and what should we do about them?"
    result   = run(question)
    print("\n--- FINAL ANSWER ---")
    print(result["final_answer"])
