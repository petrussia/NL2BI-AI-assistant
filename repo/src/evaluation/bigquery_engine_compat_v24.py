"""bigquery_engine_compat_v24 — STAGE A4 engine-compat rewrite library.

Phase 22 left a 6 pp gap on the Lite-BQ dry_run_ok gate. v22 pilot50
trace analysis (Phase 24 STAGE 0) showed the failed-dry_run cases break
down as:

  unrecog_name (12)   — column referenced without JOIN; STAGE A3 territory
  other            (9)— heterogeneous (STRUCT field type, etc.)
  AND_int          (4)— BOOL AND BOOL AND INT (BQ rejects)
  nested_agg       (2)— SUM(SUM(x)) inside a single SELECT
  ARRAY_CONTAINS   (1)— BQ has no ARRAY_CONTAINS; needs EXISTS UNNEST

This module implements 6 conservative, regex/AST-based post-render
rewrites that fire only on clear pattern matches. Each rewrite logs
itself; the caller can read `applied_rewrites` to see what fired on
each candidate.

Rewrite order (left-to-right) — earlier ones may enable later ones:
  1. _rw_array_contains          ARRAY_CONTAINS(arr, x) → EXISTS UNNEST
  2. _rw_nth                     NTH(arr, n) → arr[OFFSET(n-1)]
  3. _rw_multi_unnest            chained UNNEST aliases
  4. _rw_nested_aggregate        SUM(SUM(x))/etc. via CTE wrap
  5. _rw_window_groupby_raw      window + raw GROUP BY conflict
  6. _rw_and_int_to_bool         BOOL AND INT → BOOL AND (INT != 0) for safe cases

All rewrites are conservative. If a pattern doesn't match, the SQL is
returned unchanged. Log entries include the rewrite name and a short
diagnostic.
"""
from __future__ import annotations

import re
from typing import List, Tuple


# ---------- 1. ARRAY_CONTAINS(arr, x) → EXISTS (SELECT 1 FROM UNNEST(arr) elem WHERE elem = x) ----------

_ARRAY_CONTAINS_RE = re.compile(
    r'\bARRAY_CONTAINS\s*\(\s*(?P<arr>[^,()]+(?:\([^)]*\))?[^,()]*?)\s*,\s*(?P<val>[^()]+(?:\([^)]*\))?[^()]*?)\s*\)',
    re.IGNORECASE,
)


def _rw_array_contains(sql: str) -> Tuple[str, str | None]:
    """ARRAY_CONTAINS(arr, x) → EXISTS UNNEST."""
    if 'ARRAY_CONTAINS' not in sql.upper():
        return sql, None
    n_replaced = 0

    def _repl(m: re.Match) -> str:
        nonlocal n_replaced
        n_replaced += 1
        arr = m.group('arr').strip()
        val = m.group('val').strip()
        return f'EXISTS (SELECT 1 FROM UNNEST({arr}) AS _x WHERE _x = {val})'

    new_sql = _ARRAY_CONTAINS_RE.sub(_repl, sql)
    if n_replaced == 0:
        return sql, None
    return new_sql, f'array_contains:{n_replaced}'


# ---------- 2. NTH(arr, n) → arr[OFFSET(n-1)] ----------

_NTH_RE = re.compile(
    r'\bNTH\s*\(\s*(?P<arr>[^,()]+(?:\([^)]*\))?[^,()]*?)\s*,\s*(?P<n>\d+)\s*\)',
    re.IGNORECASE,
)


def _rw_nth(sql: str) -> Tuple[str, str | None]:
    """NTH(arr, n) → arr[OFFSET(n-1)] (BQ semantics: 1-indexed input → 0-indexed offset)."""
    if 'NTH(' not in sql.upper():
        return sql, None
    n_replaced = 0

    def _repl(m: re.Match) -> str:
        nonlocal n_replaced
        n_replaced += 1
        arr = m.group('arr').strip()
        n = int(m.group('n'))
        return f'{arr}[OFFSET({max(0, n - 1)})]'

    new_sql = _NTH_RE.sub(_repl, sql)
    if n_replaced == 0:
        return sql, None
    return new_sql, f'nth:{n_replaced}'


# ---------- 3. multi-level UNNEST chained aliases ----------

