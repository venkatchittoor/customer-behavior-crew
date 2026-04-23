from dotenv import load_dotenv
load_dotenv()

"""
agent_registry.py
-----------------
The DIRECTORY of the customer-behavior-crew.

This is the extensibility layer. The Orchestrator never imports
agents directly — it reads this registry and decides which agents
to invoke based on their descriptions and the question at hand.

Adding a new agent to the crew:
  1. Create your new agent file (e.g. risk_agent.py)
  2. Implement the standard interface:
       AGENT_NAME        = "risk_agent"
       AGENT_DESCRIPTION = "what this agent does in plain English"
       def run(...) -> dict: ...
  3. Import and register it here — one entry in REGISTRY
  4. Done. The Orchestrator picks it up automatically.

Zero changes to orchestrator.py. Zero changes to existing agents.
That is the extensibility guarantee.
"""

import data_agent
import business_agent

# ---------------------------------------------------------------------------
# Agent Registry
# ---------------------------------------------------------------------------
# Each entry defines:
#   name        — unique identifier, used by Orchestrator to route
#   description — plain English description fed to Claude for routing decisions
#   requires    — which other agent's output this agent needs as input (if any)
#   run         — the callable entry point

REGISTRY = {
    "data_agent": {
        "name":        "data_agent",
        "description": data_agent.AGENT_DESCRIPTION,
        "requires":    None,
        "run":         data_agent.run,
    },
    "business_agent": {
        "name":        "business_agent",
        "description": business_agent.AGENT_DESCRIPTION,
        "requires":    "data_agent",
        "run":         business_agent.run,
    },

    # ── Future agents — uncomment to activate ─────────────────────
    # "risk_agent": {
    #     "name":        "risk_agent",
    #     "description": risk_agent.AGENT_DESCRIPTION,
    #     "requires":    "data_agent",
    #     "run":         risk_agent.run,
    # },
    # "geo_agent": {
    #     "name":        "geo_agent",
    #     "description": geo_agent.AGENT_DESCRIPTION,
    #     "requires":    "data_agent",
    #     "run":         geo_agent.run,
    # },
}


# ---------------------------------------------------------------------------
# Registry access methods — used by the Orchestrator
# ---------------------------------------------------------------------------

def get_agents() -> dict:
    """Return the full registry — Orchestrator uses this to plan."""
    return REGISTRY


def get_agent(name: str) -> dict:
    """Return a single agent entry by name."""
    if name not in REGISTRY:
        raise ValueError(f"Agent '{name}' not found in registry. "
                         f"Available agents: {list(REGISTRY.keys())}")
    return REGISTRY[name]


def list_agents_for_prompt() -> str:
    """
    Format agent descriptions for inclusion in the Orchestrator's
    Claude prompt — tells Claude what tools are available.
    """
    lines = []
    for name, entry in REGISTRY.items():
        requires = f" (requires: {entry['requires']})" if entry["requires"] else ""
        lines.append(f"- {name}{requires}: {entry['description']}")
    return "\n".join(lines)


def run_agent(name: str, **kwargs) -> dict:
    """
    Execute an agent by name with the provided kwargs.
    The Orchestrator calls this — never calls agent.run() directly.
    """
    entry = get_agent(name)
    return entry["run"](**kwargs)


if __name__ == "__main__":
    print("=== Agent Registry ===\n")
    for name, entry in REGISTRY.items():
        requires = f"requires: {entry['requires']}" if entry["requires"] else "no dependencies"
        print(f"  {name} ({requires})")
        print(f"    {entry['description']}\n")
    print(f"Total agents registered: {len(REGISTRY)}")
