from dataclasses import dataclass
import re
from typing import List


BLOCKED_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "CREATE", "GRANT", "REVOKE", "MERGE",
    "REPLACE",
}


@dataclass
class ValidationResult:
    allowed: bool
    reason: str
    statements: int


def _split_statements(sql: str) -> List[str]:
    statements = []
    current = []
    quote = None
    line_comment = False
    block_comment = False
    i = 0

    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if line_comment:
            current.append(char)
            if char == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                block_comment = False
                i += 2
            else:
                i += 1
            continue

        if quote:
            current.append(char)
            if char == quote:
                if next_char == quote:
                    current.append(next_char)
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if char == "-" and next_char == "-":
            current.extend([char, next_char])
            line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            current.extend([char, next_char])
            block_comment = True
            i += 2
            continue

        if char in ("'", '"', "`"):
            quote = char
            current.append(char)
            i += 1
            continue

        if char == ";":
            text = "".join(current).strip()
            if text:
                statements.append(text)
            current = []
        else:
            current.append(char)

        i += 1

    text = "".join(current).strip()
    if text:
        statements.append(text)

    return statements


def _mask_comments_and_literals(sql: str) -> str:
    result = []
    quote = None
    line_comment = False
    block_comment = False
    i = 0

    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if line_comment:
            result.append("\n" if char == "\n" else " ")
            if char == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            result.append("\n" if char == "\n" else " ")
            if char == "*" and next_char == "/":
                result.append(" ")
                block_comment = False
                i += 2
            else:
                i += 1
            continue

        if quote:
            result.append(" ")
            if char == quote:
                if next_char == quote:
                    result.append(" ")
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if char == "-" and next_char == "-":
            result.extend([" ", " "])
            line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            result.extend([" ", " "])
            block_comment = True
            i += 2
            continue

        if char in ("'", '"', "`"):
            quote = char
            result.append(" ")
        else:
            result.append(char)

        i += 1

    return "".join(result)


def validate_sql(sql: str) -> ValidationResult:
    if not isinstance(sql, str) or not sql.strip():
        return ValidationResult(False, "SQL is empty", 0)

    statements = _split_statements(sql)

    if len(statements) != 1:
        return ValidationResult(
            False,
            "Stacked queries are not allowed",
            len(statements),
        )

    masked = _mask_comments_and_literals(statements[0])

    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", masked, re.IGNORECASE):
            return ValidationResult(
                False,
                f"Blocked SQL keyword: {keyword}",
                1,
            )

    if not re.match(r"^\s*(SELECT|WITH)\b", masked, re.IGNORECASE):
        return ValidationResult(
            False,
            "Only SELECT statements are allowed",
            1,
        )

    return ValidationResult(True, "SQL passed validation", 1)
