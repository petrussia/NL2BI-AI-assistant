"""schema_pack_builder_v18 — build compact schema pack from linker hits.

Compact pack = JSON-serializable dict the structured planner can fit in
a small prompt budget. Designed for CLOSED-SET planning: the planner is
told that any identifier outside the pack is invalid.

Pack shape:
  {
    "lane": "bq" | "snow",
    "alias": str | None,
    "databases": [
      {"name": <db_or_project>, "schemas": [<schema>], "score": float}
    ],
    "tables": [
      {"db": str, "schema": str, "table": str,
       "columns": [
         {"name": <col_or_field_path>, "type": str, "nullable": str,
          "description": str|None}
       ],
       "score": float}
    ],
    "wildcards": [<pattern hint>],
    "join_hints": [<text hint>],
    "token_budget_used": int (rough),
  }

The builder applies caps to keep the pack small:
- max_tables (default 8)
- max_cols_per_table (default 25 unless table is small)
- truncate description to max_desc_chars
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Optional

from schema_linking_v18 import LinkerHit, LinkerOutput, CatalogColumn


@dataclass
class PackTable:
    db: str
    schema: str
    table: str
    score: float
    columns: list = field(default_factory=list)


@dataclass
class PackColumn:
    name: str
    type: str
    nullable: str
    description: Optional[str]


def _short(s: Optional[str], n: int) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    return s if len(s) <= n else s[:n - 1] + '…'


def build_pack(linker_out: LinkerOutput, *, lane: str, alias: Optional[str],
               max_tables: int = 8, max_cols_per_table: int = 25,
               max_desc_chars: int = 120,
               all_catalog_cols: Optional[list] = None) -> dict:
    """Build compact schema pack from linker hits.

    v22 STAGE A2: when `all_catalog_cols` is supplied (the linker's
    full column list), each chosen table's `all_columns` field is
    populated with every known column name for that (db,schema,table).
    The validator uses this fuller set for residency checks while the
    planner prompt still sees only the compact `columns` BM25 top-K.
    Resolves the v21 pilot50 audit's 24 ast_leak / 10 false-positive
    schema_invalid class.
    """
    # Group hits by (db, schema, table). Use the highest-scoring table set.
    grouped: dict = defaultdict(list)  # (db, schema, table) -> list[LinkerHit]
    for h in linker_out.hits:
        c = h.record
        key = (c.db, c.schema, c.table)
        grouped[key].append(h)

    # v22 STAGE A2: index full catalog by (db, schema, table) for residency
    full_table_cols: dict = defaultdict(set)
    if all_catalog_cols is not None:
        for c in all_catalog_cols:
            full_table_cols[(c.db, c.schema, c.table)].add(c.field_path or c.column)

    # Score per table = sum of column hit scores
    table_scores = sorted(
        [(k, sum(h.score for h in v)) for k, v in grouped.items()],
        key=lambda x: -x[1])[:max_tables]
    chosen_tables = [k for k, _ in table_scores]

    # Build PackTable per chosen table.
    tables: list = []
    seen_dbs: dict = defaultdict(set)
    for (db, schema, table) in chosen_tables:
        hits = grouped[(db, schema, table)][:max_cols_per_table]
        cols = []
        for h in hits:
            c = h.record
            name = c.field_path or c.column
            cols.append(asdict(PackColumn(
                name=name,
                type=c.data_type,
                nullable=c.is_nullable,
                description=_short(c.description, max_desc_chars),
            )))
        tdict = asdict(PackTable(
            db=db, schema=schema, table=table,
            score=round(sum(h.score for h in hits), 2),
            columns=cols,
        ))
        # v22 STAGE A2: side-channel full column list for the validator
        if all_catalog_cols is not None:
            tdict['all_columns'] = sorted(full_table_cols.get((db, schema, table), set()))
        tables.append(tdict)
        seen_dbs[db].add(schema)

    databases = [
        {'name': db, 'schemas': sorted(schemas),
          'score': round(sum(linker_out.db_score.get(f'{db}.{s}', 0.0) for s in schemas), 2)}
        for db, schemas in seen_dbs.items()
    ]
    databases.sort(key=lambda d: -d['score'])

    # v18.1: detect date-shard families and surface them as wildcards.
    # Spider2-Lite-BQ has many `ga_sessions_YYYYMMDD`, `events_YYYYMMDD`,
    # `bikeshare_trips_YYYYMM` style shards. The pack should advertise
    # the wildcard form so the planner can target it as a closed-set
    # identifier rather than enumerate dates.
    import re as _re
    _SHARD = _re.compile(r'^(?P<base>.+?)_(?P<date>\d{6,8})$')
    wildcards: list = []
    seen_bases: set = set()
    for t in tables:
        m = _SHARD.match(t['table'])
        if not m:
            continue
        key = (t['db'], t['schema'], m.group('base'))
        if key in seen_bases:
            continue
        seen_bases.add(key)
        wildcards.append({
            'fqn': f'{t["db"]}.{t["schema"]}.{m.group("base")}_*',
            'base': m.group('base'),
            'sample_shard': t['table'],
            'note': 'wildcard family — use _TABLE_SUFFIX for date filtering',
        })

    # v22 STAGE A2: derive join_hints from co-occurring column names + FK-like
    # naming conventions across the chosen tables. This is heuristic but
    # deterministic and provides Family C with seed join paths.
    join_hints: list = []
    if all_catalog_cols is not None and len(tables) >= 2:
        # Build full column sets per chosen table (already in `full_table_cols`)
        cols_by_table = {}
        for t in tables:
            key = (t['db'], t['schema'], t['table'])
            cols_by_table[t['table']] = full_table_cols.get(key, set())
        # Pairwise: shared exact-match column names (likely join keys)
        seen_pairs = set()
        table_list = list(cols_by_table.keys())
        for i, ta in enumerate(table_list):
            for tb in table_list[i+1:]:
                shared = cols_by_table[ta] & cols_by_table[tb]
                # Prefer columns that look like keys
                for col in sorted(shared):
                    cn = col.split('.')[-1].lower()
                    is_key = (cn.endswith('_id') or cn == 'id'
                                or cn.endswith('_key') or cn == 'key'
                                or cn.endswith('id') and len(cn) <= 12)
                    if not is_key:
                        continue
                    pair = (ta, tb, col)
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    join_hints.append({
                        'left_table': ta, 'right_table': tb,
                        'on': col,
                        'reason': 'shared_column_name_with_key_shape',
                    })
        # FK-like naming: column `<table>_id` in B referring to `id` in A
        for ta in table_list:
            cols_a = cols_by_table[ta]
            if 'id' not in {c.split('.')[-1].lower() for c in cols_a}:
                continue
            for tb in table_list:
                if tb == ta: continue
                target_fk = ta.lower().rstrip('s') + '_id'
                for col_b in cols_by_table[tb]:
                    cb = col_b.split('.')[-1].lower()
                    if cb == target_fk or cb == ta.lower() + 'id':
                        # find the actual id column in ta
                        id_col = next((c for c in cols_a if c.split('.')[-1].lower() == 'id'), 'id')
                        pair = (ta, tb, f'{id_col}={col_b}')
                        if pair in seen_pairs: continue
                        seen_pairs.add(pair)
                        join_hints.append({
                            'left_table': ta, 'right_table': tb,
                            'on_left': id_col, 'on_right': col_b,
                            'reason': 'fk_like_naming',
                        })
        # Cap to keep prompt small
        join_hints = join_hints[:10]

    pack = {
        'lane': lane,
        'alias': alias,
        'databases': databases,
        'tables': tables,
        'wildcards': wildcards,
        'join_hints': join_hints,
    }
    pack['token_budget_used'] = len(json.dumps(pack)) // 4
    return pack


def pack_to_planner_prompt(pack: dict, question: str, *,
                              external_knowledge: str = '') -> str:
    """Render the pack into the system+user prompt for the structured planner."""
    lines = []
    lines.append('You are an extractive SQL planner. Answer ONLY in JSON.')
    lines.append(f'Lane: {pack.get("lane", "bq")}.')
    if pack.get('alias'):
        lines.append(f'Spider2 alias: {pack["alias"]}')
    lines.append('Available identifiers (closed set; do NOT introduce any others):')
    for t in pack['tables']:
        cols = ', '.join(f"{c['name']}:{c['type'] or '?'}" for c in t['columns'])
        lines.append(f'  - `{t["db"]}.{t["schema"]}.{t["table"]}` columns=[{cols}]')
    if pack.get('wildcards'):
        lines.append('Wildcard table families (prefer these over individual date shards; '
                       'use _TABLE_SUFFIX BETWEEN \'YYYYMMDD\' AND \'YYYYMMDD\'):')
        for w in pack['wildcards']:
            lines.append(f'  - `{w["fqn"]}`  (sample: {w["sample_shard"]})')
    if external_knowledge:
        lines.append('External knowledge:')
        lines.append(external_knowledge)
    lines.append('')
    lines.append('Question: ' + question)
    lines.append('')
    lines.append(_PLANNER_JSON_INSTRUCTIONS)
    return '\n'.join(lines)


_PLANNER_JSON_INSTRUCTIONS = """Return ONE JSON object with this shape:
{
  "selected_database": "<one of pack.databases[*].name>",
  "selected_schema":   "<one of pack.databases[*].schemas[*]>",
  "selected_tables":   ["<from pack.tables[*].table>"],
  "selected_columns":  ["<from pack.tables[*].columns[*].name>"],
  "metrics":           [{"label": str, "expr": str}],
  "filters":           [{"expr": str, "explanation": str}],
  "time_constraints":  [str],
  "grouping":          [str],
  "sorting":           [{"expr": str, "dir": "asc"|"desc"}],
  "limit":             int|null,
  "ambiguity_points":  [str],
  "expected_shape":    str
}
RULES:
- Every identifier in selected_tables, selected_columns, metrics.expr, filters.expr,
  grouping, sorting.expr MUST appear under one of the listed tables OR be a
  wildcard family base name from the wildcard list.
- selected_database is a project NAME like `bigquery-public-data`. NOT
  `bigquery-public-data.google_analytics_sample` and NOT `bq`.
- selected_schema is the dataset/schema NAME like `google_analytics_sample`.
- selected_tables[*] is the bare table name like `ga_sessions_20170201`,
  OR the wildcard form `ga_sessions_*` when querying a date range.
- For date ranges over wildcard tables, set time_constraints with the
  start and end dates and let _TABLE_SUFFIX handle filtering.
- If a column is a struct/array path (contains '.'), keep it as written
  (e.g. `hits.product.productRevenue`).
- Output JSON only. No prose, no fences."""
