"""bigquery_dialect_normalizer_v9 — fix common BQ lexical issues.

Pilot v8 BQ: model emitted `DATE("20210101")` (BQ rejected: "Could not
cast literal '20210101' to type DATE"). Other recurring issues:

  - Missing `r"..."` for regex literals
  - Missing typed-date literal form `DATE 'YYYY-MM-DD'`
  - INT64 vs INT casts
  - SAFE_CAST is OK on BQ but model may emit TRY_CAST (Snowflake)
    when the prompt is BQ — reverse direction

Conservative string-level fixes only.
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
        return {'sql': self.sql, 'applied_fixes': self.applied, 'notes': self.notes}


_DATE_BAD_LITERAL_RE = re.compile(
    r'\bDATE\s*\(\s*["\'](\d{4})(\d{2})(\d{2})["\']\s*\)', re.IGNORECASE)
_DATE_DASH_LITERAL_RE = re.compile(
    r'\bDATE\s*\(\s*["\'](\d{4})-(\d{2})-(\d{2})["\']\s*\)', re.IGNORECASE)
_TRY_CAST_RE = re.compile(r'\bTRY_CAST\b', re.IGNORECASE)
_DATEDIFF_SF_RE = re.compile(
    r'\bDATEDIFF\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\s*\)', re.IGNORECASE)


def normalize(sql: str) -> NormResult:
    if not sql or not isinstance(sql, str):
        return NormResult(sql=sql or '', applied=[], notes=['empty_input'])
    cur = sql
    applied: list = []
    notes: list = []

    # 1. DATE("YYYYMMDD") → DATE '20210101' (BQ accepts typed literal "DATE 'YYYY-MM-DD'")
    def _date_bad_repl(m: re.Match) -> str:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"DATE '{y}-{mo}-{d}'"
    out = _DATE_BAD_LITERAL_RE.sub(_date_bad_repl, cur)
    if out != cur: applied.append('date_yyyymmdd_to_typed'); cur = out

    # 2. DATE("YYYY-MM-DD") → DATE 'YYYY-MM-DD'
    def _date_dash_repl(m: re.Match) -> str:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"DATE '{y}-{mo}-{d}'"
    out = _DATE_DASH_LITERAL_RE.sub(_date_dash_repl, cur)
    if out != cur: applied.append('date_dashed_to_typed'); cur = out

    # 3. TRY_CAST → SAFE_CAST (Snowflake → BigQuery direction)
    out = _TRY_CAST_RE.sub('SAFE_CAST', cur)
    if out != cur: applied.append('try_cast_to_safe_cast'); cur = out

    # 4. DATEDIFF(PART, a, b) (SF) → DATE_DIFF(b, a, PART) (BQ)
    def _datediff_repl(m: re.Match) -> str:
        part, a, b = m.group(1).upper(), m.group(2).strip(), m.group(3).strip()
        return f'DATE_DIFF({b}, {a}, {part})'
    out = _DATEDIFF_SF_RE.sub(_datediff_repl, cur)
    if out != cur: applied.append('datediff_to_date_diff'); cur = out

    return NormResult(sql=cur, applied=applied, notes=notes)


def has_snowflake_isms(sql: str) -> bool:
    if not sql: return False
    s_low = sql.lower()
    if 'try_cast' in s_low: return True
    if 'lateral flatten' in s_low: return True
    # DATE("YYYYMMDD") form is the most common BQ failure
    if _DATE_BAD_LITERAL_RE.search(sql): return True
    return False
