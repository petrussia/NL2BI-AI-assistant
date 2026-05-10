"""candidate_selector_v18 — validator + minimal probe + selection policy.

Validator-first selection over a list of candidate SQLs.

v18.1 patch: replaced regex-based identifier residency with **AST-aware**
walking of the sqlglot parse tree. The earlier regex split on hyphens,
which falsely flagged `bigquery-public-data` as 3 separate "leaks"
(`bigquery`, `public`, `data`). The AST walker pulls Table.parts and
Column.parts directly from sqlglot, so hyphenated GCP project names,
nested struct paths, and wildcard date shards are handled correctly.

Wildcards: a candidate's table reference `<base>_<YYYYMMDD>` is treated
as residency-OK if the pack contains any sibling `<base>_<other_date>`
or a `<base>_*` family entry. This matches BigQuery's wildcard table
semantics.

Selection policy (in priority order):
  1. dry_run_ok (BQ live dry_run / explain) — first non-zero signal
  2. parse_ok (sqlglot in BQ dialect)
  3. schema_valid (identifiers exist in pack)
  4. preference for family A (deterministic) over B (LLM) when tied
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


_DATE_SHARD_RE = re.compile(r'^(?P<base>.+?)_(?P<date>\d{6,8})$')


@dataclass
class CandEval:
    family: str
    sql: str
    parse_ok: bool = False
    schema_valid: bool = False
    dry_run_ok: bool = False
    error_class: str = ''
    error_msg: str = ''
    notes: list = field(default_factory=list)


def parse_with_sqlglot_bq(sql: str):
    """Parse and return the AST or (None, error)."""
    try:
        import sqlglot
        ast = sqlglot.parse_one(sql, read='bigquery')
        return ast, ''
    except Exception as e:
        return None, f'{type(e).__name__}:{str(e)[:200]}'


def _normalize_pack_names(pack: dict) -> dict:
    """Return a structured residency dictionary derived from the pack.

    Returns {
      'projects':       set[str],   # db field
      'datasets':       set[str],   # schema field
      'project_dataset':set[str],   # 'project.dataset'
      'tables':         set[str],   # bare table names
      'wildcard_bases': set[str],   # date-shard families: 'ga_sessions'
      'columns_full':   set[str],   # full struct paths or column names
      'columns_root':   set[str],   # leaf top-level column or root of struct
      'columns_leaf':   set[str],   # last segment of nested path
    }
    """
    projects = set()
    datasets = set()
    project_dataset = set()
    tables = set()
    wildcard_bases = set()
    columns_full = set()
    columns_root = set()
    columns_leaf = set()

    for d in pack.get('databases', []):
        projects.add(d.get('name', ''))
        for s in d.get('schemas', []):
            datasets.add(s)
            project_dataset.add(f"{d.get('name','')}.{s}")

    for t in pack.get('tables', []):
        proj = t.get('db', '')
        dset = t.get('schema', '')
        tname = t.get('table', '')
        projects.add(proj)
        datasets.add(dset)
        project_dataset.add(f'{proj}.{dset}')
        tables.add(tname)
        # date-shard family
        m = _DATE_SHARD_RE.match(tname)
        if m:
            wildcard_bases.add(m.group('base'))
        # v22 STAGE A2: union BM25 top-K columns AND full all_columns side
        # channel for residency. Resolves the v21 audit finding that 10/24
        # ast_leak chosen-candidate failures were validator false positives
        # where the planner correctly used a real column not in the pack
        # top-K (e.g. totals.transactionRevenue, event_timestamp).
        bm25_cols = [c.get('name') or '' for c in t.get('columns', [])]
        all_cols = t.get('all_columns', []) or []
        for cn in list(bm25_cols) + list(all_cols):
            if not cn:
                continue
            columns_full.add(cn)
            if '.' in cn:
                parts = cn.split('.')
                columns_root.add(parts[0])
                columns_leaf.add(parts[-1])
            else:
                columns_root.add(cn)
                columns_leaf.add(cn)
    return {
        'projects': projects, 'datasets': datasets,
        'project_dataset': project_dataset, 'tables': tables,
        'wildcard_bases': wildcard_bases,
        'columns_full': columns_full, 'columns_root': columns_root,
        'columns_leaf': columns_leaf,
    }


def _table_residency(parts: list, names: dict) -> bool:
    """parts ~ ['project', 'dataset', 'table'] (variable length 1..3+).

    Accept if the bare table name (last) is in tables OR matches a
    wildcard base via date-shard. Project/dataset prefix mismatches
    are tolerated because BQ identifiers are also resolvable via
    cross-project access.
    """
    if not parts:
        return False
    table = parts[-1]
    if table in names['tables']:
        return True
    # wildcard table reference like ga_sessions_*
    if table.endswith('_*'):
        base = table[:-2]
        return base in names['wildcard_bases']
    # date shard
    m = _DATE_SHARD_RE.match(table)
    if m and m.group('base') in names['wildcard_bases']:
        return True
    # Last-resort: allow if any project/dataset matches a known one
    if len(parts) >= 2 and parts[-2] in names['datasets']:
        return True
    return False


# BQ + Snow pseudo-columns and global SQL identifiers always treated as valid.
_PSEUDO_COLUMNS = {
    '_TABLE_SUFFIX', '_PARTITIONTIME', '_PARTITIONDATE', '_FILE_NAME',
    'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_DATETIME', 'CURRENT_TIME',
    'true', 'false', 'null', 'TRUE', 'FALSE', 'NULL',
}


def _column_residency(parts: list, names: dict) -> bool:
    """A Column reference's parts in sqlglot may be ['table', 'col'] or
    ['col'] or a longer chain for nested fields. Accept if any of the
    forms (full, root, leaf) is in the pack's column sets, or if the
    reference is a BQ/Snow pseudo-column or a SQL global."""
    if not parts:
        return False
    if any(p in _PSEUDO_COLUMNS for p in parts):
        return True
    full = '.'.join(parts)
    if full in names['columns_full']:
        return True
    leaf = parts[-1]
    root = parts[0]
    if leaf in names['columns_leaf'] or leaf in names['columns_full']:
        return True
    if root in names['columns_root']:
        return True
    return False


def schema_valid_against_pack(sql: str, pack: dict) -> tuple:
    """AST-aware closed-set residency check.

    Walks the parsed sqlglot AST for Table and Column references and
    verifies each against the pack's identifier sets. Returns
    (ok: bool, error_msg: str). On parse failure falls back to a
    permissive result so callers don't double-penalise the candidate
    (parse_ok already captures parse failure).
    """
    ast, perr = parse_with_sqlglot_bq(sql)
    if ast is None:
        # parse failed; defer schema validity verdict to caller
        return False, f'parse_failed_for_validation:{perr}'
    import sqlglot.expressions as E
    names = _normalize_pack_names(pack)

    leaks = []
    seen_tables = set()
    seen_cols = set()

    # Pull explicit aliases declared in the SQL — these should NOT
    # be flagged as leaks even if they aren't in the pack.
    # v21 STAGE A1: also track UNNEST/Lateral aliases (so `param` in
    # `UNNEST(event_params) AS param WHERE param.key=...` is recognised),
    # CTE/With names, subquery aliases.
    aliases = set()
    for alias_node in ast.find_all(E.Alias):
        a = alias_node.alias_or_name
        if a:
            aliases.add(a)
    for table in ast.find_all(E.Table):
        if table.alias:
            aliases.add(table.alias)
    # CTE names (WITH cte AS (...))
    for cte in ast.find_all(E.CTE):
        try:
            n = cte.alias_or_name
            if n:
                aliases.add(n)
        except Exception:
            pass
    # UNNEST aliases — sqlglot represents as Unnest with .alias or
    # surrounded by Lateral. Walk all nodes and grab any `alias` attr.
    for node in ast.walk():
        try:
            a = getattr(node, 'alias_or_name', None) or getattr(node, 'alias', None)
            if isinstance(a, str) and a:
                aliases.add(a)
            elif a and hasattr(a, 'name') and a.name:
                aliases.add(a.name)
        except Exception:
            continue
    # Subquery aliases captured by Subquery node
    for sq in ast.find_all(E.Subquery):
        try:
            n = sq.alias_or_name
            if n:
                aliases.add(n)
        except Exception:
            pass

    for tab in ast.find_all(E.Table):
        # tab.parts gives ['proj', 'dataset', 'table'] when fully qualified
        try:
            parts = [p.name for p in tab.parts]
        except Exception:
            parts = [tab.name] if tab.name else []
        sig = '.'.join(parts)
        if sig in seen_tables:
            continue
        seen_tables.add(sig)
        if not _table_residency(parts, names):
            leaks.append(f'table:{sig}')

    # Track which aliases came from UNNEST/Lateral specifically — column
    # references rooted at those should be trusted (we can't validate
    # inner struct fields without type info).
    # In sqlglot BQ dialect, `UNNEST(arr) AS x` parses as Unnest with
    # an `alias` arg of TableAlias whose `columns` list holds the
    # identifier(s) — NOT alias_or_name on the Unnest itself.
    unnest_aliases = set()
    for node in ast.walk():
        try:
            if type(node).__name__ in ('Unnest', 'Lateral', 'TableFromRows'):
                a = getattr(node, 'alias_or_name', None)
                if isinstance(a, str) and a:
                    unnest_aliases.add(a)
                table_alias = node.args.get('alias') if hasattr(node, 'args') else None
                if table_alias is not None:
                    name = getattr(table_alias, 'name', '') or ''
                    if name:
                        unnest_aliases.add(name)
                    for col_id in table_alias.args.get('columns', []) or []:
                        cn = getattr(col_id, 'name', None) or getattr(col_id, 'this', None)
                        if isinstance(cn, str) and cn:
                            unnest_aliases.add(cn)
        except Exception:
            continue

    for col in ast.find_all(E.Column):
        try:
            parts = [p.name for p in col.parts] if hasattr(col, 'parts') else []
        except Exception:
            parts = []
        if not parts:
            cname = col.name if hasattr(col, 'name') else ''
            if cname:
                parts = [cname]
        if not parts:
            continue
        # If the column root is a known alias, drop it. If it specifically
        # came from UNNEST/Lateral, trust the residency entirely — we
        # can't validate inner struct fields without type info, so flagging
        # them is a guaranteed false positive.
        if parts[0] in unnest_aliases:
            continue
        if parts[0] in aliases and len(parts) > 1:
            parts = parts[1:]
        sig = '.'.join(parts)
        if sig in seen_cols:
            continue
        seen_cols.add(sig)
        if not _column_residency(parts, names):
            leaks.append(f'col:{sig}')

    if leaks:
        return False, 'leaks=' + ','.join(leaks[:8])
    return True, ''


def dry_run_bq(sql: str, *, max_bytes_billed: int = 1 * 1024**3) -> tuple:
    """Return (ok, error). Uses google-cloud-bigquery if available."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client()
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        if max_bytes_billed:
            cfg.maximum_bytes_billed = max_bytes_billed
        client.query(sql, job_config=cfg)
        return True, ''
    except Exception as e:
        return False, f'{type(e).__name__}:{str(e)[:300]}'


