from __future__ import annotations

import uuid

from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.retrieval_agent import retrieval_agent as retrieval_tool
from agents.sql_agent import sql_tool

from tokenomics_logger import (
    clear_trace_events,
    get_trace_events,
    log_stage,
    summarize_trace,
)

Route = Literal["sql", "retrieval", "both"]
ToolResult = dict[str, Any]
ToolCallable = Callable[..., ToolResult]


class OrchestratorState(TypedDict, total=False):
    question: str
    route: Route
    sql_result: ToolResult | None
    retrieval_result: ToolResult | None
    final_answer: str
    sources: list[Any]
    token_usage: dict[str, Any]
    trace_id: str


SQL_MARKERS = (
    "rds",
    "database",
    "sql",
    "client",
    "consultant",
    "invoice",
    "payment",
    "project count",
    "how many",
    "number of",
    "list projects",
    "active projects",
    "active project",
    "billing",
)

RETRIEVAL_MARKERS = (
    "document",
    "documents",
    "opensearch",
    "policy",
    "guidance",
    "indexed",
    "summarize",
    "summarise",
    "supporting evidence",
    "risk guidance",
    "playbook",
    "migration",
    "rollback",
    "communication",
)


def classify_node(state: OrchestratorState) -> dict[str, Route]:
    question = state["question"].lower()
    trace_id = state.get("trace_id")

    needs_sql = any(marker in question for marker in SQL_MARKERS)
    needs_retrieval = any(marker in question for marker in RETRIEVAL_MARKERS)

    if needs_sql and needs_retrieval:
        route: Route = "both"
    elif needs_sql:
        route = "sql"
    elif needs_retrieval:
        route = "retrieval"
    else:
        route = "both"

    log_stage(
        "classification",
        state["question"],
        trace_id,
        {"used_claude": False, "route": route},
    )

    return {"route": route}

def route_targets(state: OrchestratorState) -> list[str]:
    if state["route"] == "both":
        return ["sql_agent", "retrieval_agent"]

    return [f"{state['route']}_agent"]


def safe_invoke(
    tool: ToolCallable,
    question: str,
    trace_id: str,
) -> ToolResult:
    required_keys = {"success", "answer", "sources", "metadata"}

    try:
        result = tool(question, trace_id=trace_id)

        if not isinstance(result, dict):
            raise TypeError("Tool result must be a dictionary.")

        missing_keys = required_keys - set(result)
        if missing_keys:
            raise ValueError(f"Missing standardized keys: {sorted(missing_keys)}")

        return result

    except Exception as exc:
        return {
            "success": False,
            "answer": f"Tool execution failed: {type(exc).__name__}.",
            "sources": [],
            "metadata": {"error_type": type(exc).__name__},
        }

def sql_node(state: OrchestratorState) -> dict[str, ToolResult]:
    return {
        "sql_result": safe_invoke(
            sql_tool,
            state["question"],
            state["trace_id"],
        )
    }



def retrieval_node(state: OrchestratorState) -> dict[str, ToolResult]:
    return {
        "retrieval_result": safe_invoke(
            retrieval_tool,
            state["question"],
            state["trace_id"],
        )
    }

def normalize_sources(result: ToolResult) -> list[Any]:
    sources = result.get("sources", [])

    if isinstance(sources, list):
        return sources

    return [sources] if sources else []


def deduplicate_sources(sources: list[Any]) -> list[Any]:
    unique_sources = []
    seen = set()

    for source in sources:
        source_key = repr(source)

        if source_key not in seen:
            seen.add(source_key)
            unique_sources.append(source)

    return unique_sources


def format_agent_section(label: str, result: ToolResult) -> str:
    answer = result.get("answer") or "No answer was returned."
    sources = normalize_sources(result)

    if sources:
        source_text = "; ".join(str(source) for source in sources)
    else:
        source_text = "none returned"

    return f"{label}:\n{answer}\nSources: {source_text}"


def synthesis_node(state: OrchestratorState) -> dict[str, Any]:
    log_stage(
        "synthesis",
        state["question"],
        state.get("trace_id"),
        {
            "used_claude": False,
            "inputs": [
                name
                for name in ("sql_result", "retrieval_result")
                if state.get(name) is not None
            ],
        },
    )
    sections = []
    all_sources = []
    token_usage = {}

    sql_result = state.get("sql_result")
    if sql_result is not None:
        sections.append(
            format_agent_section("SQL agent — RDS evidence", sql_result)
        )
        all_sources.extend(normalize_sources(sql_result))
        token_usage["sql"] = sql_result.get("metadata", {}).get("token_usage")

    retrieval_result = state.get("retrieval_result")
    if retrieval_result is not None:
        sections.append(
            format_agent_section(
                "Retrieval agent — OpenSearch document evidence",
                retrieval_result,
            )
        )
        all_sources.extend(normalize_sources(retrieval_result))
        token_usage["retrieval"] = retrieval_result.get(
            "metadata",
            {},
        ).get("token_usage")

    return {
        "final_answer": "\n\n".join(sections),
        "sources": deduplicate_sources(all_sources),
        "token_usage": token_usage,
    }


def build_graph():
    graph = StateGraph(OrchestratorState)

    graph.add_node("classify", classify_node)
    graph.add_node("sql_agent", sql_node)
    graph.add_node("retrieval_agent", retrieval_node)
    graph.add_node("synthesis", synthesis_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_targets)
    graph.add_edge("sql_agent", "synthesis")
    graph.add_edge("retrieval_agent", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()


_GRAPH = build_graph()


def run_orchestrator(
    question: str,
    include_state: bool = False,
    include_trace: bool = False,
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())[:8]
    clear_trace_events(trace_id)

    state = _GRAPH.invoke(
        {
            "question": question,
            "trace_id": trace_id,
        }
    )

    sql_result = state.get("sql_result")
    retrieval_result = state.get("retrieval_result")
    events = get_trace_events(trace_id)
    summary = summarize_trace(events)

    tool_results = {
        "sql": sql_result,
        "retrieval": retrieval_result,
    }

    invoked_tools = {
        name: result is not None
        for name, result in tool_results.items()
    }

    tool_success = {
        name: bool(result and result.get("success"))
        for name, result in tool_results.items()
        if result is not None
    }

    metadata = {
        "trace_id": trace_id,
        "route": state.get("route"),
        "invoked_tools": invoked_tools,
        "tool_success": tool_success,
        "token_usage": state.get("token_usage", {}),
        "token_breakdown": summary["token_breakdown"],
        "cost_breakdown": summary["cost_breakdown"],
    }

    if include_state:
        metadata["state"] = {
            "route": state.get("route"),
            "sql_result": sql_result,
            "retrieval_result": retrieval_result,
            "final_answer": state.get("final_answer"),
        }

    if include_trace:
        metadata["trace_events"] = events


    return {
        "success": bool(tool_success) and all(tool_success.values()),
        "answer": state.get("final_answer", ""),
        "sources": state.get("sources", []),
        "metadata": metadata,
    }
