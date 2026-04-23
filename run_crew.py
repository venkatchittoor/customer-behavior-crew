from dotenv import load_dotenv
load_dotenv()

"""
run_crew.py
-----------
The single entrypoint for the customer-behavior-crew.

Usage:
  python run_crew.py                          # interactive mode
  python run_crew.py --question "your question"  # single question
  python run_crew.py --preset 1               # run a preset question
  python run_crew.py --list-presets           # show all preset questions
  python run_crew.py --dry-run                # show routing plan only, skip execution
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from orchestrator import run


# ---------------------------------------------------------------------------
# Preset questions — demonstrate crew versatility
# ---------------------------------------------------------------------------

PRESETS = {
    1: "Who are our most at-risk customers and what should we do about them?",
    2: "Which customer segments are healthiest and which need the most attention?",
    3: "Where is our biggest revenue growth opportunity in the customer base?",
    4: "What does our customer churn risk look like right now?",
    5: "Which countries represent our strongest and weakest customer relationships?",
}


def print_banner():
    print()
    print("=" * 60)
    print("  CUSTOMER BEHAVIOR CREW")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("  Agents: Data Agent + Business Agent (+ extensible)")
    print("=" * 60)
    print()


def print_presets():
    print("\nPreset questions:\n")
    for num, question in PRESETS.items():
        print(f"  [{num}] {question}")
    print()


def print_result(result: dict):
    """Print a clean formatted summary of the crew result."""
    print()
    print("=" * 60)
    print(f"  Run ID        : {result.get('run_id')}")
    print(f"  Duration      : {result.get('duration_sec')}s")
    print(f"  Agents invoked: {', '.join(result.get('agents_invoked', []))}")
    print(f"  Health score  : {result.get('health_score')}/10")
    print("=" * 60)

    print(f"\n  QUESTION:\n  {result.get('question')}")
    print(f"\n  ROUTING REASON:\n  {result.get('routing_reason')}")

    audit = result.get("audit", {}).get("business_summary", {})

    immediate = audit.get("immediate_actions", [])
    if immediate:
        print(f"\n  IMMEDIATE ACTIONS:")
        for i, action in enumerate(immediate, 1):
            print(f"  {i}. {action}")

    churn = audit.get("churn_risk_summary", "")
    if churn:
        print(f"\n  CHURN RISK:\n  {churn}")

    growth = audit.get("growth_opportunity", "")
    if growth:
        print(f"\n  GROWTH OPPORTUNITY:\n  {growth}")

    print(f"\n  FINAL ANSWER:\n")
    for line in result.get("final_answer", "").split("\n"):
        print(f"  {line}")

    print()


def interactive_mode():
    """Prompt the user to enter a question interactively."""
    print_presets()
    print("Enter a preset number [1-5] or type your own question.")
    print("Type 'quit' to exit.\n")

    while True:
        user_input = input("  Your question: ").strip()

        if user_input.lower() in ("quit", "exit", "q"):
            print("\nExiting crew. Goodbye!")
            sys.exit(0)

        if user_input.isdigit() and int(user_input) in PRESETS:
            question = PRESETS[int(user_input)]
            print(f"\n  Running preset: {question}\n")
        elif user_input:
            question = user_input
        else:
            print("  Please enter a question or preset number.\n")
            continue

        result = run(question)
        print_result(result)

        again = input("\n  Ask another question? [y/n]: ").strip().lower()
        if again != "y":
            print("\nExiting crew. Goodbye!")
            break


def main():
    parser = argparse.ArgumentParser(
        description="Customer Behavior Crew — multi-agent AI analysis powered by Claude API + Databricks"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        help="Business question to answer"
    )
    parser.add_argument(
        "--preset", "-p",
        type=int,
        choices=PRESETS.keys(),
        help="Run a preset question (1-5)"
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all preset questions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show routing plan only — skip agent execution"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON result"
    )
    args = parser.parse_args()

    print_banner()

    # List presets and exit
    if args.list_presets:
        print_presets()
        sys.exit(0)

    # Dry run — show routing plan only
    if args.dry_run:
        from orchestrator import turn1_plan
        question = (
            args.question or
            PRESETS.get(args.preset) or
            PRESETS[1]
        )
        print(f"  DRY RUN — Routing plan for:\n  '{question}'\n")
        plan, _ = turn1_plan(question)
        print(f"\n  Agents needed  : {plan.get('agents_needed')}")
        print(f"  Routing reason : {plan.get('routing_reason')}")
        print(f"  Question focus : {plan.get('question_focus')}")
        sys.exit(0)

    # Single question from flag
    if args.question:
        result = run(args.question)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print_result(result)
        sys.exit(0)

    # Preset question
    if args.preset:
        question = PRESETS[args.preset]
        print(f"  Running preset [{args.preset}]: {question}\n")
        result = run(question)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print_result(result)
        sys.exit(0)

    # Default — interactive mode
    interactive_mode()


if __name__ == "__main__":
    main()
