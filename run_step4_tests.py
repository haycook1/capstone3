from pprint import pprint

from orchestrator import run_orchestrator


TEST_CASES = [
    {
        "name": "SQL-only",
        "question": "How many active projects are there?",
        "route": "sql",
        "sql": True,
        "retrieval": False,
    },
    {
        "name": "Retrieval-only",
        "question": "Summarize the indexed documents.",
        "route": "retrieval",
        "sql": False,
        "retrieval": True,
    },
    {
        "name": "Mixed",
        "question": (
            "Using the project database and indexed documents, identify "
            "active project risks and supporting policy guidance."
        ),
        "route": "both",
        "sql": True,
        "retrieval": True,
    },
]


def run_test(case: dict) -> None:
    result = run_orchestrator(case["question"], include_state=True)
    state = result["metadata"]["state"]

    sql_result = state.get("sql_result")
    retrieval_result = state.get("retrieval_result")
    final_answer = result.get("answer", "")

    print("\n" + "=" * 80)
    print(f"TEST: {case['name']}")
    print(f"QUESTION: {case['question']}")
    print(f"ROUTE: {state.get('route')}")

    print("\nINVOKED TOOLS:")
    pprint(result["metadata"].get("invoked_tools"))

    print("\nSQL RESULT:")
    pprint(sql_result)

    print("\nRETRIEVAL RESULT:")
    pprint(retrieval_result)

    print("\nFINAL ANSWER:")
    print(final_answer)

    assert state.get("route") == case["route"]
    assert (sql_result is not None) == case["sql"]
    assert (retrieval_result is not None) == case["retrieval"]

    for label, tool_result, expected in (
        ("SQL", sql_result, case["sql"]),
        ("Retrieval", retrieval_result, case["retrieval"]),
    ):
        if expected:
            assert tool_result["success"] is True, f"{label} tool failed."

    if case["route"] == "both":
        assert "SQL agent — RDS evidence" in final_answer
        assert "Retrieval agent — OpenSearch document evidence" in final_answer
        assert "RDS query result" in final_answer
        assert result["success"] is True

    print("\nSTATUS: PASS")


def main() -> None:
    for case in TEST_CASES:
        run_test(case)

    print("\n" + "=" * 80)
    print("ALL STEP 4 ROUTING AND SYNTHESIS TESTS PASSED")


if __name__ == "__main__":
    main()
