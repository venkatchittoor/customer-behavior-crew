# 🤝 Customer Behavior Crew

> *A multi-agent AI crew that answers business questions about customer behavior — an Orchestrator routes questions to specialist Data and Business agents, coordinates their execution, and synthesizes a single executive-ready answer. Built with Claude API + Databricks. Designed for extensibility.*

---

## The Leap: From Agent to Crew

The previous projects in this portfolio — `data-incident-agent` and `pricing-decision-agent` — are single agents. One agent observes, reasons, and acts. It is a generalist.

This project is different. It is a crew.

| | Single agent | Multi-agent crew |
|---|---|---|
| **Structure** | One agent does everything | Specialists collaborate |
| **Routing** | Fixed execution path | Orchestrator decides dynamically |
| **Extensibility** | Add logic to one file | Add a new agent file, register it |
| **Analogy** | Solo consultant | Consulting firm |

In a consulting firm, the partner doesn't run the analysis — they manage the engagement. The analyst doesn't write the strategy deck — they produce the numbers. The strategist doesn't query the database — they interpret what the analyst found.

Each specialist is better at their job precisely because they don't do anyone else's job.

---

## The Crew

```
Business question
      │
      ▼
┌─────────────────────────────────────┐
│           Orchestrator              │
│  Routes · Coordinates · Synthesizes │
│  Never touches the database         │
└────────────┬───────────────┬────────┘
             │               │
             ▼               ▼
    ┌──────────────┐  ┌────────────────┐
    │  Data Agent  │  │ Business Agent │
    │              │→ │                │
    │ Queries Delta│  │ Interprets     │
    │ Returns data │  │ Recommends     │
    │ No opinions  │  │ No SQL         │
    └──────────────┘  └────────────────┘
             │               │
             └───────┬───────┘
                     ▼
            Final answer
      (narrative + actions + numbers)
```

| Agent | Strict lane | Data sources |
|---|---|---|
| `orchestrator.py` | Plans, routes, synthesizes — never queries | None |
| `data_agent.py` | Queries only — never interprets | `gold_customer_segments`, `gold_top_customers`, `silver_customers_enriched` |
| `business_agent.py` | Interprets only — never queries | Output from Data Agent |
| `agent_registry.py` | Directory — extensibility layer | None |

---

## The Three-Turn Orchestration Loop

```
Turn 1 — Plan
  Orchestrator feeds the question + agent registry to Claude
  Claude reads agent descriptions and decides who to invoke
  Routing is LLM-driven — not hardcoded if/else logic
        ↓
Turn 2 — Execute
  Orchestrator calls agents in dependency order
  Data Agent runs first (no dependencies)
  Business Agent runs second (needs Data Agent output)
  Each agent stays in its lane — no cross-agent calls
        ↓
Turn 3 — Synthesize
  Orchestrator feeds both agent outputs back to Claude
  Claude produces one coherent executive-ready prose answer
  Neither agent alone could produce this — synthesis is the Orchestrator's unique contribution
```

The routing decision in Turn 1 is what makes this genuinely multi-agent rather than just a pipeline. Claude reads the agent descriptions from the registry and decides which specialists the question needs — dynamically, per question. Ask about churn risk and it routes to both agents. Ask a definitional question and it routes to neither.

---

## Extensibility by Design

Adding a new agent to the crew requires exactly three steps:

**1. Create the agent file** (`risk_agent.py`) with the standard interface:
```python
AGENT_NAME        = "risk_agent"
AGENT_DESCRIPTION = "Assesses revenue concentration and customer churn risk..."

def run(data: dict, question_context: str = "") -> dict:
    ...
```

**2. Register it** in `agent_registry.py`:
```python
"risk_agent": {
    "name":        "risk_agent",
    "description": risk_agent.AGENT_DESCRIPTION,
    "requires":    "data_agent",
    "run":         risk_agent.run,
}
```

**3. Done.** The Orchestrator reads the registry at runtime — it picks up the new agent automatically. Zero changes to `orchestrator.py`. Zero changes to existing agents.

This is the extensibility guarantee: the crew grows by addition, not by modification.

---

## Sample Output

The same crew, three completely different questions, zero code changes:

**Question 1:** *"Who are our most at-risk customers?"*
```
Health score: 4/10

Your two highest-value at-risk customers — Denise Weber and Sandra
Montgomery — represent over $21,000 in immediate churn risk and need
emergency intervention today. These customers ranked #6 and #9 in
total value but haven't ordered in 93 and 75 days respectively.

Beyond these critical cases, you have 7 customers in churn territory
(90+ days inactive) and 38 more in the danger zone (31-90 days).
This represents roughly $30,000+ in recoverable revenue at risk...
```

