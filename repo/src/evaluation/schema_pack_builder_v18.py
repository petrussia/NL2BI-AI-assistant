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
               max_desc_chars: int = 120) -> dict:
    # Group hits by (db, schema, table). Use the highest-scoring table set.
    grouped: dict = defaultdict(list)  # (db, schema, table) -> list[LinkerHit]
    for h in linker_out.hits:
        c = h.record
        key = (c.db, c.schema, c.table)
        grouped[key].append(h)

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
        tables.append(asdict(PackTable(
            db=db, schema=schema, table=table,
            score=round(sum(h.score for h in hits), 2),
            columns=cols,
        )))
        seen_dbs[db].add(schema)

    databases = [
        {'name': db, 'schemas': sorted(schemas),
          'score': round(sum(linker_out.db_score.get(f'{db}.{s}', 0.0) for s in schemas), 2)}
        for db, schemas in seen_dbs.items()
    ]
    databases.sort(key=lambda d: -d['score'])

    pack = {
        'lane': lane,
        'alias': alias,
        'databases': databases,
        'tables': tables,
        'wildcards': [],
        'join_hints': [],
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
  grouping, sorting.expr MUST appear under one of the listed tables.
- If a column is a struct/array path (contains '.'), keep it as written.
- Output JSON only. No prose, no fences."""
