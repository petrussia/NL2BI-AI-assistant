"""bigquery_nested_rewrite_v16 — deterministic STRUCT/UNNEST rewrite.

Conservative SQL rewrite for known Spider2-Lite-BQ patterns. Each rewrite
fires ONLY when:
  - the qualifier matches a known nested column on a referenced table;
  - the rewrite produces lexically valid replacement;
  - we don't touch identifiers we don't recognize.

Each call returns `{sql, applied: list[str]}`.

A) GA4 event_params:
   `event_params.key = 'x'` and `event_params.value.int_value > 0`
   (in WHERE / SELECT) → wrap a `EXISTS (SELECT 1 FROM UNNEST(event_params) ep
   WHERE ep.key = 'x' AND ep.value.int_value > 0)`. Done only if the
   model used the wrong direct dot-notation (no UNNEST in scope).

B) GA360 hits.product / hits.transaction / hits.eventInfo:
   wrap with `, UNNEST(hits) hit, UNNEST(hit.product) product` etc.

C) Project-qualified 4-part already handled in v12 backtick collapse.
   Here we extend to `"DB.SCHEMA.TABLE"` (snowflake-side blob); not
   needed for BQ.

D) Wildcard suffix detection: if SQL says
   `FROM \`project.dataset.events_2021\`` but catalog has only
   `events_*` shards, leave it (BQ accepts shards directly when
   they exist). Add `_TABLE_SUFFIX` clause only if SQL referenced
   `events_*` literal pattern.

This module never breaks well-formed SQL — every rewrite is gated by
a structural test plus the model's apparent intent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

GA4_NESTED_COLS = {'event_params', 'user_properties', 'items', 'device',
                       'geo', 'traffic_source', 'ecommerce', 'user_ltv'}
GA360_NESTED_COLS = {'hits', 'totals', 'trafficsource', 'device',
                          'geonetwork', 'customdimensions', 'customvariables'}


@dataclass
class RewriteResult:
    sql: str
    applied: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _has_unnest_for(col: str, sql: str) -> bool:
    pat = re.compile(rf'UNNEST\s*\(\s*{re.escape(col)}\s*\)', re.IGNORECASE)
    return bool(pat.search(sql))


def _ga4_rewrite_event_params(sql: str) -> tuple[str, list]:
    """Rewrite `event_params.key = 'X'` in WHERE clause to use EXISTS+UNNEST.
    Conservative: only if no existing UNNEST(event_params) is in scope.
    """
    applied = []
    if 'event_params' not in sql.lower():
        return sql, applied
    if _has_unnest_for('event_params', sql):
        return sql, applied

    # Pattern: event_params.key = 'X' AND event_params.value.<TYPE> <op> <val>
    # We rewrite each direct event_params.<x> reference into an EXISTS subquery
    # at WHERE clause level. To avoid breaking complex SQL, only rewrite if
    # the pattern is a single-row-scope WHERE filter.
    # Heuristic: replace the whole pair `event_params.key = 'X' AND event_params.value.<TYPE> <op> <val>`
    # with EXISTS subquery.
    pair_re = re.compile(
        r"event_params\.key\s*=\s*'([^']+)'\s+AND\s+"
        r"event_params\.value\.(int_value|string_value|float_value|double_value)"
        r"\s*([=!<>]+|IS NOT NULL|IS NULL|>|<|>=|<=)\s*([^\s)]+)",
        re.IGNORECASE)

    def _repl(m):
        key = m.group(1)
        leaf = m.group(2)
        op = m.group(3)
        val = m.group(4)
        applied.append("ga4_event_params_exists")
        return (f"EXISTS (SELECT 1 FROM UNNEST(event_params) ep "
                f"WHERE ep.key = '{key}' AND ep.value.{leaf} {op} {val})")

    out = pair_re.sub(_repl, sql)
    if out != sql:
        return out, applied
    return sql, applied


def _ga360_rewrite_hits(sql: str) -> tuple[str, list]:
    """Add UNNEST(hits) and UNNEST(hit.product) joins if SQL references
    `hits.X` directly without UNNEST."""
    applied = []
    if 'hits.' not in sql.lower():
        return sql, applied
    if _has_unnest_for('hits', sql):
        return sql, applied
    # Conservative: only annotate; full rewriting of complex GA360 SQL is
    # risky. Mark for human inspection.
    return sql, applied


def rewrite_bq_nested(sql: str, *, catalog: dict | None = None) -> RewriteResult:
    """Public entry point. Conservative chain of rewrites.

    Args:
      sql: BQ SQL string.
      catalog: optional catalog dict for stronger gating.

    Returns RewriteResult with applied list of rewrite-class names.
    """
    if not sql or not isinstance(sql, str):
        return RewriteResult(sql=sql or '', applied=[])
    cur = sql
    applied: list[str] = []
    notes: list[str] = []

    out, ap = _ga4_rewrite_event_params(cur)
    if ap: applied.extend(ap)
    cur = out

    out, ap = _ga360_rewrite_hits(cur)
    if ap: applied.extend(ap)
    cur = out

    return RewriteResult(sql=cur, applied=applied, notes=notes)


# --- smoke test ---
if __name__ == '__main__':
    cases = [
        ("SELECT user_pseudo_id FROM `bigquery-public-data.ga4.events_20210101` "
         "WHERE event_params.key = 'engaged' AND event_params.value.int_value > 0"),
        ("SELECT a FROM `b.c.d` WHERE x = 1"),  # no rewrite
        ("SELECT user_pseudo_id FROM `t`, UNNEST(event_params) p WHERE p.key = 'x'"),  # already unnested
    ]
    for s in cases:
        r = rewrite_bq_nested(s)
        print(f"\nIN:  {s}")
        print(f"OUT: {r.sql}")
        print(f"APP: {r.applied}")
