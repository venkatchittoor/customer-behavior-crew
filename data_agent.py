from dotenv import load_dotenv
load_dotenv()

"""
data_agent.py
-------------
The DATA AGENT of the customer-behavior-crew.

Strict lane: this agent ONLY retrieves data. It never interprets,
never recommends, never draws conclusions. It answers one question:
"What do the numbers say?"

Interpretation is the Business Agent's job. Keeping these lanes
separate is what makes this a crew, not just a bigger agent.

Think of the Data Agent as the analyst who runs the numbers and
hands the printout to the strategist — no editorializing, just data.

Data sources (3 Gold/Silver tables):
  - gold_customer_segments    — tenure segmentation, days since signup
  - gold_top_customers        — spend, order count, recency
  - silver_customers_enriched — country distribution, enriched attributes

Designed for extensibility: add new query methods here and register
them in agent_registry.py — the Orchestrator picks them up automatically.
"""

import os
import time
import requests
from datetime import datetime, timezone
from databricks.sdk import WorkspaceClient


# ---------------------------------------------------------------------------
# Databricks connection helpers
# ---------------------------------------------------------------------------

def _get_client():
    return WorkspaceClient()


def _get_warehouse_id(client) -> str:
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")
    if http_path:
        return http_path.strip("/").split("/")[-1]
    warehouses = client.warehouses.list()
    for wh in warehouses:
        if wh.state.value in ("RUNNING", "IDLE"):
            return wh.id
    raise RuntimeError("No running SQL warehouse found.")