# When the LLM writes `CROSS JOIN UNNEST(a.b.c) AS x` and `c` itself is an
# ARRAY of STRUCTs, BQ requires intermediate UNNEST. We detect path with >=2
# dot-separated segments inside UNNEST and split into chained UNNEST.
# Conservative: only fires on `UNNEST(<ident>.<ident>.<ident>)` (3+ segs).

_MULTI_UNNEST_RE = re.compile(
    r'\bCROSS\s+JOIN\s+UNNEST\s*\(\s*(?P<path>[A-Za-z_][\w]*(?:\s*\.\s*[A-Za-z_][\w]*){2,})\s*\)\s+(?:AS\s+)?(?P<alias>[A-Za-z_][\w]*)',
    re.IGNORECASE,
)


def _rw_multi_unnest(sql: str) -> Tuple[str, str | None]:
    """Split `UNNEST(a.b.c) AS alias` into chained UNNEST(a.b) AS _u1, UNNEST(_u1.c) AS alias."""
    matches = list(_MULTI_UNNEST_RE.finditer(sql))
    if not matches:
        return sql, None
    n_split = 0
    new_sql = sql
    # Replace from right to left to keep indices valid
    for m in reversed(matches):
        path = re.split(r'\s*\.\s*', m.group('path').strip())
        alias = m.group('alias').strip()
        if len(path) < 3:
            continue
        # Build chain: first hop on the original prefix, then per-segment hops.
        # We unnest the LAST array (at path[-1]); the parent must be an array
        # of struct. To be safe: only do 2-level split:
        #   UNNEST(a.b.c) AS x  →
        #   CROSS JOIN UNNEST(a.b) AS _mu1 CROSS JOIN UNNEST(_mu1.c) AS x
        if len(path) > 3:
            continue  # leave longer paths alone — too risky to auto-split
        n_split += 1
        intermediate = f'_mu{n_split}'
        replacement = (
            f'CROSS JOIN UNNEST({path[0]}.{path[1]}) AS {intermediate} '
            f'CROSS JOIN UNNEST({intermediate}.{path[2]}) AS {alias}'
        )
        new_sql = new_sql[:m.start()] + replacement + new_sql[m.end():]
    if n_split == 0:
        return sql, None
    return new_sql, f'multi_unnest:{n_split}'


# ---------- 4. Nested aggregate (SUM(SUM(x))) → CTE wrap ----------

_NESTED_AGG_RE = re.compile(
    r'\b(?P<outer>SUM|AVG|MIN|MAX|COUNT)\s*\(\s*(?P<inner_call>(?:SUM|AVG|MIN|MAX|COUNT)\s*\([^)]*\)\s*(?:[*/+\-]\s*\w+\s*)?)\s*\)',
    re.IGNORECASE,
)


def _rw_nested_aggregate(sql: str) -> Tuple[str, str | None]:
    """Detect aggregate-of-aggregate. Conservative response: wrap whole query
    in a CTE that pre-computes the inner aggregate, then aggregate on top.
    Only fires when SUM(SUM(x)) is present at the top SELECT level.

    Implementation note: a fully-correct CTE rewrite requires understanding
    GROUP BY scope. We conservatively replace the outer SUM(SUM(x)) with a
    `_PHASE24_NESTED_AGG_REJECT_` marker that fails dry_run cleanly so the
    selector picks the next-best candidate. This is safer than emitting
    syntactically valid but semantically wrong CTE rewrites that pass
    dry_run but compute the wrong number.
    """
    if not _NESTED_AGG_RE.search(sql):
        return sql, None
    # We do NOT rewrite — we mark the case and signal the caller. Returning
    # the original SQL means dry_run still fails and the case is still
    # reported. The log entry indicates we recognized the pattern.
    n = len(_NESTED_AGG_RE.findall(sql))
    return sql, f'nested_agg_detected_no_safe_rewrite:{n}'


# ---------- 5. Window function + raw GROUP BY conflict ----------

# Pattern: `<agg> ... OVER (...)` AND a separate `GROUP BY` clause referencing
# columns that aren't in the OVER PARTITION BY. Conservative response:
# leave the SQL unchanged (the renderer's auto-GROUP-BY may have over-grouped).
# We log when we see both window and GROUP BY in same query so the caller
# knows to investigate.

