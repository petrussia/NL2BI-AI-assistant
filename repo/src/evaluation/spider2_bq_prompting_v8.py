"""spider2_bq_prompting_v8 — BigQuery-specific prompt construction.

Three prompt builders:
  - direct_prompt:  C0 candidate, compact schema only, BQ rules in system
  - retrieval_prompt: C1 candidate, retrieved tables + columns + doc chunks
  - cte_prompt:    C2 candidate, asks for WITH/CTE decomposition

All three include the same BigQuery system rules (backticks, _TABLE_SUFFIX,
DATE_DIFF not DATEDIFF, UNNEST for repeated, etc.) so the model has a
single mental model. The rules section is gold-free — built only from
documented BigQuery Standard SQL.
"""
from __future__ import annotations

import textwrap

from spider2_bq_schema_index_v8 import (
    BqSchemaIndex, render_table_block, render_subset,
)
from spider2_bq_retrieval_v8 import RetrievalBundle


_BQ_RULES = textwrap.dedent('''
You generate BigQuery Standard SQL. Hard rules — your output MUST follow:

1. **Backtick fully-qualified table names**: write
   `` `project.dataset.table` ``. Never use unquoted dashes, e.g.
   `bigquery-public-data` MUST be wrapped: `` `bigquery-public-data.x.y` ``.
2. **Wildcard tables**: a table family `foo_YYYYMMDD` should be queried as
   `` `proj.ds.foo_*` `` and filtered with `_TABLE_SUFFIX BETWEEN '20210101' AND '20210107'`.
3. **Date functions**: use `DATE_DIFF(d2, d1, DAY)`, `DATE_TRUNC(d, MONTH)`,
   `DATE_ADD(d, INTERVAL 1 DAY)`, `EXTRACT(YEAR FROM d)`, `PARSE_DATE('%Y%m%d', s)`.
   Do NOT use `DATEDIFF`, `DATEADD`, `STRFTIME`, `TO_DATE` or other dialects.
4. **Repeated/STRUCT fields**: use `UNNEST(arr) AS x` and dotted access
   `x.field`. Cross-join `, UNNEST(arr) AS x` only when needed.
5. **Aggregations**: `COUNT(DISTINCT x)`, `SUM`, `AVG`, `APPROX_COUNT_DISTINCT`.
   Always alias outputs (`AS revenue`, `AS n_users`).
6. **Limits**: never emit `LIMIT 0`. Use `LIMIT N` only when the question
   asks for top-K.
7. **String comparisons**: prefer `LOWER(x) = LOWER('y')` or `REGEXP_CONTAINS(x, ...)`
   for fuzzy matches. Quote string literals with single quotes.
8. **Single statement**: emit exactly one query, no `DECLARE` / `BEGIN` /
   semicolons separating multiple statements. Multi-step logic goes in CTEs.
9. **Schema fidelity**: only use tables and columns explicitly listed in
   the SCHEMA block. If a needed column is missing, pick the closest one
   from the SCHEMA — DO NOT invent column names.
10. Output: SQL only. No markdown, no commentary, no `SQL:` prefix.
''').strip()


def _docs_block(bundle: RetrievalBundle, max_chars: int = 1200) -> str:
    if not bundle.docs: return ''
    lines: list[str] = ['DOMAIN KNOWLEDGE (use only if relevant):']
    used = 0
    for d in bundle.docs:
        chunk = (f'## {d.title} ({d.source})\n{d.text}'
                  if d.title else f'({d.source})\n{d.text}')
        if used + len(chunk) > max_chars: break
        lines.append(chunk); used += len(chunk)
    return '\n\n'.join(lines)


def _columns_block(bundle: RetrievalBundle, max_lines: int = 16) -> str:
    if not bundle.columns: return ''
    lines = ['HIGH-RELEVANCE COLUMNS:']
    for c in bundle.columns[:max_lines]:
        sample = (' /* eg. ' + ', '.join(c.sample_values[:2]) + ' */'
                   if c.sample_values else '')
        lines.append(f'  `{c.fq_name}`.{c.column_name} {c.dtype}{sample}')
    return '\n'.join(lines)


def _joins_block(bundle: RetrievalBundle) -> str:
    if not bundle.joins: return ''
    return 'JOIN HINTS:\n' + '\n'.join(bundle.joins)


def direct_prompt(question: str, idx: BqSchemaIndex, bundle: RetrievalBundle,
                    *, max_cols: int = 25) -> str:
    schema_text = render_subset(idx, bundle.selected_keys, max_cols=max_cols,
                                  include_samples=True)
    return textwrap.dedent(f'''
    {_BQ_RULES}

    SCHEMA:
    {schema_text}

    Question: {question}
    SQL:
    ''').strip()


def retrieval_prompt(question: str, idx: BqSchemaIndex,
                       bundle: RetrievalBundle, *,
                       max_cols: int = 25) -> str:
    schema_text = render_subset(idx, bundle.selected_keys, max_cols=max_cols,
                                  include_samples=True)
    docs = _docs_block(bundle)
    cols = _columns_block(bundle)
    joins = _joins_block(bundle)
    parts = [_BQ_RULES, '\nSCHEMA:', schema_text]
    if cols: parts.append(cols)
    if joins: parts.append(joins)
    if docs: parts.append(docs)
    parts.append(f'Question: {question}')
    parts.append('SQL:')
    return '\n\n'.join(parts).strip()


def cte_prompt(question: str, idx: BqSchemaIndex, bundle: RetrievalBundle,
                 *, max_cols: int = 25) -> str:
    schema_text = render_subset(idx, bundle.selected_keys, max_cols=max_cols,
                                  include_samples=True)
    docs = _docs_block(bundle)
    return textwrap.dedent(f'''
    {_BQ_RULES}

    Decompose the answer into named CTEs (`WITH step1 AS (...), step2 AS (...) SELECT ...`).
    Each CTE computes ONE logical step. Final SELECT consumes the CTEs.

    SCHEMA:
    {schema_text}

    {docs}

    Question: {question}
    SQL:
    ''').strip()


def repair_prompt(question: str, schema_text: str, broken_sql: str,
                    error_msg: str) -> str:
    """Repair prompt that gets the exact BQ error message."""
    return textwrap.dedent(f'''
    You wrote BigQuery SQL that BigQuery rejected. Fix it. Output only the
    corrected SQL — no markdown, no explanation, no `SQL:` prefix.

    BIGQUERY RULES:
    - Backtick `project.dataset.table`; wildcard tables use _TABLE_SUFFIX.
    - Use DATE_DIFF / DATE_TRUNC / EXTRACT / PARSE_DATE (NOT DATEDIFF / STRFTIME).
    - Repeated fields require UNNEST.
    - Use only tables and columns from the SCHEMA — DO NOT invent identifiers.

    SCHEMA:
    {schema_text}

    QUESTION: {question}

    ORIGINAL_SQL:
    {broken_sql}

    BIGQUERY_ERROR:
    {error_msg[:600]}

    FIXED_SQL:
    ''').strip()
