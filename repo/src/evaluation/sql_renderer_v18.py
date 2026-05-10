"""sql_renderer_v18 — deterministic SQL renderer from a structured JSON plan.

v18.1 patches:
  - _qualify_table: detect already-qualified `selected_database`
    (contains '.') or `selected_tables[0]` and collapse to a clean
    `project.dataset.table` FQN. Eliminates the prefix-duplication
    bug observed in Phase 18 (`...ga_sessions.bigquery-public-data.
    google_analytics_sample.ga_sessions_20170710`).
  - render_bq: GA-style wildcard rendering. When `selected_tables`
    enumerates several ``<base>_<YYYYMMDD>`` shards OR when
    ``time_constraints`` reference a date range AND a wildcard family
    is available in the pack, emit ``FROM `...<base>_*` WHERE
    _TABLE_SUFFIX BETWEEN <start> AND <end>`` rather than
    concatenating shard names.

Plan shape per `structured_plan_v18`. Renderer outputs BQ-dialect SQL
by default. Snow rendering remains a future variant.
"""
from __future__ import annotations

import re
from typing import Optional


_DATE_SHARD_RE = re.compile(r'^(?P<base>.+?)_(?P<date>\d{6,8})$')


def _strip_known_prefix(name: str, project: str, dataset: str) -> str:
    """If `name` already contains the project.dataset prefix, strip it
    so the caller can re-qualify cleanly."""
    if not name:
        return name
    p = f'{project}.{dataset}.' if project and dataset else ''
    if p and name.startswith(p):
        return name[len(p):]
    # also strip duplicate ".<project>.<dataset>." appearances inside
    if p and p in name:
        # collapse first occurrence
        return name.split(p, 1)[-1]
    return name


def _split_database_field(db_field: str) -> tuple:
    """Accept a `selected_database` that may legitimately be either:
       - 'bigquery-public-data'
       - 'bigquery-public-data.google_analytics_sample' (project.dataset)
       - 'google_analytics_sample' (dataset name only — caller fills project)
       Returns (project_or_empty, dataset_or_empty)."""
    if not db_field:
        return '', ''
    if '.' in db_field:
        head, _, tail = db_field.partition('.')
        return head, tail
    return db_field, ''


def _qualify_table(plan: dict, *, pack: Optional[dict] = None) -> str:
    """Build a clean `project.dataset.table` FQN from the plan, tolerating
    over-qualified planner output. Also handles the wildcard case where
    selected_tables[0] already contains `_*` or several date shards
    were concatenated.

    Phase 20: when a pack is available, defer to the shared canonicaliser
    so renderer + validator agree on what counts as a clean FQN."""
    if pack is not None:
        try:
            from identifier_canonicalize_v20 import canonical_table_for_render
            project, dataset, table = canonical_table_for_render(plan, pack)
            if project and dataset and table:
                return f'`{project}.{dataset}.{table}`'
            if dataset and table:
                return f'`{dataset}.{table}`'
            if table:
                return f'`{table}`'
        except Exception:
            pass
    # Legacy path retained for the no-pack smoke tests.
    db_field = plan.get('selected_database', '') or ''
    schema_field = plan.get('selected_schema', '') or ''
    tables = plan.get('selected_tables') or []
    if not tables:
        return ''
    table = tables[0]

    # 1. Project hint
    proj_db, dset_from_db = _split_database_field(db_field)

    # 2. selected_schema may itself be 'project.dataset'; prefer the dataset tail
    schema_proj, schema_dset = '', schema_field
    if '.' in schema_field:
        schema_proj, _, schema_dset = schema_field.partition('.')

    # 3. Resolve project + dataset preferring already-cited values
    project = proj_db or schema_proj
    dataset = dset_from_db or schema_dset

    # 4. selected_tables[0] may already be FQN — strip any known prefix
    table_clean = _strip_known_prefix(table, project, dataset)
    # also strip shorter project. or dataset. prefixes if they remain
    if project and table_clean.startswith(project + '.'):
        table_clean = table_clean[len(project) + 1:]
    if dataset and table_clean.startswith(dataset + '.'):
        table_clean = table_clean[len(dataset) + 1:]
    # If table_clean still has dots (e.g. 'project.dataset.table' that didn't match
    # because of casing), take the last segment.
    if '.' in table_clean:
        table_clean = table_clean.split('.')[-1]

    # 5. Multi-shard wildcard collapse: if multiple selected_tables
    # share the same date-shard base, render the wildcard.
    bases = set()
    for t in tables:
        bare = t.split('.')[-1]
        m = _DATE_SHARD_RE.match(bare)
        if m:
            bases.add(m.group('base'))
    if len(tables) > 1 and len(bases) == 1:
        wildcard_base = next(iter(bases))
        table_clean = f'{wildcard_base}_*'

    parts = [p for p in (project, dataset, table_clean) if p]
    if not parts:
        return ''
    return f'`{".".join(parts)}`'