def evaluate_candidate(cand: dict, pack: dict, *, do_dry_run: bool = True) -> CandEval:
    sql = cand.get('sql') or ''
    ev = CandEval(family=cand.get('family', '?'), sql=sql)
    if not sql:
        ev.error_class = 'empty_sql'
        return ev
    ast, perr = parse_with_sqlglot_bq(sql)
    ev.parse_ok = ast is not None
    if not ev.parse_ok:
        ev.error_class = 'parse_error'
        ev.error_msg = perr
    sok, serr = schema_valid_against_pack(sql, pack)
    ev.schema_valid = sok
    if not sok:
        ev.error_class = ev.error_class or 'schema_invalid'
        ev.error_msg = ev.error_msg or serr
    if do_dry_run and ev.parse_ok:
        dok, derr = dry_run_bq(sql)
        ev.dry_run_ok = dok
        if not dok:
            ev.error_class = ev.error_class or 'bq_dry_run_failed'
            ev.error_msg = ev.error_msg or derr
    return ev


def select(candidates: list, pack: dict, *, do_dry_run: bool = True) -> dict:
    evals = [evaluate_candidate(c, pack, do_dry_run=do_dry_run) for c in candidates]

    def score(ev: CandEval) -> tuple:
        return (
            int(ev.dry_run_ok),
            int(ev.parse_ok),
            int(ev.schema_valid),
            1 if ev.family == 'A' else 0,
        )

    chosen = max(range(len(evals)), key=lambda i: score(evals[i])) if evals else -1
    return {
        'evals': [ev.__dict__ for ev in evals],
        'chosen_idx': chosen,
        'chosen': evals[chosen].__dict__ if chosen >= 0 else None,
    }
