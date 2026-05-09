# Stage 5+6 (a): author B3_v1 (adaptive retrieval) + B4_final modules.

import datetime as dt
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
EVAL = REPO / 'src' / 'evaluation'
EVAL.mkdir(parents=True, exist_ok=True)
ts = dt.datetime.now(dt.timezone.utc).isoformat()


# ===== B3_v1 module =====
b3v1_src = '''"""B3_v1: adaptive retrieval policy on top of B3.

Differences vs B3:
1. Adaptive knowledge channel: if DB has fewer than KNOWLEDGE_MIN_TABLES (default 5),
   the knowledge channel is OMITTED entirely. Schema linker output is enough.
2. When enabled, knowledge snippets are shorter and more structured (no prose):
   tablename: cols (with PK/FK flags). Top-1 snippet only by default (not top-3).
3. Separate planner context (compact) from synthesizer context (richer).
"""
from __future__ import annotations
import re
import textwrap
from typing import Optional


KNOWLEDGE_MIN_TABLES = 5
KNOWLEDGE_TOP_K_DEFAULT = 1


def _camel_split(s):
    s2 = re.sub(r"([a-z])([A-Z])", r"\\1 \\2", str(s))
    return s2.replace("_", " ").lower()


STOP = {"a","an","the","of","in","on","at","for","to","from","by","with","is","are","was","were",
        "what","which","who","whom","whose","how","many","much","show","list","find","give","me",
        "all","each","every","any","do","does","did","that","this","there","their","them","they"}


def _toks(s):
    parts = re.split(r"[\\s_]+", str(s).lower())
    return {p for p in parts if p and p not in STOP and len(p) > 1}


def build_compact_table_doc(table_idx: int, tables_obj: dict) -> str:
    """Compact one-line per table with name + cols + PK/FK flags. No prose."""
    table_names = tables_obj.get("table_names_original") or tables_obj.get("table_names") or []
    column_names = tables_obj.get("column_names_original") or tables_obj.get("column_names") or []
    pk = set(tables_obj.get("primary_keys") or [])
    fk = tables_obj.get("foreign_keys") or []
    fk_left = {a for a, b in fk}
    cols_here = [(ci, col) for ci, (ti, col) in enumerate(column_names) if ti == table_idx]
    parts = []
    for ci, col in cols_here:
        flags = []
        if ci in pk: flags.append("PK")
        if ci in fk_left: flags.append("FK")
        parts.append(col + (f"[{','.join(flags)}]" if flags else ""))
    return f"{table_names[table_idx]}: {', '.join(parts)}"


def build_compact_knowledge_index(tables_obj: dict):
    n_tables = len(tables_obj.get("table_names_original") or tables_obj.get("table_names") or [])
    return [(i, build_compact_table_doc(i, tables_obj)) for i in range(n_tables)]


def retrieve_knowledge(question: str, knowledge_index, top_k: int = KNOWLEDGE_TOP_K_DEFAULT):
    qt = _toks(question)
    scored = []
    for ti, doc in knowledge_index:
        dt_ = _toks(doc)
        scored.append((ti, doc, len(qt & dt_)))
    scored.sort(key=lambda x: (-x[2], x[0]))
    return scored[:top_k]


def adaptive_b3_context(db_id: str, schema_link: dict, tables_obj: dict,
                        for_planner: bool = True) -> str:
    """Build context. Compact for planner; same content for synthesizer.
    Knowledge channel omitted when DB has < KNOWLEDGE_MIN_TABLES tables."""
    table_names = tables_obj.get("table_names_original") or tables_obj.get("table_names") or []
    column_names = tables_obj.get("column_names_original") or tables_obj.get("column_names") or []
    n_tables = len(table_names)

    by_table = {i: [] for i in range(n_tables)}
    for ti, col in column_names:
        if ti >= 0:
            by_table.setdefault(ti, []).append(col)

    schema_lines = [f"Database: {db_id}", "Schema:"]
    for idx in schema_link["selected_table_indexes"]:
        schema_lines.append(f"- {table_names[idx]}(" + ", ".join(by_table.get(idx, [])) + ")")

    if n_tables >= KNOWLEDGE_MIN_TABLES:
        kindex = build_compact_knowledge_index(tables_obj)
        know_top = retrieve_knowledge(" ".join(schema_link.get("q_tokens", [])) + " " + db_id, kindex,
                                       top_k=KNOWLEDGE_TOP_K_DEFAULT)
        if know_top:
            schema_lines.append("")
            schema_lines.append("Knowledge (top-1 candidate table, compact, proxy from schema metadata):")
            for ti, doc, score in know_top:
                schema_lines.append("- " + doc)

    return "\\n".join(schema_lines)


def make_b3v1_plan_prompt(question: str, ctx: str) -> str:
    """Compact planner prompt — no in-context Knowledge prose, just structured context."""
    return textwrap.dedent(f\"\"\"
    You are a SQL planner. Output one JSON plan only. No prose, no markdown fences.
    Allowed fields (additionalProperties:false enforced downstream):
    intent (enum: select_count, select_aggregate, select_filter, select_join,
    select_groupby, select_orderby, select_other), tables (array of names),
    operations (array of short verbs), distinct (boolean), columns, filters,
    aggregations, group_by, order_by, limit, joins, notes.
    Required: intent, tables, operations.

    Subquery filter pattern (for "X of the youngest/largest/..."):
    use filters with a subquery value, e.g. {{"column":"Age","op":"=","value":"(SELECT MIN(Age) FROM singer)"}}.
    Distinct pattern: set "distinct": true for "all distinct/unique/different X" questions.

    {ctx}

    Question: {question}
    JSON plan:
    \"\"\").strip()


def make_b3v1_sql_prompt(question: str, plan_obj, ctx: str) -> str:
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f\"\"\"
    You are a text-to-SQL assistant. Use the schema and the JSON plan to emit one SQLite SQL query.
    Return SQL only. If plan has "distinct": true, prepend SELECT with DISTINCT.
    If plan filters reference subqueries (values starting with "(SELECT"), keep them verbatim in WHERE.

    {ctx}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    \"\"\").strip()
'''
(EVAL / 'baselines_b3_v1.py').write_text(b3v1_src, encoding='utf-8')


