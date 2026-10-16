import pytest

import agents.sql_agent as sql_agent


@pytest.mark.parametrize(
    ("case_name", "query", "expected_valid"),
    [
        (
            "valid SELECT",
            "SELECT id, name FROM projects;",
            True,
        ),
        (
            "destructive DROP statement",
            "DROP TABLE projects;",
            False,
        ),
        (
            "blocked word inside column name is allowed",
            "SELECT deleted_at FROM projects;",
            True,
        ),
        (
            "stacked query containing blocked keyword",
            "SELECT id FROM projects; DROP TABLE projects;",
            False,
        ),
        (
            "stacked query with two SELECT statements",
            "SELECT id FROM projects; SELECT id FROM clients;",
            False,
        ),
    ],
    ids=[
        "valid-select",
        "destructive-drop",
        "blocked-word-column-name",
        "stacked-query-with-drop",
        "stacked-query-two-selects",
    ],
)
def test_sql_validation_cases(case_name, query, expected_valid):
    result = sql_agent.validate_sql(query)

    assert result["valid"] is expected_valid, (
        f"{case_name} failed: query={query!r}, result={result}"
    )


def test_invalid_sql_never_connects_to_database(monkeypatch):
    connection_attempted = False

    def fail_if_called(*args, **kwargs):
        nonlocal connection_attempted
        connection_attempted = True
        raise AssertionError("Database connection occurred before validation.")

    monkeypatch.setattr(sql_agent.psycopg2, "connect", fail_if_called)

    result = sql_agent.execute_query_safely("DROP TABLE projects;")

    assert result["success"] is False
    assert result["validation"] == "BLOCKED"
    assert connection_attempted is False
