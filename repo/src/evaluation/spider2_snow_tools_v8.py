"""spider2_snow_tools_v8 — Snowflake-side tooling shim for the agent.

Re-exports the existing Snowflake executor + helpers under the user-spec
"snow_tools" name for clarity and future divergence between Spider2-Snow
benchmark needs and the SF lane of Spider2-Lite.

Currently a re-export. Future split-points are flagged with TODO.
"""
from __future__ import annotations

from spider2_sf_executor_v8 import (  # noqa: F401  (re-exports)
    build_sf_executor, _classify_error,
)


# Snowflake dialect quick-checks the agent uses to bias generation:
SNOWFLAKE_QUICK_NOTES = (
    "Snowflake dialect notes:\n"
    "- Identifiers are unquoted=UPPERCASE; quoted identifiers are case-sensitive.\n"
    "- Use DATABASE.SCHEMA.TABLE in fully qualified refs.\n"
    "- Use TRY_CAST, IFF(cond,a,b), COALESCE; avoid CASE WHEN unless needed.\n"
    "- ILIKE is case-insensitive LIKE; use it instead of LOWER(col) LIKE LOWER(...).\n"
    "- QUALIFY <window predicate> can replace a wrapping subquery.\n"
    "- DATE_TRUNC('day'|'month'|'year', ts), DATEDIFF('day', a, b), TO_DATE(...).\n"
    "- For semi-structured: VARIANT, FLATTEN(input => ...), v:field syntax.\n"
    "- FETCH FIRST n ROWS ONLY OR LIMIT n; NO TOP n.\n"
    "- No backticks (BigQuery), no [brackets] (T-SQL).\n"
)


def is_snowflake_specific(sql: str) -> bool:
    """Heuristic — flag clearly non-SF dialect artifacts."""
    if not sql: return False
    s = sql.lower()
    if '`' in sql: return False              # BigQuery backtick → not SF
    if '[' in sql and ']' in sql: return False  # T-SQL brackets → not SF
    return True