# ===== B4_final module (B4-lite-final, builds on B3_v1) =====
b4f_src = '''"""B4_final: B3_v1 base + SELECT-only guard + multi-candidate + bounded repair.

Honest naming: this is still NOT true grammar-constrained decoding (no XGrammar
or Outlines). The validation is post-hoc regex/AST. Nothing changed from B4-lite
in terms of "constrained decoding" approximation; the name "_final" is for
positioning relative to B4-lite, not a claim that the spec is fully closed.
"""
from __future__ import annotations
import re
import textwrap


_FORBIDDEN_KEYWORDS = re.compile(
    r"\\b(insert|update|delete|drop|create|alter|truncate|replace|pragma|attach|detach|grant|revoke)\\b",
    re.IGNORECASE,
)
_SELECT_HEAD = re.compile(r"^\\s*(?:with\\s+.+?\\s+as\\s+\\(.+?\\)\\s*,?\\s*)*\\s*select\\b",
                          re.IGNORECASE | re.DOTALL)


def is_safe_select(sql: str):
    s = (sql or "").strip().rstrip(";").strip()
    if not s: return False, "empty"
    m = _FORBIDDEN_KEYWORDS.search(s)
    if m: return False, f"forbidden_keyword:{m.group(0).lower()}"
    if not _SELECT_HEAD.match(s): return False, "does_not_start_with_select"
    return True, ""


def make_repair_prompt(question, plan_obj, ctx, prev_sql, error_msg):
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f\"\"\"
    Your previous SQL produced an error. Generate a fixed SQLite SQL query.
    Return SQL only, no markdown.

    {ctx}

    Question: {question}

    Plan:
    {plan_pretty}

    Previous SQL (FAILED):
    {prev_sql}

    Error:
    {error_msg[:300]}

    Fixed SQL:
    \"\"\").strip()


def consistency_pick(candidate_results):
    if not candidate_results: return None, "no_candidates"
    executable = [(sql, rows) for sql, ex, rows, _ in candidate_results if ex]
    if not executable: return candidate_results[0][0], "no_executable"
    from collections import Counter
    counts = Counter(tuple(sorted(r)) for _, r in executable)
    best, _ = counts.most_common(1)[0]
    for sql, rows in executable:
        if tuple(sorted(rows)) == best: return sql, "consistency_winner"
    return executable[0][0], "fallback"
'''
(EVAL / 'baselines_b4_final.py').write_text(b4f_src, encoding='utf-8')


