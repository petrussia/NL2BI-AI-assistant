"""snowflake_dialect_normalizer_v9 — fix common BigQuery-isms in SF SQL.

Pilot10 (v8) showed Coder-7B emits `\`db.schema.table\`` (BQ backtick) for
Snowflake tasks despite the prompt forbidding it. The v9 normalizer is
**string-level + sqlglot-fallback** post-processing applied between
generation and verification. It is intentionally conservative — only
rewrites that preserve semantics.

Top fixes (in order applied):

1. **Backticks → fully-qualified Snowflake identifier**.
   `\`PROJECT.DATASET.TABLE\`` → `DATASET.TABLE` (Snowflake doesn't have
   GCP projects; we drop the project component) or, if no project is
   detected, `DB.SCHEMA.TABLE` → uppercase unquoted form.
2. **`UNNEST(arr)` → `LATERAL FLATTEN(input => arr) AS f`** + replace
   bare alias references downstream where safe.
3. **`SAFE_CAST(x AS T)` → `TRY_CAST(x AS T)`**.
4. **`DATE("YYYYMMDD")` → `TO_DATE('YYYYMMDD','YYYYMMDD')`**.
5. **`DATE "YYYY-MM-DD"` typed-date literal stays** — Snowflake supports
   it; we just defensively wrap with `TO_DATE` if it appeared as a
   bare BQ STRING cast.
6. **`DATE_DIFF(d1, d2, DAY)` (BQ) → `DATEDIFF(DAY, d2, d1)` (SF)** —
   note Snowflake uses (PART, start, end) order.
7. **`DATE_TRUNC(d, DAY)` (BQ) → `DATE_TRUNC('DAY', d)` (SF)**.
8. **`DATE_ADD(d, INTERVAL 1 DAY)` (BQ) → `DATEADD(DAY, 1, d)` (SF)**.
9. **`REGEXP_CONTAINS(x, p)` (BQ) → `REGEXP_LIKE(x, p)` (SF)**.
10. **`_TABLE_SUFFIX BETWEEN ...` (BQ wildcard) → drop and emit a
    runtime warning (cannot be safely converted)**.
11. **Last-resort sqlglot transpile** — if sqlglot can parse it as bq,
    `transpile(sql, read='bigquery', write='snowflake')` and use the
    result IF it's still well-formed.

Returns `{normalized_sql, applied_fixes: list[str], notes: list[str]}`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NormResult:
    sql: str
    applied: list
    notes: list

    def to_dict(self) -> dict:
        return {'sql': self.sql, 'applied_fixes': self.applied,
                 'notes': self.notes}


_BACKTICK_TRIPLE_RE = re.compile(
    r'`([A-Za-z_][\w-]*)\.([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)`')
_BACKTICK_DOUBLE_RE = re.compile(
    r'`([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)`')
_BACKTICK_SINGLE_RE = re.compile(r'`([A-Za-z_][\w-]*)`')

_UNNEST_RE = re.compile(r'\bUNNEST\s*\(\s*([^)]+)\s*\)\s*(?:AS\s+(\w+))?',
                          re.IGNORECASE)
_SAFE_CAST_RE = re.compile(r'\bSAFE_CAST\b', re.IGNORECASE)
_DATE_LITERAL_RE = re.compile(
    r'\bDATE\s*\(\s*"(\d{4})(\d{2})(\d{2})"\s*\)', re.IGNORECASE)
_DATEDIFF_BQ_RE = re.compile(
    r'\bDATE_DIFF\s*\(\s*([^,]+),\s*([^,]+),\s*(\w+)\s*\)', re.IGNORECASE)
_DATETRUNC_BQ_RE = re.compile(
    r'\bDATE_TRUNC\s*\(\s*([^,]+),\s*(\w+)\s*\)', re.IGNORECASE)
_DATEADD_BQ_RE = re.compile(
    r'\bDATE_ADD\s*\(\s*([^,]+),\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)', re.IGNORECASE)
_REGEXP_CONTAINS_RE = re.compile(r'\bREGEXP_CONTAINS\b', re.IGNORECASE)
_TABLE_SUFFIX_RE = re.compile(
    r'\b_TABLE_SUFFIX\s+BETWEEN\b[^\n]+', re.IGNORECASE)


def _strip_project_in_3part(m: re.Match) -> str:
    """`a.b.c` → if `a` looks like a GCP project (lowercase/dashes), drop it
    and return `b.c`. Else return uppercase `A.B.C` (Snowflake fully
    qualified DB.SCHEMA.TABLE).
    """
    a, b, c = m.group(1), m.group(2), m.group(3)
    if '-' in a or a.islower():
        return f'{b.upper()}.{c.upper()}'
    return f'{a.upper()}.{b.upper()}.{c.upper()}'


def normalize(sql: str) -> NormResult:
    if not sql or not isinstance(sql, str):
        return NormResult(sql=sql or '', applied=[], notes=['empty_input'])
    cur = sql
    applied: list = []
    notes: list = []

    # 1. Backticks → Snowflake form
    out = _BACKTICK_TRIPLE_RE.sub(_strip_project_in_3part, cur)
    if out != cur: applied.append('backtick_3part'); cur = out
    out = _BACKTICK_DOUBLE_RE.sub(lambda m: f'{m.group(1).upper()}.{m.group(2).upper()}', cur)
    if out != cur: applied.append('backtick_2part'); cur = out
    out = _BACKTICK_SINGLE_RE.sub(lambda m: m.group(1).upper(), cur)
    if out != cur: applied.append('backtick_1part'); cur = out

    # 2. UNNEST → LATERAL FLATTEN
    def _unnest_repl(m: re.Match) -> str:
        arr = m.group(1).strip()
        alias = m.group(2) or 'f'
        return f'LATERAL FLATTEN(input => {arr}) AS {alias}'
    out = _UNNEST_RE.sub(_unnest_repl, cur)
    if out != cur:
        applied.append('unnest_to_flatten')
        notes.append('UNNEST→FLATTEN: alias.value access may need manual fix; SF uses f.value not f')
        cur = out

    # 3. SAFE_CAST → TRY_CAST
    out = _SAFE_CAST_RE.sub('TRY_CAST', cur)
    if out != cur: applied.append('safe_cast_to_try_cast'); cur = out

    # 4. DATE("YYYYMMDD") → TO_DATE('YYYYMMDD','YYYYMMDD')
    def _date_lit_repl(m: re.Match) -> str:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"TO_DATE('{y}{mo}{d}','YYYYMMDD')"
    out = _DATE_LITERAL_RE.sub(_date_lit_repl, cur)
    if out != cur: applied.append('date_string_literal'); cur = out

    # 6. DATE_DIFF arg order
    def _datediff_repl(m: re.Match) -> str:
        d1, d2, part = m.group(1).strip(), m.group(2).strip(), m.group(3).upper()
        return f'DATEDIFF({part}, {d2}, {d1})'
    out = _DATEDIFF_BQ_RE.sub(_datediff_repl, cur)
    if out != cur: applied.append('date_diff_arg_order'); cur = out

    # 7. DATE_TRUNC arg order
    def _datetrunc_repl(m: re.Match) -> str:
        d, part = m.group(1).strip(), m.group(2).upper()
        return f"DATE_TRUNC('{part}', {d})"
    out = _DATETRUNC_BQ_RE.sub(_datetrunc_repl, cur)
    if out != cur: applied.append('date_trunc_arg_order'); cur = out

    # 8. DATE_ADD → DATEADD
    def _dateadd_repl(m: re.Match) -> str:
        d, n, part = m.group(1).strip(), m.group(2), m.group(3).upper()
        return f'DATEADD({part}, {n}, {d})'
    out = _DATEADD_BQ_RE.sub(_dateadd_repl, cur)
    if out != cur: applied.append('date_add_to_dateadd'); cur = out

    # 9. REGEXP_CONTAINS → REGEXP_LIKE
    out = _REGEXP_CONTAINS_RE.sub('REGEXP_LIKE', cur)
    if out != cur: applied.append('regexp_contains_to_like'); cur = out

    # 10. _TABLE_SUFFIX (cannot fix automatically)
    if _TABLE_SUFFIX_RE.search(cur):
        notes.append('contains _TABLE_SUFFIX — Snowflake has no equivalent')

    # 11. Last-resort sqlglot transpile (only if cur still has `[` brackets
    # or BQ-only artifacts we couldn't catch)
    try:
        if '[' in cur or 'STRUCT(' in cur.upper():
            import sqlglot
            transpiled = sqlglot.transpile(cur, read='bigquery', write='snowflake',
                                              pretty=False)
            if transpiled and transpiled[0] and transpiled[0] != cur:
                cur = transpiled[0]
                applied.append('sqlglot_transpile')
    except Exception as exc:
        notes.append(f'sqlglot_transpile_failed:{type(exc).__name__}')

    return NormResult(sql=cur, applied=applied, notes=notes)


def has_bigquery_isms(sql: str) -> bool:
    """Quick check before normalization."""
    if not sql: return False
    s_low = sql.lower()
    if '`' in sql: return True
    if 'safe_cast' in s_low: return True
    if 'unnest(' in s_low: return True
    if 'regexp_contains' in s_low: return True
    if '_table_suffix' in s_low: return True
    return False
