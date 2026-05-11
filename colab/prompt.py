from __future__ import annotations

from colab.schema_loader import DatabaseSchema
from colab.db_engine import dialect_label


SYSTEM_PROMPT = (
    "You are an expert Text-to-SQL assistant. "
    "You translate Russian or English natural-language analytics questions into a single SELECT query "
    "in the dialect specified by the user (SQLite, DuckDB, or PostgreSQL).\n"
    "Rules:\n"
    "1. Use ONLY the tables and columns from the provided schema.\n"
    "2. Output exactly one SQL statement. No explanations, no comments, no markdown.\n"
    "3. The query must start with SELECT or WITH and must be read-only.\n"
    "4. Prefer explicit column names over SELECT *.\n"
    "5. If aggregations are needed, give them readable aliases (e.g. SUM(revenue) AS revenue).\n"
    "6. Do NOT use UNION, UNION ALL, INTERSECT, or EXCEPT. A single SELECT (or a single WITH ... SELECT) is enough.\n"
    "7. Do NOT chain multiple statements with `;` — produce only one statement.\n"
    "8. Respect the target dialect: use ILIKE for case-insensitive matches on PostgreSQL/DuckDB; "
    "stick to standard SQL functions when in doubt.\n"
    "9. Use double quotes around identifiers that need quoting (Cyrillic names, reserved words). "
    "Avoid SQL Server's [bracketed identifiers] and MySQL's `backticks`.\n"
    "10. NEVER nest aggregate functions — SUM(x + SUM(y)) is invalid SQL. "
    "If you need to combine two aggregations, use separate aggregations in the SELECT list "
    "or wrap one aggregation in a subquery / CTE.\n"
    "11. Use the FOREIGN KEYS section to navigate between tables. Do not invent direct "
    "joins between tables that are connected only via an intermediate table — follow the "
    "actual FK path (e.g. orders → customers → regions for a 2-hop link).\n"
    "12. If a column you need doesn't exist in the natural table, check the FK targets first "
    "before writing nonsense — invented columns produce 'column does not exist' errors.\n"
    "13. If the question is ambiguous, choose the most natural interpretation and proceed."
)


def build_user_prompt(
    user_query: str,
    schema: DatabaseSchema,
    locale: str | None = None,
) -> str:
    schema_block = schema.render_for_prompt()
    dialect = dialect_label(schema.engine)
    locale_note = ""
    if locale and locale.lower().startswith("ru"):
        locale_note = "Question is in Russian. Translate column names mentally if needed.\n"
    return (
        f"Database dialect: {dialect}\n"
        f"Schema:\n{schema_block}\n\n"
        f"{locale_note}"
        f"Question: {user_query}\n\n"
        f"Return a single SQL query."
    )


def build_chat_messages(
    user_query: str,
    schema: DatabaseSchema,
    locale: str | None = None,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(user_query, schema, locale)},
    ]


# ----------------- Planner → Emitter two-stage pipeline -----------------

PLANNER_SYSTEM_PROMPT = (
    "You are an expert data analyst. Your job is to PLAN how a SQL query should be written, "
    "WITHOUT writing the SQL itself. Given a natural-language question and a database schema, "
    "produce a short structured plan that a junior SQL writer can follow.\n\n"
    "Output format (strict):\n"
    "  INTENT: <one sentence stating what the answer should be>\n"
    "  TABLES: <comma-separated list of tables needed>\n"
    "  JOIN PATH: <list of foreign-key edges to traverse, e.g. orders.client_id -> clients.client_id>\n"
    "  FILTERS: <list of WHERE conditions, e.g. orders.date >= '2024-01-01'; clients.segment = 'B2B'>\n"
    "  GROUP BY: <columns or 'none'>\n"
    "  AGGREGATIONS: <e.g. COUNT(*) AS n; SUM(price * quantity) AS revenue>\n"
    "  ORDER BY: <expr direction or 'none'>\n"
    "  LIMIT: <integer or 'none'>\n"
    "  NOTES: <one short sentence on edge cases — e.g. 'use 2-hop FK orders → clients → regions'>\n\n"
    "Rules:\n"
    "1. Use ONLY tables and columns from the provided schema.\n"
    "2. Follow the FOREIGN KEYS graph — do not invent direct joins.\n"
    "3. Never write SQL syntax — only plan elements.\n"
    "4. Keep the plan short and surgical (≤15 lines)."
)


def build_planner_messages(
    user_query: str,
    schema: DatabaseSchema,
    locale: str | None = None,
) -> list[dict[str, str]]:
    schema_block = schema.render_for_prompt()
    locale_note = "Question is in Russian. Translate column names mentally if needed.\n" if (locale and locale.lower().startswith("ru")) else ""
    user = (
        f"Database dialect: {dialect_label(schema.engine)}\n"
        f"Schema:\n{schema_block}\n\n"
        f"{locale_note}"
        f"Question: {user_query}\n\n"
        f"Produce the plan in the strict format described in the system message."
    )
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


EMITTER_WITH_PLAN_SYSTEM_PROMPT = (
    "You are an expert SQL emitter. Given a question, a database schema, and a STRUCTURED PLAN "
    "produced by a senior analyst, write a single SELECT query in the target dialect that "
    "implements the plan exactly.\n\n"
    "Rules (in order of priority):\n"
    "1. Follow the plan literally — same TABLES, JOIN PATH, FILTERS, GROUP BY, AGGREGATIONS, ORDER BY, LIMIT.\n"
    "2. Output exactly one SQL statement. No prose, no markdown, no comments.\n"
    "3. The query must start with SELECT or WITH and must be read-only.\n"
    "4. Use double quotes around identifiers that need quoting (Cyrillic names, reserved words).\n"
    "5. Never nest aggregate functions — SUM(x + SUM(y)) is invalid.\n"
    "6. Respect the dialect: ILIKE for case-insensitive on Postgres/DuckDB; EXTRACT(YEAR FROM …) etc.\n"
    "7. If a piece of the plan contradicts the schema, prefer the schema."
)


def build_emitter_with_plan_messages(
    user_query: str,
    schema: DatabaseSchema,
    plan: str,
    locale: str | None = None,
) -> list[dict[str, str]]:
    schema_block = schema.render_for_prompt()
    locale_note = "Question is in Russian.\n" if (locale and locale.lower().startswith("ru")) else ""
    user = (
        f"Database dialect: {dialect_label(schema.engine)}\n"
        f"Schema:\n{schema_block}\n\n"
        f"{locale_note}"
        f"Question: {user_query}\n\n"
        f"Plan:\n{plan}\n\n"
        f"Return a single SQL query that implements the plan."
    )
    return [
        {"role": "system", "content": EMITTER_WITH_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