# ===== Design notes =====
b3v1_design = f'''# B3_v1 Design Decision

Date: {ts}

## Why B3_v1
B3 (knowledge proxy on top of B2_v1) regressed on smoke10: EX dropped to 0.2 with 8/10 plan_invalid. The longer prompt confused the planner more than it helped on tiny `concert_singer` (4 tables).

## What changes in v1
1. **Adaptive knowledge channel**: if `n_tables(db) < 5`, the knowledge channel is OMITTED entirely; the prompt is identical to B2_v1's reduced-schema prompt.
2. **Compact knowledge snippets**: when enabled, top-1 snippet (not top-3), one line per table with name + cols + PK/FK flags. No prose.
3. **Compact planner prompt**: no embedded "Knowledge (synthetic proxy docs derived from schema metadata):" verbose preamble. Just `Schema:` + (optional) `Knowledge:` block.
4. **Same content for synthesizer**: same context object reused; no separate "richer" version this iteration (separating context per stage was deferred — current change already addresses the over-prompt issue).

## Acceptance for B3_v1 smoke10
- plan_valid_count ≥ 9/10 (recover from B3 = 2/10).
- EX ≥ B2_v1's EX (≥ 0.8). Ideally ≥ 0.9.

## Out of v1 scope
- Embedding-based retrieval.
- Cross-DB retrieval (kept in retrieval.py for B1R/B2R baselines).
- Real domain documentation ingestion.
'''
(OUTPUTS / 'logs' / 'b3v1_design_decision.md').write_text(b3v1_design, encoding='utf-8')


b4f_design = f'''# B4_final Design Decision

Date: {ts}

## Why B4_final
B4-lite was correct as a system but inherited B3's planner failures upstream. By moving its base from B3 to B3_v1, the upstream is now (we expect) reliable. Otherwise the design is unchanged from B4-lite.

## What B4_final implements
1. **SELECT-only AST guard** (`is_safe_select`) — same regex-based gate. Forbidden: INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/REPLACE/PRAGMA/ATTACH/DETACH/GRANT/REVOKE.
2. **Multi-candidate generation**: `num_return_sequences=3`, T=0.7, top_p=0.95.
3. **Execution-guided selection**: pick the candidate whose result row-multiset matches the most others (consistency); tie-break first executable.
4. **Bounded repair**: depth=1; if no executable candidate, regenerate ONCE with the SQLite error message appended to the prompt.

## Honest naming
This is still **B4-lite-style**: no true grammar-constrained decoding (XGrammar / Outlines / Guidance). The constrained decoding requirement is *approximated* by the post-hoc safety gate. Documented in `b4_final_validation_policy.md`.

## Acceptance for B4_final smoke10
- plan_valid_count = same as B3_v1 (B4_final does not change the planner).
- EX ≥ B3_v1's EX. Ideally ≥ 0.9.
- Validation gate triggers ≥ 0 times (sanity: should not trigger on benign Spider questions; if it does, something else is wrong).
'''
(OUTPUTS / 'logs' / 'b4_final_design_decision.md').write_text(b4f_design, encoding='utf-8')

b4f_policy = f'''# B4_final Validation Policy

Date: {ts}

## SELECT-only guard
Implemented as `is_safe_select` in `baselines_b4_final.py`. Forbidden keywords (case-insensitive, word-boundary):
INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, REPLACE, PRAGMA, ATTACH, DETACH, GRANT, REVOKE.

A candidate must:
- Be non-empty after stripping whitespace and trailing semicolon.
- NOT contain any forbidden keyword as a word.
- Start with `SELECT` (optionally preceded by `WITH ... AS (...)` CTE block).

If a candidate fails, it is dropped from the pool.

## Repair policy
Triggered only when zero candidates execute successfully. One retry per item (bounded). The retry prompt embeds the previous SQL and SQLite error (truncated to 300 chars). The retry candidate is also subject to the safety gate and execution check.

## Selection policy
Group executable candidates by their result (sorted row tuple). Pick the SQL whose result group is largest (consistency). Tie-break: first executable candidate in original generation order.

## Out of policy scope (deferred to next iterations)
- True grammar-constrained decoding via XGrammar/Outlines/Guidance.
- Cost-based query planning checks (no EXPLAIN cost analysis).
- Schema-aware AST validation (rejection of unknown tables/columns by AST).
- Query rewriting beyond regex-based replacement.
'''
(OUTPUTS / 'logs' / 'b4_final_validation_policy.md').write_text(b4f_policy, encoding='utf-8')

print(f'WROTE {EVAL / "baselines_b3_v1.py"} ({(EVAL / "baselines_b3_v1.py").stat().st_size} B)')
print(f'WROTE {EVAL / "baselines_b4_final.py"} ({(EVAL / "baselines_b4_final.py").stat().st_size} B)')
print(f'WROTE {OUTPUTS / "logs" / "b3v1_design_decision.md"}')
print(f'WROTE {OUTPUTS / "logs" / "b4_final_design_decision.md"}')
print(f'WROTE {OUTPUTS / "logs" / "b4_final_validation_policy.md"}')
print('STATUS=DONE')
