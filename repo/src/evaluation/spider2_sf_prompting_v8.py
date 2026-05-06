"""spider2_sf_prompting_v8 — Snowflake-specific prompt builders.

Mirrors `spider2_bq_prompting_v8` but with Snowflake dialect rules:
  - identifiers: `DB.SCHEMA.TABLE`, double-quote when case-sensitive
  - DATEDIFF / DATEADD: Snowflake order (`DATEDIFF(DAY, d1, d2)`)
  - FLATTEN / LATERAL FLATTEN instead of UNNEST
  - TRY_CAST instead of SAFE_CAST
  - no _TABLE_SUFFIX
  - ILIKE for case-insensitive match
  - QUALIFY supported
"""
from __future__ import annotations

import textwrap

from spider2_sf_schema_index_v8 import (
    SfSchemaIndex, render_table_block, render_subset,
)


_SF_RULES = textwrap.dedent('''
You generate Snowflake SQL. Hard rules — your output MUST follow:

1. **Fully-qualified names**: write `DB.SCHEMA.TABLE`. Do NOT use BigQuery
   backticks. Quote identifiers with **double quotes** when they are
   case-sensitive or contain special characters: `"DB"."SCHEMA"."Order Items"`.
   Snowflake uppercases unquoted identifiers — match the case in the SCHEMA
   block exactly.
2. **Date functions**: use `DATEDIFF(DAY, d1, d2)` (note arg order),
   `DATEADD(DAY, 1, d)`, `DATE_TRUNC('MONTH', d)`, `EXTRACT(YEAR FROM d)`,
   `TO_DATE(s, 'YYYYMMDD')`. Do NOT use BigQuery `DATE_DIFF`/`DATE_ADD`
   (Snowflake's `DATE_DIFF` exists but with different argument order).
3. **Repeated/array fields**: use `FLATTEN(input => arr)` or
   `LATERAL FLATTEN(input => arr) f` and access via `f.value`. Do NOT
   use BigQuery `UNNEST(arr)` syntax.
4. **Cast**: use `TRY_CAST(x AS T)` for safe coercion (Snowflake does not
   have BigQuery's `SAFE_CAST`).
5. **No table wildcards**: Snowflake does not support BigQuery's
   `_TABLE_SUFFIX` / `events_*` patterns. Reference each table explicitly,
   or `UNION ALL` between them, or use a CTE that builds the union.
6. **Case-insensitive match**: use `ILIKE 'pattern%'` or `LOWER(x) =
   LOWER('y')`. Do NOT use BigQuery `REGEXP_CONTAINS`.
7. **VARIANT / OBJECT / ARRAY**: access nested fields with `:field_name`
   or `:["field name"]`. Cast results with `::TYPE`. Example:
   `event:user.id::STRING`.
8. **Aggregations**: `COUNT(DISTINCT x)`, `SUM`, `AVG`,
   `APPROX_COUNT_DISTINCT(x)`. Always alias outputs.
9. **Window / QUALIFY**: `QUALIFY ROW_NUMBER() OVER (...) = 1` is
   supported by Snowflake — useful for top-N-per-group patterns.
10. **Single statement**: emit exactly one query. No `BEGIN`/`USE`/`CALL`
    statements; no semicolon-separated multi-statement.
11. **Schema fidelity**: only reference tables and columns explicitly
    listed in the SCHEMA block. If a needed column is missing, pick the
    closest one — DO NOT invent identifiers.
12. Output: SQL only. No markdown, no commentary, no `SQL:` prefix.
''').strip()


def _docs_block(bundle, max_chars: int = 1200) -> str:
    docs = getattr(bundle, 'docs', None) or []
    if not docs: return ''
    lines = ['DOMAIN KNOWLEDGE (use only if relevant):']
    used = 0
    for d in docs:
        chunk = (f'## {d.title} ({d.source})\n{d.text}'
                  if d.title else f'({d.source})\n{d.text}')
        if used + len(chunk) > max_chars: break
        lines.append(chunk); used += len(chunk)
    return '\n\n'.join(lines)


def _columns_block(bundle, max_lines: int = 16) -> str:
    cols = getattr(bundle, 'columns', None) or []
    if not cols: return ''
    lines = ['HIGH-RELEVANCE COLUMNS:']
    for c in cols[:max_lines]:
        sample = (' /* eg. ' + ', '.join(c.sample_values[:2]) + ' */'
                   if getattr(c, 'sample_values', None) else '')
        lines.append(f'  "{c.fq_name}".{c.column_name} {c.dtype}{sample}')
    return '\n'.join(lines)


def direct_prompt(question: str, idx: SfSchemaIndex, selected_keys: list[str],
                    *, max_cols: int = 25) -> str:
    schema_text = render_subset(idx, selected_keys, max_cols=max_cols,
                                  include_samples=True)
    return textwrap.dedent(f'''
    {_SF_RULES}

    SCHEMA:
    {schema_text}

    Question: {question}
    SQL:
    ''').strip()


def retrieval_prompt(question: str, idx: SfSchemaIndex, selected_keys: list[str],
                       *, columns_block: str = '', docs_block: str = '',
                       max_cols: int = 25) -> str:
    schema_text = render_subset(idx, selected_keys, max_cols=max_cols,
                                  include_samples=True)
    parts = [_SF_RULES, '\nSCHEMA:', schema_text]
    if columns_block: parts.append(columns_block)
    if docs_block: parts.append(docs_block)
    parts.append(f'Question: {question}')
    parts.append('SQL:')
    return '\n\n'.join(parts).strip()


def cte_prompt(question: str, idx: SfSchemaIndex, selected_keys: list[str],
                 *, docs_block: str = '', max_cols: int = 25) -> str:
    schema_text = render_subset(idx, selected_keys, max_cols=max_cols,
                                  include_samples=True)
    return textwrap.dedent(f'''
    {_SF_RULES}

    Decompose the answer into named CTEs (`WITH step1 AS (...), step2 AS (...) SELECT ...`).
    Each CTE computes ONE logical step. Final SELECT consumes the CTEs.

    SCHEMA:
    {schema_text}

    {docs_block}

    Question: {question}
    SQL:
    ''').strip()


def repair_prompt(question: str, schema_text: str, broken_sql: str,
                    error_msg: str) -> str:
    return textwrap.dedent(f'''
    You wrote Snowflake SQL that the engine rejected. Fix it. Output only
    the corrected SQL — no markdown, no explanation, no `SQL:` prefix.

    SNOWFLAKE RULES:
    - Identifiers: `DB.SCHEMA.TABLE`; double-quote when case-sensitive.
    - DATEDIFF(DAY, d1, d2) — note arg order; FLATTEN, not UNNEST;
      TRY_CAST, not SAFE_CAST. No _TABLE_SUFFIX.
    - Use only tables/columns from the SCHEMA — do not invent names.

    SCHEMA:
    {schema_text}

    QUESTION: {question}

    ORIGINAL_SQL:
    {broken_sql}

    SNOWFLAKE_ERROR:
    {error_msg[:600]}

    FIXED_SQL:
    ''').strip()
