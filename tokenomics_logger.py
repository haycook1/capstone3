from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

COST_PER_1K_INPUT = float(os.getenv("COST_PER_1K_INPUT", "0.003"))
COST_PER_1K_OUTPUT = float(os.getenv("COST_PER_1K_OUTPUT", "0.015"))

_EVENTS: list[dict[str, Any]] = []
_EVENTS_LOCK = threading.Lock()


def _usage(input_tokens: int = 0, output_tokens: int = 0) -> dict[str, int]:
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
    }


def cost_for_tokens(input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens / 1000 * COST_PER_1K_INPUT)
        + (output_tokens / 1000 * COST_PER_1K_OUTPUT),
        6,
    )


def _write_event(entry: dict[str, Any]) -> None:
    logger.info(json.dumps(entry, default=str))

    path = os.getenv("DECISION_LOG_PATH") or "/tmp/agent_decisions.jsonl"
    if path:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(path, "a", encoding="utf-8") as file:
            file.write(json.dumps(entry, default=str) + "\n")


def _record_event(entry: dict[str, Any]) -> None:
    with _EVENTS_LOCK:
        _EVENTS.append(entry)

    _write_event(entry)


def log_decision(
    stage: str,
    question: str,
    details: dict[str, Any],
    trace_id: str | None = None,
) -> None:
    _record_event(
        {
            "event_type": "decision",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "stage": stage,
            "question": question,
            "details": details,
        }
    )


def log_llm_call(
    stage: str,
    question: str,
    input_tokens: int,
    output_tokens: int,
    trace_id: str | None,
    model: str = "claude-sonnet-4-6",
) -> dict[str, Any]:
    usage = _usage(input_tokens, output_tokens)

    entry = {
        "event_type": "llm_call",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "stage": stage,
        "question": question,
        "model": model,
        "usage": usage,
        "cost_usd": cost_for_tokens(
            usage["input_tokens"],
            usage["output_tokens"],
        ),
    }

    _record_event(entry)
    return entry


def log_stage(
    stage: str,
    question: str,
    trace_id: str | None,
    details: dict[str, Any] | None = None,
) -> None:
    usage = _usage()

    _record_event(
        {
            "event_type": "stage",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "stage": stage,
            "question": question,
            "usage": usage,
            "cost_usd": 0.0,
            "details": details or {},
        }
    )


def clear_trace_events(trace_id: str) -> None:
    with _EVENTS_LOCK:
        _EVENTS[:] = [
            event for event in _EVENTS
            if event.get("trace_id") != trace_id
        ]


def get_trace_events(trace_id: str) -> list[dict[str, Any]]:
    with _EVENTS_LOCK:
        return [
            dict(event)
            for event in _EVENTS
            if event.get("trace_id") == trace_id
        ]


def summarize_trace(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = {}

    for event in events:
        stage = event["stage"]
        usage = event.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        cost_usd = float(event.get("cost_usd", 0.0) or 0.0)

        record = by_stage.setdefault(
            stage,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "llm_calls": 0,
            },
        )

        record["input_tokens"] += input_tokens
        record["output_tokens"] += output_tokens
        record["total_tokens"] += input_tokens + output_tokens
        record["cost_usd"] = round(record["cost_usd"] + cost_usd, 6)

        if event.get("event_type") == "llm_call":
            record["llm_calls"] += 1

    total_input = sum(item["input_tokens"] for item in by_stage.values())
    total_output = sum(item["output_tokens"] for item in by_stage.values())
    total_cost = round(
        sum(item["cost_usd"] for item in by_stage.values()),
        6,
    )

    llm_stages = {
        stage: item
        for stage, item in by_stage.items()
        if item["llm_calls"] > 0
    }

    highest_stage = (
        max(
            llm_stages,
            key=lambda stage: llm_stages[stage]["total_tokens"],
        )
        if llm_stages
        else None
    )

    return {
        "token_breakdown": {
            "by_stage": by_stage,
            "total": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_input + total_output,
            },
            "highest_token_component": highest_stage,
        },
        "cost_breakdown": {
            "by_stage": {
                stage: item["cost_usd"]
                for stage, item in by_stage.items()
            },
            "total_cost_usd": total_cost,
            "cost_per_1000_queries_usd": round(total_cost * 1000, 2),
        },
    }


def calculate_full_query_cost(
    sql_tokens: dict[str, Any],
    retrieval_tokens: dict[str, Any],
    synthesis_tokens: dict[str, Any],
) -> dict[str, float]:
    def extract(tokens: dict[str, Any] | None) -> tuple[int, int]:
        tokens = tokens or {}
        return (
            int(tokens.get("input_tokens", tokens.get("input", 0)) or 0),
            int(tokens.get("output_tokens", tokens.get("output", 0)) or 0),
        )

    sql_input, sql_output = extract(sql_tokens)
    retrieval_input, retrieval_output = extract(retrieval_tokens)
    synthesis_input, synthesis_output = extract(synthesis_tokens)

    sql_cost = cost_for_tokens(sql_input, sql_output)
    retrieval_cost = cost_for_tokens(retrieval_input, retrieval_output)
    synthesis_cost = cost_for_tokens(synthesis_input, synthesis_output)
    total = round(sql_cost + retrieval_cost + synthesis_cost, 6)

    return {
        "sql_agent_cost": sql_cost,
        "retrieval_agent_cost": retrieval_cost,
        "synthesis_cost": synthesis_cost,
        "total_cost": total,
        "cost_per_1000_queries": round(total * 1000, 2),
    }


def run_traced_query(orchestrator, question: str) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())[:8]
    log_decision("query_start", question, {}, trace_id)

    if callable(orchestrator):
        result = orchestrator(question)
    else:
        result = orchestrator.invoke({"question": question})

    log_decision(
        "query_complete",
        question,
        {
            "route": result.get("metadata", {}).get("route"),
            "token_breakdown": result.get("metadata", {}).get(
                "token_breakdown",
            ),
            "cost_breakdown": result.get("metadata", {}).get(
                "cost_breakdown",
            ),
        },
        trace_id,
    )

    return result