def _is_wildcard_table(qualified: str) -> bool:
    return qualified.endswith('_*`') or qualified.endswith('_*')


def _table_suffix_filters(plan: dict) -> list:
    """If the plan's table came from a wildcard family AND the plan
    has a recognizable date range in time_constraints, emit
    _TABLE_SUFFIX filters. Best-effort regex pull on YYYY-MM-DD or
    YYYYMMDD literals."""
    tcs = plan.get('time_constraints') or []
    if not tcs:
        return []
    text = ' '.join(str(t) for t in tcs)
    # find dates in YYYY-MM-DD or YYYYMMDD form
    date_strs = re.findall(r"(\d{4}-\d{2}-\d{2}|\d{8})", text)
    if len(date_strs) < 1:
        return []
    def _to_yyyymmdd(s: str) -> str:
        return s.replace('-', '')[:8]
    norm = sorted({_to_yyyymmdd(d) for d in date_strs})
    if len(norm) >= 2:
        return [f"_TABLE_SUFFIX BETWEEN '{norm[0]}' AND '{norm[-1]}'"]
    if len(norm) == 1:
        return [f"_TABLE_SUFFIX = '{norm[0]}'"]
    return []


_AGG_RE = re.compile(r'\b(?:SUM|COUNT|AVG|MIN|MAX|APPROX_COUNT_DISTINCT|PERCENTILE_CONT|ANY_VALUE)\s*\(',
                       re.IGNORECASE)


def _is_aggregate_expr(expr: str) -> bool:
    return bool(_AGG_RE.search(expr or ''))


def _array_struct_root(col_name: str, pack: Optional[dict]) -> Optional[str]:
    """If `col_name` looks like a nested struct/array path AND the pack's
    column metadata indicates the root column type is ARRAY/REPEATED,
    return the root segment (e.g. 'hits' for 'hits.product.productRevenue').
    Returns None if no UNNEST is required."""
    if not pack or '.' not in col_name:
        return None
    root = col_name.split('.')[0]
    for t in pack.get('tables', []):
        for c in t.get('columns', []):
            if c.get('name') == root or c.get('name', '').startswith(root + '.'):
                ctype = (c.get('type') or '').upper()
                if 'ARRAY' in ctype or 'REPEATED' in ctype:
                    return root
                # nested column path also indicates an array if any column
                # under the same root has further dotted parts
        for c in t.get('columns', []):
            if c.get('name', '').startswith(root + '.') and (c.get('name', '').count('.') >= 2):
                return root
    return None


