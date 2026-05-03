"""planner_v2 — LM-driven structured plan generation for the Phase B stack.

Produces a JSON plan matching plan_schema_v5.json. Designed to maximise
parse-success and schema-validity (the v4 planner failed validation 99.6% on
BIRD; we trade prompt verbosity and few-shot examples for valid output).

Public API:
  make_planner_prompt(question, schema_text, fk_summary, evidence='', dialect='sqlite') -> str
  parse_plan(raw_text) -> tuple[plan_dict | None, error_str]
  validate_plan(plan, schema_path) -> tuple[bool, error_str]
  link_plan_to_ir(plan, ir) -> dict (audit: unknown_tables/columns/edges + auto-fixes)
"""
from __future__ import annotations
import json
import re
import textwrap
from pathlib import Path
from typing import Any

# jsonschema is optional — soft-fail to a structural check if missing.
try:
    import jsonschema
    HAVE_JSONSCHEMA = True
except Exception:
    HAVE_JSONSCHEMA = False


_FEW_SHOT = """
Example 1 — count over a single table:
Question: How many singers are from Germany?
Plan:
{
  "answer_shape": "scalar",
  "measures": [{"agg": "count", "expr": "*", "alias": "n"}],
  "dimensions": [],
  "filters": [{"expr": "singer.country", "op": "=", "rhs": "Germany", "rhs_type": "string"}],
  "join_anchor_nodes": ["singer"],
  "join_path_ids": [],
  "having": [], "ordering": [], "limit": null,
  "distinct": false, "set_operation": null,
  "requires_nested": false, "requires_window": false,
  "time_grain": null, "dialect": "sqlite", "confidence": 0.92
}

Example 2 — group by + ORDER BY + LIMIT (top-k):
Question: List the top 3 stadiums by capacity, descending.
Plan:
{
  "answer_shape": "table",
  "measures": [{"agg": "none", "expr": "stadium.name"}, {"agg": "none", "expr": "stadium.capacity"}],
  "dimensions": [],
  "filters": [],
  "join_anchor_nodes": ["stadium"],
  "join_path_ids": [],
  "having": [],
  "ordering": [{"expr": "stadium.capacity", "direction": "desc"}],
  "limit": 3,
  "distinct": false, "set_operation": null,
  "requires_nested": false, "requires_window": false,
  "time_grain": null, "dialect": "sqlite", "confidence": 0.90
}

Example 3 — join + group-by + having:
Question: Show concert names where more than 2 singers performed.
Plan:
{
  "answer_shape": "grouped",
  "measures": [{"agg": "count", "expr": "singer_in_concert.singer_id", "alias": "n_singers"}],
  "dimensions": [{"expr": "concert.concert_name"}],
  "filters": [],
  "join_anchor_nodes": ["concert"],
  "join_path_ids": [["concert.concert_id -> singer_in_concert.concert_id"]],
  "having": [{"agg": "count", "expr": "singer_in_concert.singer_id", "op": ">", "rhs": 2, "rhs_type": "int"}],
  "ordering": [],
  "limit": null,
  "distinct": false, "set_operation": null,
  "requires_nested": false, "requires_window": false,
  "time_grain": null, "dialect": "sqlite", "confidence": 0.88
}
""".strip()


_PLANNER_INSTRUCTIONS = """
You are a SQL planner. Given a natural-language question and a database
schema, produce a SINGLE JSON object that follows the plan format below.
The downstream compiler is deterministic — produce valid JSON only and
prefer simple plans over clever ones. NEVER write SQL strings in the plan;
the compiler will render SQL from the plan.

Hard rules:
- Output JSON only — no prose, no markdown, no comments.
- Every "expr" must be qualified as "table.column" using identifiers from the schema.
- "join_anchor_nodes" must be at least one table from the schema.
- Each "join_path_ids" entry is a list of edges in the form "tableA.colA -> tableB.colB".
- If you need a feature outside the supported list (window functions, recursive CTE,
  exotic functions), set "requires_window" or "requires_nested" to true and the
  compiler will emit a skeleton.
- For BIRD-style domain hints, use them to pick the correct columns and
  filter values — the hint may name the gold formula directly.

Supported families: scalar/grouped aggregates (count, count_distinct, sum, avg,
min, max), filters (=, !=, <, <=, >, >=, in, not in, like, between, is null,
is not null), distinct, group-by, having, order-by + limit, simple INNER joins
along the supplied FK edges, and set operations (union/intersect/except).
""".strip()


def make_planner_prompt(question: str, schema_text: str, *,
                         fk_summary: str = '',
                         evidence: str = '',
                         dialect: str = 'sqlite') -> str:
    extra = ''
    if evidence:
        extra = f'\n\nDomain hints (apply if relevant; ignore otherwise):\n{evidence.strip()}'
    fk_block = ''
    if fk_summary:
        fk_block = f'\n\nKnown FK edges:\n{fk_summary}'
    prompt = f"""{_PLANNER_INSTRUCTIONS}

Few-shot examples:
{_FEW_SHOT}

Schema (dialect={dialect}):
{schema_text}{fk_block}{extra}

Question: {question}

JSON plan:
""".strip()
    return prompt


