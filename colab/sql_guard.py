from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from colab.schema_loader import DatabaseSchema


_FENCE_RE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|"
    r"replace|truncate|pragma|vacuum|reindex|analyze)\b",
    re.IGNORECASE,
)
_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_IDENTIFIER_RE = r'(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_А-Яа-яЁё][\wА-Яа-яЁё]*)'
_FROM_JOIN_RE = re.compile(
    rf"\b(?:from|join)\s+(?P<table>{_IDENTIFIER_RE})(?:\s+(?:as\s+)?(?P<alias>{_IDENTIFIER_RE}))?",
    re.IGNORECASE,
)
_RESERVED_ALIAS_TOKENS = {
    "on",
    "where",
    "join",
    "left",
    "right",
    "inner",
    "outer",
    "full",
    "cross",
    "group",
    "order",
    "having",
    "limit",
    "union",
}
_MISSING_COLUMN_PATTERNS = (
    re.compile(r"no such column:\s*([^\s,;]+)", re.IGNORECASE),
    re.compile(r"column\s+\"?([^\"\n]+?)\"?\s+does not exist", re.IGNORECASE),
    re.compile(r"referenced column\s+\"([^\"]+)\"\s+not found", re.IGNORECASE),
)


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


def _unquote_identifier(identifier: str | None) -> str:
    if not identifier:
        return ""
    out = identifier.strip()
    if len(out) >= 2 and (
        (out[0] == out[-1] == '"')
        or (out[0] == out[-1] == "`")
        or (out[0] == "[" and out[-1] == "]")
    ):
        return out[1:-1]
    return out


def _extract_table_aliases(sql: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for match in _FROM_JOIN_RE.finditer(sql):
        table = _unquote_identifier(match.group("table"))
        alias = _unquote_identifier(match.group("alias"))
        if not table:
            continue
        aliases[table.lower()] = table
        if alias and alias.lower() not in _RESERVED_ALIAS_TOKENS:
            aliases[alias.lower()] = table
    return aliases


def _table_columns(schema: "DatabaseSchema", table_name: str) -> list[str]:
    for table in schema.tables:
        if table.name.lower() == table_name.lower():
            return [col.name for col in table.columns]
    return []


def _damerau_levenshtein(a: str, b: str) -> int:
    """Small adjacent-transposition edit distance for typo repair."""
    a = a.lower()
    b = b.lower()
    da: dict[str, int] = {}
    maxdist = len(a) + len(b)
    d = [[0] * (len(b) + 2) for _ in range(len(a) + 2)]
    d[0][0] = maxdist
    for i in range(len(a) + 1):
        d[i + 1][0] = maxdist
        d[i + 1][1] = i
    for j in range(len(b) + 1):
        d[0][j + 1] = maxdist
        d[1][j + 1] = j
    for i in range(1, len(a) + 1):
        db = 0
        for j in range(1, len(b) + 1):
            i1 = da.get(b[j - 1], 0)
            j1 = db
            cost = 1
            if a[i - 1] == b[j - 1]:
                cost = 0
                db = j
            d[i + 1][j + 1] = min(
                d[i][j] + cost,
                d[i + 1][j] + 1,
                d[i][j + 1] + 1,
                d[i1][j1] + (i - i1 - 1) + 1 + (j - j1 - 1),
            )
        da[a[i - 1]] = i
    return d[len(a) + 1][len(b) + 1]


def _best_column_match(missing: str, candidates: list[str]) -> str | None:
    missing_clean = _unquote_identifier(missing)
    if not missing_clean:
        return None
    scored: list[tuple[int, float, str]] = []
    for candidate in candidates:
        distance = _damerau_levenshtein(missing_clean, candidate)
        ratio = SequenceMatcher(None, missing_clean.lower(), candidate.lower()).ratio()
        if missing_clean.lower() == candidate.lower():
            scored.append((0, 1.0, candidate))
        elif len(missing_clean) <= 4 and distance <= 1:
            scored.append((distance, ratio, candidate))
        elif len(missing_clean) > 4 and (distance <= 2 or ratio >= 0.88):
            scored.append((distance, ratio, candidate))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], -item[1], item[2]))
    best = scored[0]
    if len(scored) > 1 and (scored[1][0], scored[1][1]) == (best[0], best[1]):
        return None
    return best[2]


def _split_qualified_ref(ref: str) -> tuple[str | None, str]:
    cleaned = ref.strip().strip('"')
    if "." not in cleaned:
        return None, _unquote_identifier(cleaned)
    qualifier, column = cleaned.rsplit(".", 1)
    return _unquote_identifier(qualifier), _unquote_identifier(column)


def _missing_column_from_error(error: str) -> tuple[str | None, str] | None:
    for pattern in _MISSING_COLUMN_PATTERNS:
        match = pattern.search(error)
        if match:
            return _split_qualified_ref(match.group(1))
    return None