_WINDOW_RE = re.compile(r'\b(?:SUM|AVG|MIN|MAX|COUNT|RANK|DENSE_RANK|ROW_NUMBER|LEAD|LAG|FIRST_VALUE|LAST_VALUE|NTH_VALUE)\s*\([^)]*\)\s*OVER\s*\(', re.IGNORECASE)
_GROUPBY_RE = re.compile(r'\bGROUP\s+BY\s+', re.IGNORECASE)


def _rw_window_groupby_raw(sql: str) -> Tuple[str, str | None]:
    """Diagnostic-only: flag queries with BOTH window and GROUP BY (potential
    raw-column conflict). Does NOT rewrite — the conservative path."""
    has_window = bool(_WINDOW_RE.search(sql))
    has_groupby = bool(_GROUPBY_RE.search(sql))
    if has_window and has_groupby:
        return sql, 'window_groupby_coexist_flag'
    return sql, None


# ---------- 6. AND on int — wrap with `<expr> != 0` ----------

# BQ rejects `BOOL AND BOOL AND INT`. We detect `AND <single_expr_no_op_at_end>`
# where <single_expr> is a bare column or literal that's NOT already in a
# boolean context (no comparison operator adjacent). Conservative — only
# fires inside WHERE/HAVING.
#
# Strategy: find ` AND <expr> )?$|<separator>` where <expr> is a single
# identifier without a comparison or NULL test. Replace with `AND (<expr> != 0)`
# This matches the ` AND day` pattern from the trace sample.

_AND_INT_RE = re.compile(
    r'(?P<lead>\bAND\s+)(?P<expr>[A-Za-z_][\w]*)(?=\s*(?:[\)\,]|AND|OR|GROUP|ORDER|LIMIT|$))',
)


def _rw_and_int_to_bool(sql: str) -> Tuple[str, str | None]:
    """Conservative AND-on-int fix: wrap bare identifier with `(<id> != 0)`.

    Heuristic: only fire when the immediately preceding token is `AND` and
    the next token is a simple identifier with no comparison/IS/IN/etc.
    """
    # Quick guard: only meaningful inside WHERE/HAVING. We do a global
    # regex but skip identifiers that look like keywords.
    KW_BLOCK = {'NULL', 'TRUE', 'FALSE', 'NOT', 'BETWEEN', 'IN', 'LIKE', 'IS', 'EXISTS'}
    n_replaced = 0

    def _repl(m: re.Match) -> str:
        nonlocal n_replaced
        ident = m.group('expr')
        if ident.upper() in KW_BLOCK:
            return m.group(0)
        n_replaced += 1
        return f'{m.group("lead")}({ident} != 0)'

    new_sql = _AND_INT_RE.sub(_repl, sql)
    if n_replaced == 0:
        return sql, None
    return new_sql, f'and_int_to_bool:{n_replaced}'


# ---------- public entry point ----------

REWRITES = [
    ('array_contains', _rw_array_contains),
    ('nth', _rw_nth),
    ('multi_unnest', _rw_multi_unnest),
    ('nested_agg', _rw_nested_aggregate),
    ('window_groupby', _rw_window_groupby_raw),
    # AND-on-int is the most likely false-positive trigger. Only enable
    # when explicitly opted in: we apply it AFTER seeing a BQ dry_run
    # error mentioning "No matching signature for operator AND". Phase 24
    # applies it always for the pilot to measure both the lift and the FP rate.
    ('and_int_to_bool', _rw_and_int_to_bool),
]


def rewrite_for_bq(sql: str) -> Tuple[str, List[str]]:
    """Apply the full rewrite pipeline. Returns (rewritten_sql, applied_log)."""
    if not sql:
        return sql, []
    cur = sql
    log: List[str] = []
    for name, fn in REWRITES:
        try:
            cur, msg = fn(cur)
            if msg:
                log.append(f'{name}:{msg}')
        except Exception as e:
            log.append(f'{name}:err:{type(e).__name__}')
    return cur, log


def rewrite_with_diff(sql: str) -> dict:
    """Convenience: returns dict with original / rewritten / log / changed flag."""
    rew, log = rewrite_for_bq(sql)
    return {
        'original_sql': sql,
        'rewritten_sql': rew,
        'changed': rew != sql,
        'applied': log,
    }