# ---------------- parse + validate ----------------

_JSON_RE = re.compile(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', re.DOTALL)


def parse_plan(raw_text: str) -> tuple[dict | None, str]:
    """Extract the first JSON object from the LM output. Tolerant of
    wrapping prose / markdown / code fences."""
    if not raw_text: return None, 'empty_text'
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?', '', text, flags=re.I).strip()
    text = re.sub(r'```$', '', text).strip()
    # Try direct parse
    try:
        obj = json.loads(text)
        return (obj, '') if isinstance(obj, dict) else (None, f'top_level_not_object:{type(obj).__name__}')
    except Exception:
        pass
    # Find first balanced JSON object
    for m in _JSON_RE.finditer(text):
        chunk = m.group(0)
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict): return obj, ''
        except Exception:
            continue
    return None, 'no_json_found'


def validate_plan(plan: dict, schema_path: str | Path | None = None) -> tuple[bool, str]:
    """Validate against plan_schema_v5.json if jsonschema is available, else
    do a structural check (presence of required keys + types)."""
    if HAVE_JSONSCHEMA and schema_path and Path(schema_path).exists():
        schema = json.loads(Path(schema_path).read_text(encoding='utf-8'))
        try:
            jsonschema.validate(plan, schema)
            return True, ''
        except jsonschema.ValidationError as exc:
            return False, f'jsonschema:{exc.message[:160]}'
        except Exception as exc:
            return False, f'jsonschema_engine:{type(exc).__name__}'
    # Soft structural check
    if 'answer_shape' not in plan: return False, 'missing:answer_shape'
    if plan.get('answer_shape') not in ('scalar', 'table', 'grouped'):
        return False, f'invalid_answer_shape:{plan.get("answer_shape")}'
    anchors = plan.get('join_anchor_nodes')
    if not isinstance(anchors, list) or not anchors: return False, 'missing:join_anchor_nodes'
    return True, ''


# ---------------- link/auto-fix to schema IR ----------------

def link_plan_to_ir(plan: dict, ir) -> dict:
    """Best-effort: ensure tables/columns referenced by the plan exist in
    the IR. Drop unknown filters/dimensions/measures (record them in audit),
    keep the rest. Returns audit dict; mutates plan in place when safe.
    """
    audit = {'unknown_tables': [], 'unknown_columns': [], 'auto_drops': []}
    table_set = {t.name for t in ir.tables}
    col_set = {(c.table_name, c.name) for c in ir.all_columns()}

    def _norm(qual: str) -> tuple[str, str] | None:
        if not isinstance(qual, str): return None
        s = qual.strip().lower()
        if '.' not in s: return None
        t, c = s.split('.', 1)
        return (t, c)

    # 0. Anchors
    new_anchors = []
    for a in plan.get('join_anchor_nodes', []):
        if a.lower() in table_set: new_anchors.append(a)
        else: audit['unknown_tables'].append(a)
    plan['join_anchor_nodes'] = new_anchors or list(table_set)[:1]

    # 1. Filters / dimensions / measures
    for key in ('filters', 'dimensions'):
        kept = []
        for item in plan.get(key, []) or []:
            tc = _norm(item.get('expr'))
            if tc is None: audit['auto_drops'].append({'key': key, 'item': item, 'why': 'unparsed_expr'})
            elif tc not in col_set:
                if tc[1] == '*' and tc[0] in table_set:
                    kept.append(item); continue
                audit['unknown_columns'].append('.'.join(tc))
                audit['auto_drops'].append({'key': key, 'item': item, 'why': 'unknown_col'})
            else:
                kept.append(item)
        plan[key] = kept

    # 2. Measures: leave count(*) alone
    kept = []
    for m in plan.get('measures', []) or []:
        expr = m.get('expr')
        if expr in ('*', None): kept.append(m); continue
        tc = _norm(expr)
        if tc and (tc in col_set or tc[1] == '*'):
            kept.append(m)
        else:
            audit['unknown_columns'].append(str(expr))
            audit['auto_drops'].append({'key': 'measures', 'item': m, 'why': 'unknown_col'})
    plan['measures'] = kept

    # 3. Join paths
    edge_re = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*$')
    fk_set = {(e.from_table, e.from_column, e.to_table, e.to_column) for e in ir.fk_edges}
    fk_set |= {(e.to_table, e.to_column, e.from_table, e.from_column) for e in ir.fk_edges}
    new_paths = []
    for path in plan.get('join_path_ids', []) or []:
        new_path = []
        for edge in path:
            m = edge_re.match(edge)
            if not m:
                audit['auto_drops'].append({'key': 'join_path_ids', 'edge': edge, 'why': 'unparsed'})
                continue
            tup = tuple(x.lower() for x in m.groups())
            if tup not in fk_set and (tup[0], tup[1]) not in {(t, c) for (t, c) in col_set}:
                audit['auto_drops'].append({'key': 'join_path_ids', 'edge': edge, 'why': 'unknown_or_not_fk'})
                continue
            new_path.append(edge)
        if new_path: new_paths.append(new_path)
    plan['join_path_ids'] = new_paths

    return audit