def render_bq(plan: dict, *, pack: Optional[dict] = None) -> str:
    """Render a plan into a BigQuery SQL string. Single-table primary
    path; wildcard tables handled via _TABLE_SUFFIX filters when the
    plan's tables form a date-shard family.

    v18.1 adds:
      - GROUP BY auto-fix: if any metric is an aggregate AND there are
        non-aggregated SELECT entries, auto-emit GROUP BY for those.
      - UNNEST: if any selected_column is a nested ARRAY<STRUCT> path
        whose root is array-typed in the pack, emit a CROSS JOIN UNNEST
        and rewrite the column reference to use the alias.
      - SELECT dedup: don't append a column if it already appears in a
        metric expression (the prior heuristic was too lax).
    """
    selects = []
    metric_exprs = []
    metrics = plan.get('metrics') or []
    for m in metrics:
        label = m.get('label') or 'metric'
        expr = m.get('expr') or ''
        if expr:
            # v21 STAGE A1 fix: planner sometimes emits aliases with spaces
            # ("Total Revenue") — those break sqlglot parse. Normalise to
            # snake_case while keeping it readable.
            label_clean = re.sub(r'[^A-Za-z0-9_]+', '_', str(label)).strip('_')
            if not label_clean or label_clean[0].isdigit():
                label_clean = 'metric_' + (label_clean or 'x')
            selects.append(f'{expr} AS {label_clean}')
            metric_exprs.append(expr)
    selected_cols = plan.get('selected_columns') or []
    selected_cols_dedup: list = []
    for c in selected_cols:
        # skip if already present in any metric expression (e.g. SUM(x) AS y
        # makes raw `x` redundant in SELECT and triggers GROUP BY errors)
        if any(c in mx for mx in metric_exprs):
            continue
        if c in selected_cols_dedup:
            continue
        selected_cols_dedup.append(c)
        selects.append(c)
    if not selects:
        selects.append('*')

    # UNNEST detection: collect array roots that need CROSS JOIN UNNEST
    unnest_roots: list = []
    if pack:
        seen_roots = set()
        for c in selected_cols_dedup + metric_exprs:
            for root in re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_]', c):
                if root in seen_roots:
                    continue
                seen_roots.add(root)
                ar = _array_struct_root(root + '.x', pack)
                if ar:
                    unnest_roots.append(ar)

    table = _qualify_table(plan, pack=pack)
    select_clause = ', '.join(selects)
    sql = f'SELECT {select_clause}\nFROM {table}'

    for root in unnest_roots:
        # CROSS JOIN UNNEST; alias preserved as the same root name to
        # match selected_columns references.
        sql += f'\nCROSS JOIN UNNEST({root}) AS {root}'

    where_parts = []
    if _is_wildcard_table(table):
        for f in _table_suffix_filters(plan):
            where_parts.append(f'({f})')
    for f in plan.get('filters') or []:
        e = f.get('expr') if isinstance(f, dict) else f
        if e:
            where_parts.append(f'({e})')
    for tc in plan.get('time_constraints') or []:
        if tc and not _is_wildcard_table(table):
            # for non-wildcard tables keep the literal time constraints
            where_parts.append(f'({tc})')
    if where_parts:
        sql += '\nWHERE ' + ' AND '.join(where_parts)

    group = plan.get('grouping') or []
    # v18.1 auto-GROUP-BY: if metrics contain at least one aggregate AND the
    # SELECT list has any non-aggregated raw column entries, auto-add the
    # raw columns to GROUP BY (BQ rejects mixed aggregate + raw without it).
    has_aggregate = any(_is_aggregate_expr(mx) for mx in metric_exprs)
    if has_aggregate:
        non_agg_select = [c for c in selected_cols_dedup
                              if c and not _is_aggregate_expr(c)]
        if non_agg_select:
            for c in non_agg_select:
                if c not in group:
                    group.append(c)
    if group:
        sql += '\nGROUP BY ' + ', '.join(group)

    sortings = plan.get('sorting') or []
    if sortings:
        order_parts = []
        for s in sortings:
            if isinstance(s, dict):
                e = s.get('expr', '')
                d = (s.get('dir') or 'asc').upper()
                if e:
                    order_parts.append(f'{e} {d}')
            else:
                order_parts.append(str(s))
        if order_parts:
            sql += '\nORDER BY ' + ', '.join(order_parts)

    lim = plan.get('limit')
    if lim not in (None, '', 0):
        try:
            sql += f'\nLIMIT {int(lim)}'
        except (TypeError, ValueError):
            pass

    return sql


def render_coder7b_direct_prompt(question: str, pack: dict, external_knowledge: str = '') -> str:
    """Prompt for the Coder-7B control direct emitter."""
    lines = []
    lines.append('You are a BigQuery SQL writer.')
    lines.append('Use ONLY the tables and columns listed below.')
    for t in pack['tables']:
        cols = ', '.join(f"{c['name']}:{c['type']}" for c in t['columns'])
        lines.append(f'Table `{t["db"]}.{t["schema"]}.{t["table"]}`')
        lines.append(f'  Columns: {cols}')
    if external_knowledge:
        lines.append('External knowledge: ' + external_knowledge)
    lines.append('')
    lines.append('Question: ' + question)
    lines.append('')
    lines.append('Return ONE SQL query in a fenced ```sql block.')
    return '\n'.join(lines)