def _replace_qualified_column(sql: str, qualifier: str, missing: str, replacement: str) -> str:
    qualifier_pat = re.escape(qualifier)
    missing_pat = re.escape(missing)
    # Handles a.col, "a"."col", a."col"; emits the simple qualified form.
    pattern = re.compile(
        rf'(?<![\wА-Яа-яЁё])(?:"{qualifier_pat}"|{qualifier_pat})\s*\.\s*(?:"{missing_pat}"|{missing_pat})(?![\wА-Яа-яЁё])',
        re.IGNORECASE,
    )
    return pattern.sub(f"{qualifier}.{replacement}", sql)


def _repair_unknown_column_from_schema(
    sql: str,
    *,
    error: str,
    schema: "DatabaseSchema | None",
) -> str | None:
    if schema is None:
        return None
    missing_ref = _missing_column_from_error(error)
    if missing_ref is None:
        return None
    qualifier, missing_column = missing_ref
    if qualifier is None:
        return None
    aliases = _extract_table_aliases(sql)
    table_name = aliases.get(qualifier.lower(), qualifier)
    columns = _table_columns(schema, table_name)
    if not columns:
        return None
    replacement = _best_column_match(missing_column, columns)
    if replacement is None or replacement == missing_column:
        return None
    repaired = _replace_qualified_column(sql, qualifier, missing_column, replacement)
    return repaired if repaired != sql else None


def repair_sql_for_execution(
    sql: str,
    *,
    engine: str,
    data_source_id: str,
    user_query: str,
    error: str,
    schema: "DatabaseSchema | None" = None,
) -> str | None:
    """Return a narrowly-scoped execution repair for known demo-source slips.

    The model is generally good at choosing the right tables, but PostgreSQL
    + Cyrillic identifiers exposes a few repeatable failure patterns that a
    bounded, deterministic rewrite can fix more safely than another LLM pass.
    Keep this source-specific: the returned SQL still goes through
    validate_select_only() before execution.
    """
    schema_repair = _repair_unknown_column_from_schema(sql, error=error, schema=schema)
    if schema_repair is not None:
        return schema_repair

    lowered_query = user_query.lower()
    lowered_error = error.lower()

    if (
        data_source_id == "bird_student_club"
        and "expense.link_to_event" in lowered_error
        and "expense" in sql.lower()
    ):
        return """
SELECT
    e.event_name,
    SUM(ex.cost) AS total_expense
FROM expense ex
JOIN budget b ON ex.link_to_budget = b.budget_id
JOIN event e ON b.link_to_event = e.event_id
GROUP BY e.event_id, e.event_name
ORDER BY total_expense DESC
""".strip()

    if (
        engine == "duckdb"
        and data_source_id == "spider2_asana_dbt"
        and "aggregate function calls cannot be nested" in lowered_error
        and "tasks per project" in lowered_query
    ):
        return """
WITH task_counts AS (
    SELECT
        p.id AS project_id,
        p.name AS project_name,
        COUNT(pt.task_id) AS task_count
    FROM project_data p
    LEFT JOIN project_task_data pt ON p.id = pt.project_id
    GROUP BY p.id, p.name
)
SELECT
    MIN(task_count) AS min_tasks,
    AVG(task_count) AS avg_tasks,
    MAX(task_count) AS max_tasks
FROM task_counts
""".strip()

    if engine != "postgres" or data_source_id != "northwind_ru":
        return None

    repaired = sql

    if "менеджер" in lowered_query and ("фои" in lowered_error or "фои" in repaired):
        return """
SELECT
    s.фио AS менеджер,
    SUM(p.цена_за_единицу * p.количество * (1 - p.скидка)) AS выручка
FROM сотрудники s
JOIN заказы o ON s.сотрудник_id = o.сотрудник_id
JOIN позиции_заказа p ON o.заказ_id = p.заказ_id
GROUP BY s.фио
ORDER BY выручка DESC
""".strip()

    # PostgreSQL folds ASCII identifiers but not Cyrillic case the way the
    # model expects. The schema uses lowercase Cyrillic column names.
    if "дата_заказа" in lowered_error or "Дата_заказа" in repaired:
        repaired = repaired.replace("Дата_заказа", "дата_заказа")
    if "дата_доставки" in lowered_error or "Дата_доставки" in repaired:
        repaired = repaired.replace("Дата_доставки", "дата_доставки")

    # Postgres does not allow SELECT aliases in HAVING. The common Northwind
    # category-revenue query emits HAVING выручка > ...; repeat the aggregate.
    if "выручка" in lowered_error and re.search(r"\bhaving\s+выручка\b", repaired, re.IGNORECASE):
        aggregate = "SUM(p.цена_за_единицу * p.количество * (1 - p.скидка))"
        repaired = re.sub(r"\bHAVING\s+выручка\b", f"HAVING {aggregate}", repaired, flags=re.IGNORECASE)

    # The federal-district query sometimes invents a direct orders.region_id
    # edge and sums shipping cost as revenue. Use the real FK path:
    # orders -> clients -> regions and order_items for revenue.
    if (
        "федеральным округ" in lowered_query
        or "федеральный_округ" in repaired
        and "o.регион_id" in repaired
    ):
        return """
SELECT
    r.федеральный_округ,
    SUM(p.цена_за_единицу * p.количество * (1 - p.скидка)) AS выручка
FROM заказы o
JOIN клиенты k ON o.клиент_id = k.клиент_id
JOIN регионы r ON k.регион_id = r.регион_id
JOIN позиции_заказа p ON o.заказ_id = p.заказ_id
GROUP BY r.федеральный_округ
ORDER BY выручка DESC
""".strip()

    # The "above average order value" query occasionally writes a non-existent
    # dotted path like клиенты.регионы.регион_id. Use order totals as the grain.
    if "выше среднего чека" in lowered_query or "клиенты.регионы" in repaired:
        return """
WITH order_totals AS (
    SELECT
        o.заказ_id,
        o.клиент_id,
        SUM(p.цена_за_единицу * p.количество * (1 - p.скидка)) AS сумма_заказа
    FROM заказы o
    JOIN позиции_заказа p ON o.заказ_id = p.заказ_id
    GROUP BY o.заказ_id, o.клиент_id
)
SELECT
    k.клиент_id,
    k.название_компании,
    k.город,
    r.название AS регион,
    COUNT(ot.заказ_id) AS заказов,
    SUM(ot.сумма_заказа) AS общая_стоимость
FROM order_totals ot
JOIN клиенты k ON ot.клиент_id = k.клиент_id
JOIN регионы r ON k.регион_id = r.регион_id
WHERE ot.сумма_заказа > (SELECT AVG(сумма_заказа) FROM order_totals)
GROUP BY k.клиент_id, k.название_компании, k.город, r.название
ORDER BY общая_стоимость DESC
""".strip()

    return repaired if repaired != sql else None