def _execute_sql(client, sql: str, warehouse_id: str) -> list:
    host = client.config.host
    token = client.config.token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers=headers,
        json={
            "statement": sql,
            "warehouse_id": warehouse_id,
            "wait_timeout": "30s",
            "on_wait_timeout": "CONTINUE",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    statement_id = payload["statement_id"]

    for _ in range(30):
        state = payload.get("status", {}).get("state", "")
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        time.sleep(2)
        poll = requests.get(
            f"{host}/api/2.0/sql/statements/{statement_id}",
            headers=headers,
        )
        poll.raise_for_status()
        payload = poll.json()

    state = payload.get("status", {}).get("state")
    if state != "SUCCEEDED":
        error = payload.get("status", {}).get("error", {})
        raise RuntimeError(f"SQL failed [{state}]: {error.get('message', 'unknown')}")

    schema   = payload.get("manifest", {}).get("schema", {}).get("columns", [])
    col_names = [c["name"] for c in schema]
    rows     = payload.get("result", {}).get("data_array", [])
    return [dict(zip(col_names, row)) for row in rows]


# ---------------------------------------------------------------------------
# Query methods — each returns raw data, no interpretation
# ---------------------------------------------------------------------------

def get_segment_distribution(client, warehouse_id: str) -> list:
    """How are customers distributed across tenure segments?"""
    sql = """
        SELECT
            tenure_segment,
            COUNT(*)                            AS customer_count,
            ROUND(AVG(days_since_signup), 0)    AS avg_days_since_signup,
            MIN(signup_date)                    AS earliest_signup,
            MAX(signup_date)                    AS latest_signup
        FROM workspace.ecommerce.silver_customers_enriched
        GROUP BY tenure_segment
        ORDER BY avg_days_since_signup DESC
    """
    return _execute_sql(client, sql.strip(), warehouse_id)


def get_top_customers(client, warehouse_id: str, limit: int = 10) -> list:
    """Who are the highest-value customers by total spend?"""
    sql = f"""
        SELECT
            customer_id,
            customer_name,
            country,
            ROUND(total_spend, 2)       AS total_spend,
            order_count,
            ROUND(avg_order_value, 2)   AS avg_order_value,
            first_order,
            last_order,
            DATEDIFF(CURRENT_DATE(), last_order) AS days_since_last_order
        FROM workspace.ecommerce.gold_top_customers
        ORDER BY total_spend DESC
        LIMIT {limit}
    """
    return _execute_sql(client, sql.strip(), warehouse_id)


def get_country_distribution(client, warehouse_id: str) -> list:
    """Which countries have the most customers?"""
    sql = """
        SELECT
            country,
            COUNT(*)                            AS customer_count,
            ROUND(AVG(days_since_signup), 0)    AS avg_days_since_signup,
            MIN(tenure_segment)                 AS common_segment
        FROM workspace.ecommerce.silver_customers_enriched
        GROUP BY country
        ORDER BY customer_count DESC
        LIMIT 10
    """
    return _execute_sql(client, sql.strip(), warehouse_id)


def get_recency_signals(client, warehouse_id: str) -> dict:
    """How recently have top customers been active? Flags churn risk."""
    sql = """
        SELECT
            COUNT(*)                                                        AS total_customers,
            SUM(CASE WHEN DATEDIFF(CURRENT_DATE(), last_order) <= 30
                THEN 1 ELSE 0 END)                                          AS active_last_30d,
            SUM(CASE WHEN DATEDIFF(CURRENT_DATE(), last_order) BETWEEN 31 AND 90
                THEN 1 ELSE 0 END)                                          AS active_31_90d,
            SUM(CASE WHEN DATEDIFF(CURRENT_DATE(), last_order) > 90
                THEN 1 ELSE 0 END)                                          AS inactive_90d_plus,
            ROUND(AVG(DATEDIFF(CURRENT_DATE(), last_order)), 1)             AS avg_days_since_order,
            ROUND(MAX(DATEDIFF(CURRENT_DATE(), last_order)), 0)             AS max_days_since_order
        FROM workspace.ecommerce.gold_top_customers
    """
    rows = _execute_sql(client, sql.strip(), warehouse_id)
    return rows[0] if rows else {}


def get_spend_percentiles(client, warehouse_id: str) -> dict:
    """What does the spend distribution look like across top customers?"""
    sql = """
        SELECT
            ROUND(MIN(total_spend), 2)                          AS min_spend,
            ROUND(AVG(total_spend), 2)                          AS avg_spend,
            ROUND(MAX(total_spend), 2)                          AS max_spend,
            ROUND(PERCENTILE(total_spend, 0.25), 2)             AS p25_spend,
            ROUND(PERCENTILE(total_spend, 0.50), 2)             AS median_spend,
            ROUND(PERCENTILE(total_spend, 0.75), 2)             AS p75_spend,
            ROUND(PERCENTILE(total_spend, 0.90), 2)             AS p90_spend,
            COUNT(*)                                            AS total_customers
        FROM workspace.ecommerce.gold_top_customers
    """
    rows = _execute_sql(client, sql.strip(), warehouse_id)
    return rows[0] if rows else {}


# ---------------------------------------------------------------------------
# Main data collection — assembles all signals into one payload
# ---------------------------------------------------------------------------

def collect(question_context: str = "") -> dict:
    """
    Collect all customer behavior signals from Databricks.
    Returns a structured dict ready to pass to the Business Agent.

    question_context: optional hint from the Orchestrator about
    what question is being answered — logged for traceability.
    """
    print("   [Data Agent] Connecting to Databricks...")
    client       = _get_client()
    warehouse_id = _get_warehouse_id(client)
    print(f"   [Data Agent] Connected. Warehouse: {warehouse_id}")

    print("   [Data Agent] Pulling customer signals...")

    segments     = get_segment_distribution(client, warehouse_id)
    top_customers = get_top_customers(client, warehouse_id, limit=10)
    countries    = get_country_distribution(client, warehouse_id)
    recency      = get_recency_signals(client, warehouse_id)
    spend_dist   = get_spend_percentiles(client, warehouse_id)

    payload = {
        "collected_at":        datetime.now(timezone.utc).isoformat(),
        "question_context":    question_context,
        "segment_distribution": segments,
        "top_customers":       top_customers,
        "country_distribution": countries,
        "recency_signals":     recency,
        "spend_distribution":  spend_dist,
    }

    print(f"   [Data Agent] Done. {len(segments)} segments, "
          f"{len(top_customers)} top customers, "
          f"{len(countries)} countries collected.")

    return payload


# ---------------------------------------------------------------------------
# Agent interface — standard contract for agent_registry.py
# ---------------------------------------------------------------------------

AGENT_NAME        = "data_agent"
AGENT_DESCRIPTION = (
    "Retrieves raw customer behavior metrics from Databricks Delta tables. "
    "Covers segment distribution, top customers by spend, country breakdown, "
    "recency signals, and spend percentiles. Returns data only — no interpretation."
)

def run(question_context: str = "") -> dict:
    """Standard entry point called by the Orchestrator."""
    return collect(question_context)


if __name__ == "__main__":
    import json
    print("Testing Data Agent standalone...\n")
    data = collect("standalone test")
    print("\n--- DATA AGENT OUTPUT ---")
    print(json.dumps(data, indent=2, default=str))
