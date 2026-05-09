"""spider2_snow_prompting_v10 — H1-aware prompts.

Diff from v9 (`spider2_sf_prompting_v8`):
  - Schema rendered via `spider2_snow_schema_render_v10.render_subset_v10`
    — identifiers as canonical unquoted DB.SCHEMA.TABLE (no double-quote
    blob, no `table_fullname`).
  - Reinforced rule block forbidding 4-part identifiers and segment
    duplication.
"""
from __future__ import annotations

import textwrap

from spider2_sf_schema_index_v8 import SfSchemaIndex
from spider2_snow_schema_render_v10 import render_subset_v10


_SF_RULES_V10 = textwrap.dedent('''
You generate Snowflake SQL. STRICT rules:

1. **3-part identifiers ONLY**: write `DB.SCHEMA.TABLE`. Never 4-part.
   Never repeat any segment. Never wrap segments in extra quotes —
   the SCHEMA block already shows the canonical form. If a column is
   case-sensitive, double-quote that single segment, e.g.
   `MY_DB.PUBLIC."CamelCase Col"`. Do NOT double-quote the whole
   identifier blob like `"MY_DB.PUBLIC.TABLE"`.
2. **Use ONLY identifiers shown in the SCHEMA block.** If a needed
   column isn't there, pick the closest one — DO NOT invent names.
3. **No BigQuery backticks**, no T-SQL brackets.
4. **Snowflake date/time**: `DATEDIFF(DAY, d1, d2)` (PART, start, end),
   `DATEADD(DAY, 1, d)`, `DATE_TRUNC('DAY', d)`, `TO_DATE(s,'YYYYMMDD')`.
5. **Repeated/array fields**: use `LATERAL FLATTEN(input => arr) AS f`
   and `f.value` to access the element. Do NOT use BigQuery `UNNEST(arr)`.
6. **Cast**: `TRY_CAST(x AS T)` — Snowflake has no `SAFE_CAST`.
7. **Case-insensitive match**: `ILIKE`. No `REGEXP_CONTAINS`.
8. **Window / QUALIFY**: `QUALIFY ROW_NUMBER() OVER (...) = 1` is fine.
9. **Single statement**: emit exactly one query. No `BEGIN`/`USE`/`CALL`.
10. Output: SQL only. No markdown fence is required if the prompt says
    "SQL:". No commentary, no `SQL:` prefix in the body.
''').strip()


def direct_prompt_v10(question: str, idx: SfSchemaIndex,
                          selected_keys: list[str], *,
                          max_cols: int = 22) -> str:
    schema_text = render_subset_v10(idx, selected_keys, max_cols=max_cols,
                                          include_samples=True)
    return textwrap.dedent(f'''
    {_SF_RULES_V10}

    SCHEMA:
    {schema_text}

    Question: {question}
    SQL:
    ''').strip()


def retrieval_prompt_v10(question: str, idx: SfSchemaIndex,
                              selected_keys: list[str], *,
                              max_cols: int = 22) -> str:
    schema_text = render_subset_v10(idx, selected_keys, max_cols=max_cols,
                                          include_samples=True)
    return textwrap.dedent(f'''
    {_SF_RULES_V10}

    Use ONLY the tables and columns below. Do not invent identifiers.

    SCHEMA:
    {schema_text}

    Question: {question}
    SQL:
    ''').strip()


def cte_prompt_v10(question: str, idx: SfSchemaIndex,
                         selected_keys: list[str], *,
                         max_cols: int = 22) -> str:
    schema_text = render_subset_v10(idx, selected_keys, max_cols=max_cols,
                                          include_samples=True)
    return textwrap.dedent(f'''
    {_SF_RULES_V10}

    Decompose into named CTEs (`WITH step1 AS (...), step2 AS (...) SELECT ...`).
    Each CTE = one logical step. Final SELECT consumes the CTEs.

    SCHEMA:
    {schema_text}

    Question: {question}
    SQL:
    ''').strip()


def repair_prompt_v10(question: str, schema_text: str, broken_sql: str,
                          error_msg: str) -> str:
    return textwrap.dedent(f'''
    Your previous Snowflake SQL was rejected. Output ONLY the corrected
    SQL — no markdown, no commentary.

    STRICT IDENTIFIER RULES:
    - 3-part names only: DB.SCHEMA.TABLE. Never 4-part.
    - Never repeat any identifier segment.
    - Never wrap a multi-part identifier in a single pair of double quotes.
    - Use only tables/columns from the SCHEMA. Do not invent names.

    SCHEMA:
    {schema_text}

    QUESTION: {question}

    BROKEN_SQL:
    {broken_sql}

    SNOWFLAKE_ERROR:
    {error_msg[:600]}

    FIXED_SQL:
    ''').strip()