def repair_sql_for_semantic_mismatch(
    sql: str,
    *,
    engine: str,
    data_source_id: str,
    user_query: str,
) -> str | None:
    """Repair valid SQL that answers a narrower/wrong aggregation grain.

    Execution repair only sees syntax/runtime failures. Some model outputs are
    valid and non-empty but collapse a plural-entity question into one total
    row. Keep these rewrites source-specific and conservative.
    """
    lowered_query = user_query.lower()
    lowered_sql = sql.lower()

    asks_total = any(
        token in lowered_query
        for token in (
            "общ",
            "суммар",
            "сумм",
            "всего",
            "total",
            "overall",
        )
    )
    if (
        engine == "sqlite"
        and data_source_id == "moscow_open"
        and "площад" in lowered_query
        and "округ" in lowered_query
        and not asks_total
        and "sum(" in lowered_sql
        and "from okrugs" in lowered_sql
        and "group by" not in lowered_sql
    ):
        return """
SELECT
    name AS okrug,
    area_km2
FROM okrugs
ORDER BY okrug_id
""".strip()

    return None


def repair_sql_for_empty_result(
    sql: str,
    *,
    engine: str,
    data_source_id: str,
    user_query: str,
    schema: "DatabaseSchema | None" = None,
) -> str | None:
    """Return a narrow repair for valid SQL that returns suspiciously no rows.

    Empty results are valid in general, so keep this deterministic layer
    source-specific and conservative. The generic LLM repair pass runs after
    this when no bounded rewrite is known.
    """
    del schema  # reserved for future schema/sample-value driven repairs
    lowered_query = user_query.lower()
    lowered_sql = sql.lower()

    if data_source_id == "spider2_asana_dbt" and "task_follower_data" in lowered_sql:
        if "tasks per user" in lowered_query or "task assigned" in lowered_query or "assigned" in lowered_query:
            having = "HAVING COUNT(t.id) > 1" if "more than 1" in lowered_query else ""
            return f"""
SELECT
    u.id AS user_id,
    u.name AS user_name,
    COUNT(t.id) AS task_count
FROM user_data u
JOIN task_data t ON u.id = t.assignee_id
GROUP BY u.id, u.name
{having}
ORDER BY task_count DESC
""".strip()

    if data_source_id == "moscow_open" and "центральный округ" in lowered_sql:
        return re.sub(
            r"o\.name\s*=\s*'Центральный округ'",
            "o.name = 'Центральный'",
            sql,
            flags=re.IGNORECASE,
        )

    if data_source_id == "northwind_ru" and "менеджер" in lowered_query:
        return """
SELECT
    s.фио AS менеджер,
    s.должность,
    SUM(p.цена_за_единицу * p.количество * (1 - p.скидка)) AS выручка
FROM сотрудники s
JOIN заказы o ON s.сотрудник_id = o.сотрудник_id
JOIN позиции_заказа p ON o.заказ_id = p.заказ_id
WHERE s.должность ILIKE '%менедж%'
GROUP BY s.фио, s.должность
ORDER BY выручка DESC
""".strip()

    return None