**Question 2:** *"Which segments are healthiest?"*
```
Health score: 7/10

Your Loyal segment is healthy but dangerously concentrated, while
your New customer acquisition is failing. Your top 10 customers
generate $117,878 — 18% of total revenue. Losing 2-3 of them would
significantly damage the business...
```

**Question 3:** *"Which segment has the best long-term revenue potential?"*
```
The Growing segment has the best long-term revenue potential. These
41 customers represent your optimal revenue conversion zone — proven
purchase behavior, 238 days average tenure, and significant room
for expansion. Scaling this segment to 80+ customers would double
your highest-converting customer base...
```

Different question, different lens, different answer. The Orchestrator routed each question dynamically. The specialists adapted their focus. The synthesis was question-specific and data-grounded every time.

---

## What Makes This Different From a Single Agent

A single agent with access to all tools would also answer these questions. So why a crew?

**Separation of concerns.** When the Data Agent returns wrong data, you know exactly where to look — and you fix one file. When the Business Agent's recommendations are too conservative, you tune one system prompt. With a single agent doing everything, every bug is a mystery.

**Independent improvement.** Swap the Business Agent's model from Sonnet to Opus for deeper reasoning — zero impact on the Data Agent. Replace the Data Agent's SQL with an API call — zero impact on the Business Agent. Components evolve independently.

**Honest specialization.** The Data Agent has no opinions because it is not allowed to have opinions. That constraint is enforced by architecture, not by hoping the prompt holds. The Business Agent never writes SQL because it has no database connection. These are hard boundaries, not soft guidelines.

**The consulting firm analogy holds:** a firm that sends one person to do everything scales linearly with headcount. A firm with specialists scales through coordination — the same Orchestrator can manage two agents today and six agents next quarter without changing the coordination model.

---

## Setup

### Prerequisites
- Python 3.8+
- Databricks workspace with Unity Catalog
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Installation

```bash
git clone https://github.com/venkatchittoor/customer-behavior-crew.git
cd customer-behavior-crew
python3 -m venv venv
source venv/bin/activate
pip install databricks-sdk requests anthropic python-dotenv
```

### Configuration

```
DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
DATABRICKS_TOKEN=your-personal-access-token
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
ANTHROPIC_API_KEY=your-anthropic-api-key
```

---

## Usage

```bash
# Interactive mode — type any question or choose a preset
python run_crew.py

# Ask a specific question
python run_crew.py --question "Which countries have the highest churn risk?"

# Run a preset question
python run_crew.py --preset 1    # churn risk
python run_crew.py --preset 2    # segment health
python run_crew.py --preset 3    # growth opportunity
python run_crew.py --preset 4    # churn overview
python run_crew.py --preset 5    # geographic analysis

# See routing plan without executing
python run_crew.py --dry-run --question "Who are our top customers?"

# Raw JSON output
python run_crew.py --preset 1 --json
```

---

## Portfolio Context

Three repos. Three distinct agentic patterns. One coherent arc.

| Repo | Pattern | Core capability |
|---|---|---|
| [`ecommerce-pipeline`](https://github.com/venkatchittoor/ecommerce-pipeline) | Pipeline engineering | Build and move data through Medallion Architecture |
| [`data-incident-agent`](https://github.com/venkatchittoor/data-incident-agent) | Monitoring agent | Observe, diagnose, report — never acts |
| [`pricing-decision-agent`](https://github.com/venkatchittoor/pricing-decision-agent) | Decisioning agent | Reason, decide, act — with confidence-gated autonomy |
| [`customer-behavior-crew`](https://github.com/venkatchittoor/customer-behavior-crew) | Multi-agent crew | Orchestrate specialists, synthesize answers |

The progression is intentional:
```
Build pipelines → Monitor with AI → Decide with AI → Coordinate AI agents
```

Each repo adds a capability the previous one didn't have. Together they demonstrate the full spectrum from data engineering to autonomous multi-agent systems.

---

## Tech Stack

- **Databricks** — Delta tables, SQL warehouses, Unity Catalog, REST API
- **Claude API (Anthropic)** — Orchestration reasoning, business interpretation, synthesis
- **Databricks SDK** — Auto-credential detection
- **Python** — `requests`, `python-dotenv`, `databricks-sdk`

---

## Roadmap

- [ ] **v2 — Risk Agent:** Specialist for revenue concentration and churn scoring — plug in via registry, zero Orchestrator changes
- [ ] **v3 — Memory:** Persist crew outputs to Delta table, enable *"how has health score changed this month?"* questions
- [ ] **v4 — Slack integration:** Push synthesized answers to a Slack channel on a schedule

---

*Built by Venkat Chittoor in collaboration with Claude (Anthropic) — a demonstration that the engineers who thrive in the AI era are not those who know everything, but those who adapt fast, leverage the best tools available, and ship things that matter. The future belongs to those who adapt and adopt.*
