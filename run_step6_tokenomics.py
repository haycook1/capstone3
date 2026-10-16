from __future__ import annotations

import json
import os
from collections import defaultdict

os.environ.setdefault(
    "DECISION_LOG_PATH",
    "step6-tokenomics-events.jsonl",
)

from orchestrator import run_orchestrator


QUESTIONS = [
    "How many active projects are there?",
    "List active projects and their budgets.",
    "Which invoices are overdue?",
    "How many consultants are assigned to projects?",
    "Summarize the indexed documents.",
    "What migration phases does the playbook describe?",
    "What guidance covers rollback planning?",
    "What communication guidance does the migration playbook provide?",
    (
        "Compare active project billing risks with supporting "
        "migration policy guidance."
    ),
    (
        "Using the project database and indexed documents, identify "
        "active project risks and supporting policy guidance."
    ),
]


def add_stage_totals(
    totals: dict[str, dict[str, float]],
    by_stage: dict[str, dict[str, float]],
) -> None:
    for stage, values in by_stage.items():
        target = totals[stage]
        target["input_tokens"] += values["input_tokens"]
        target["output_tokens"] += values["output_tokens"]
        target["total_tokens"] += values["total_tokens"]
        target["cost_usd"] += values["cost_usd"]


def main() -> None:
    stage_totals = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }
    )

    total_cost = 0.0

    for number, question in enumerate(QUESTIONS, start=1):
        result = run_orchestrator(
            question,
            include_trace=True,
        )
        metadata = result["metadata"]
        token_breakdown = metadata["token_breakdown"]
        cost_breakdown = metadata["cost_breakdown"]

        add_stage_totals(
            stage_totals,
            token_breakdown["by_stage"],
        )

        total_cost += cost_breakdown["total_cost_usd"]

        print("\n" + "=" * 90)
        print(f"QUERY {number}: {question}")
        print(f"ROUTE: {metadata['route']}")
        print("CLAUDE CALL AND STAGE LOG:")

        for event in metadata.get("trace_events", []):
            print(
                json.dumps(
                    {
                        "event_type": event["event_type"],
                        "stage": event["stage"],
                        "usage": event.get("usage"),
                        "cost_usd": event.get("cost_usd"),
                    },
                    default=str,
                )
            )

        print("FINAL ANSWER:")
        print(result["answer"][:1000])

    highest_stage = max(
        stage_totals,
        key=lambda stage: stage_totals[stage]["total_tokens"],
    )

    print("\n" + "=" * 90)
    print("10-QUERY TOKENOMICS SUMMARY")
    print("-" * 90)
    print(
        f"{'COMPONENT':<24}"
        f"{'INPUT':>12}"
        f"{'OUTPUT':>12}"
        f"{'TOTAL':>12}"
        f"{'COST (USD)':>16}"
    )

    for stage, values in sorted(stage_totals.items()):
        print(
            f"{stage:<24}"
            f"{values['input_tokens']:>12}"
            f"{values['output_tokens']:>12}"
            f"{values['total_tokens']:>12}"
            f"{values['cost_usd']:>16.6f}"
        )

    total_input = sum(
        values["input_tokens"]
        for values in stage_totals.values()
    )
    total_output = sum(
        values["output_tokens"]
        for values in stage_totals.values()
    )

    print("-" * 90)
    print(f"Total input tokens: {total_input}")
    print(f"Total output tokens: {total_output}")
    print(f"Total tokens: {total_input + total_output}")
    print(f"Total cost for 10 queries: ${total_cost:.6f}")
    print(f"Projected cost per 1,000 queries: ${total_cost * 100:.2f}")
    print(
        "Highest token-consuming component: "
        f"{highest_stage}"
    )
    print(
        "Event log written to: "
        f"{os.environ['DECISION_LOG_PATH']}"
    )


if __name__ == "__main__":
    main()
