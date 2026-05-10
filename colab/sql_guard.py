from __future__ import annotations

import re
from dataclasses import dataclass


_FENCE_RE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|"
    r"replace|truncate|pragma|vacuum|reindex|analyze)\b",
    re.IGNORECASE,
)
_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


@dataclass
class GuardResult:
    ok: bool
    sql: str
    reason: str | None = None


def _strip_markdown(sql: str) -> str:
    match = _FENCE_RE.search(sql)
    if match:
        return match.group(1).strip()
    return sql.strip()


def _strip_trailing_semicolon(sql: str) -> str:
    return sql.rstrip().rstrip(";").strip()


def extract_sql(model_output: str) -> str:
    """Pull a single SQL statement out of model output (handles fences + prefixes)."""
    if not model_output:
        return ""
    cleaned = _strip_markdown(model_output)
    lower = cleaned.lower()
    for marker in ("sql:", "query:", "answer:"):
        idx = lower.find(marker)
        if idx >= 0:
            cleaned = cleaned[idx + len(marker) :].strip()
            lower = cleaned.lower()
    select_idx = lower.find("select")
    with_idx = lower.find("with")
    candidates = [i for i in (select_idx, with_idx) if i >= 0]
    if candidates:
        cleaned = cleaned[min(candidates):]
    cleaned = _strip_trailing_semicolon(cleaned)
    return cleaned.strip()


def validate_select_only(sql: str) -> GuardResult:
    if not sql or not sql.strip():
        return GuardResult(ok=False, sql=sql, reason="empty SQL")

    stripped = _COMMENT_BLOCK_RE.sub(" ", sql)
    stripped = _COMMENT_LINE_RE.sub(" ", stripped)
    stripped_lower = stripped.lower().strip()

    if not (stripped_lower.startswith("select") or stripped_lower.startswith("with")):
        return GuardResult(ok=False, sql=sql, reason="must start with SELECT or WITH")

    semis = [i for i, ch in enumerate(stripped) if ch == ";"]
    for pos in semis:
        rest = stripped[pos + 1:].strip()
        if rest:
            return GuardResult(ok=False, sql=sql, reason="multiple statements not allowed")

    if _FORBIDDEN_RE.search(stripped):
        return GuardResult(ok=False, sql=sql, reason="forbidden keyword detected")

    return GuardResult(ok=True, sql=_strip_trailing_semicolon(sql))


def apply_row_limit(sql: str, row_limit: int) -> tuple[str, bool]:
    """Append LIMIT if the SQL has none. Returns (sql, limit_was_added)."""
    if row_limit <= 0:
        return sql, False
    cleaned = _strip_trailing_semicolon(sql)
    lower = cleaned.lower()
    if re.search(r"\blimit\b\s+\d+", lower):
        return cleaned, False
    return f"{cleaned}\nLIMIT {row_limit}", True
