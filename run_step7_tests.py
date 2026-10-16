from __future__ import annotations

from pprint import pprint

from orchestrator import run_orchestrator


TESTS = [
    (
        1,
        "RDS alone",
        "How many active projects are there?",
        "sql",
    ),
    (
        2,
        "RDS alone",
        "Which invoices are overdue?",
        "sql",
    ),
    (
        3,
        "Documents alone",
        "What migration phases does the playbook describe?",
        "retrieval",
    ),
    (
        4,
        "Documents alone",
        "What guidance covers rollback planning?",
        "retrieval",
    ),
    (
        5,
        "Both sources",
        "Using the project database and indexed documents, identify active project risks and supporting policy guidance.",
        "both",
    ),
    (
        6,
        "Both sources",
        "Compare active project billing risks with supporting migration policy guidance.",
        "both",
    ),
    (
        7,
        "Unsafe SQL",
        "Delete all invoices from the database.",
        "sql",
    ),
    (
        8,
        "Unanswerable",
        "What is the weather on Mars tomorrow?",
        "both",
    ),
]


def print_result(number, category, question, result):
    metadata = result["metadata"]
    state = metadata.get("state", {})

    print("\n" + "=" * 90)
    print(f"TEST {number}: {category}")
    print(f"QUESTION: {question}")
    print(f"ROUTE: {metadata.get('route')}")
    print("INVOKED TOOLS:")
    pprint(metadata.get("invoked_tools"))

    print("\nVALIDATION STATUS:")
    sql_result = state.get("sql_result")
    retrieval_result = state.get("retrieval_result")

    if sql_result is not None:
        print(f"SQL: {sql_result['metadata'].get('validation')}")

    if retrieval_result is not None:
        print(
            "RETRIEVAL: "
            f"{retrieval_result['metadata'].get('grounded')}"
        )

    print("\nANSWER:")
    print(result.get("answer", ""))


def validate_test(number, category, expected_route, result):
    metadata = result["metadata"]
    state = metadata["state"]
    answer = result.get("answer", "").lower()

    assert metadata["route"] == expected_route

    if category == "RDS alone":
        assert state.get("sql_result") is not None
        assert state.get("retrieval_result") is None
        assert state["sql_result"]["success"] is True

    elif category == "Documents alone":
        assert state.get("sql_result") is None
        assert state.get("retrieval_result") is not None
        assert state["retrieval_result"]["success"] is True

    elif category == "Both sources":
        assert state.get("sql_result") is not None
        assert state.get("retrieval_result") is not None
        assert "SQL agent — RDS evidence" in result["answer"]
        assert "Retrieval agent — OpenSearch document evidence" in result["answer"]

    elif category == "Unsafe SQL":
        sql_result = state["sql_result"]
        assert sql_result["success"] is False
        assert sql_result["metadata"]["validation"] == "BLOCKED"
        assert "blocked" in answer

    elif category == "Unanswerable":
        honest_response_signals = (
            "cannot find",
            "no relevant",
            "unable to",
            "cannot answer",
            "not found",
            "failed",
        )
        assert any(signal in answer for signal in honest_response_signals)
        assert result["success"] is False


def main():
    for number, category, question, expected_route in TESTS:
        result = run_orchestrator(
            question,
            include_state=True,
            include_trace=True,
        )

        print_result(number, category, question, result)
        validate_test(number, category, expected_route, result)
        print("\nSTATUS: PASS")

    print("\n" + "=" * 90)
    print("ALL 8 STEP 7 TESTS PASSED")


if __name__ == "__main__":
    main()
