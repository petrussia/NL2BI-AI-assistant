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
