# Stages 3-4 (a): author B3 (dual retrieval) + B4 (validation/repair/multi-candidate)
# modules + design notes + B4 validation policy. No inference yet.

import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
DOCS = REPO / 'docs'
EVAL = REPO / 'src' / 'evaluation'
DOCS.mkdir(parents=True, exist_ok=True)
EVAL.mkdir(parents=True, exist_ok=True)
ts = dt.datetime.now(dt.timezone.utc).isoformat()


# ===== B3 module =====
b3_src = '''"""B3 minimal viable: dual retrieval (schema + knowledge proxy) + Plan->SQL.

Two retrieval channels:
  1. Schema retrieval: reuses lexical_schema_linking (B1-style) within the given db_id.
  2. Knowledge retrieval: lexical scoring over a synthetic per-table documentation
     proxy derived from table/column names + PK/FK metadata. Marked as proxy in
     audit, not real enterprise docs.

Both channels are merged into the prompt context as "Schema:" and "Knowledge:" blocks.
Then B2_v1 planner + plan->SQL stages are used.
"""
from __future__ import annotations
import re
import textwrap


STOP = {"a","an","the","of","in","on","at","for","to","from","by","with","is","are","was","were",
        "what","which","who","whom","whose","how","many","much","show","list","find","give","me",
        "all","each","every","any","do","does","did","that","this","there","their","them","they"}


def _toks(s: str):
    parts = re.split(r"[\\s_]+", str(s).lower())
    return {p for p in parts if p and p not in STOP and len(p) > 1}


def _camel_split(s: str):
    s2 = re.sub(r"([a-z])([A-Z])", r"\\1 \\2", str(s))
    return s2.replace("_", " ").lower()


def build_table_doc(db_id: str, table_idx: int, tables_obj: dict) -> str:
    """Synthetic per-table description from schema metadata."""
    table_names = tables_obj.get("table_names_original") or tables_obj.get("table_names") or []
    column_names = tables_obj.get("column_names_original") or tables_obj.get("column_names") or []
    pk = tables_obj.get("primary_keys") or []
    fk = tables_obj.get("foreign_keys") or []
    column_types = tables_obj.get("column_types") or []

    name = table_names[table_idx]
    pretty = _camel_split(name)
    cols_here = [(ci, col, column_types[ci] if ci < len(column_types) else None)
                 for ci, (ti, col) in enumerate(column_names) if ti == table_idx]
    pk_set = set(pk)
    fk_map = {a: b for a, b in fk}
    rfk_map = {b: a for a, b in fk}
    parts = [f"Table {name}: domain entity {pretty!r}.",
             f"Columns:"]
    for ci, col, ctype in cols_here:
        flags = []
        if ci in pk_set: flags.append("PK")
        if ci in fk_map: flags.append(f"FK->col#{fk_map[ci]}")
        if ci in rfk_map: flags.append(f"referenced by col#{rfk_map[ci]}")
        if ctype: flags.append(ctype)
        parts.append(f"  - {col}" + (f" [{', '.join(flags)}]" if flags else ""))
    return "\\n".join(parts)


def build_knowledge_index(db_id: str, tables_obj: dict):
    """Return list of (table_idx, doc_text) for the DB."""
    table_names = tables_obj.get("table_names_original") or tables_obj.get("table_names") or []
    return [(i, build_table_doc(db_id, i, tables_obj)) for i in range(len(table_names))]


def retrieve_knowledge(question: str, knowledge_index, top_k: int = 3):
    """Score each (table_idx, doc_text) by lexical overlap with the question."""
    qt = _toks(question)
    scored = []
    for ti, doc in knowledge_index:
        dt = _toks(doc)
        overlap = len(qt & dt)
        scored.append((ti, doc, overlap))
    scored.sort(key=lambda x: (-x[2], x[0]))
    return scored[:top_k]


def build_b3_context(db_id: str, schema_link: dict, tables_obj: dict, top_k_knowledge: int = 3):
    """Build the dual-retrieval context: Schema (linker) + Knowledge (proxy docs)."""
    table_names = tables_obj.get("table_names_original") or tables_obj.get("table_names") or []
    column_names = tables_obj.get("column_names_original") or tables_obj.get("column_names") or []

    by_table = {i: [] for i in range(len(table_names))}
    for ti, col in column_names:
        if ti >= 0:
            by_table.setdefault(ti, []).append(col)

    schema_lines = [f"Database: {db_id}", "Schema (relevant tables):"]
    for idx in schema_link["selected_table_indexes"]:
        schema_lines.append(f"- {table_names[idx]}(" + ", ".join(by_table.get(idx, [])) + ")")

    kindex = build_knowledge_index(db_id, tables_obj)
    knowledge_top = retrieve_knowledge(" ".join(schema_link.get("q_tokens", [])) + " " + db_id,
                                       kindex, top_k=top_k_knowledge)
    know_lines = ["", "Knowledge (synthetic proxy docs derived from schema metadata):"]
    for ti, doc, score in knowledge_top:
        know_lines.append(doc)
    return "\\n".join(schema_lines + know_lines)


def make_b3_plan_prompt(question: str, b3_context: str) -> str:
    """B3 planner prompt: same shape as B2_v1 but with dual-retrieval context."""
    return textwrap.dedent(f\"\"\"
    You are a SQL planner with access to two information sources:
    a Schema block listing tables and columns, and a Knowledge block with
    short proxy descriptions of those tables.

    Output one JSON plan only. No prose, no markdown fences. Allowed fields:
    intent (enum: select_count, select_aggregate, select_filter, select_join,
    select_groupby, select_orderby, select_other), tables (array of names),
    operations (array of short verbs), distinct (boolean), columns, filters,
    aggregations, group_by, order_by, limit, joins, notes.
    Required: intent, tables, operations.

    {b3_context}

    Question: {question}
    JSON plan:
    \"\"\").strip()


def make_b3_sql_prompt(question: str, plan_obj, b3_context: str) -> str:
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f\"\"\"
    You are a text-to-SQL assistant. Use the schema, the knowledge descriptions,
    and the JSON plan to emit one SQLite SQL query. Return SQL only, no markdown.
    Honour the plan's distinct flag and any subquery filter values verbatim.

    {b3_context}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    \"\"\").strip()
'''
(EVAL / 'baselines_b3.py').write_text(b3_src, encoding='utf-8')


# ===== B4 module =====
b4_src = '''"""B4-lite: B3 base + SELECT-only guard + bounded repair + multi-candidate selection.

Honest naming: this is B4-lite, NOT full grammar-constrained decoding (XGrammar/Outlines).
We approximate constrained decoding via post-hoc AST/regex validation gates.

Pipeline per item:
  1. Run B3 planner stage to get a JSON plan (validated).
  2. Generate K candidate SQLs (sampling temperature 0.7, num_return_sequences=K).
  3. AST/regex guard each candidate: SELECT-only (no INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/REPLACE/PRAGMA).
  4. Execute each surviving candidate against the gold DB with 8s timeout.
  5. Pick the candidate by consistency (most candidates agreeing on a row-multiset).
     Tie-break: first executable.
  6. Bounded repair: if NO candidate executable, retry SQL gen once with the error message
     appended to the prompt. Single retry, bounded to 1.
"""
from __future__ import annotations
import re
import textwrap


# Regex-based SQL safety guard (post-hoc constrained decoding approximation)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\\b(insert|update|delete|drop|create|alter|truncate|replace|pragma|attach|detach|grant|revoke)\\b",
    re.IGNORECASE,
)
_SELECT_HEAD = re.compile(r"^\\s*(?:with\\s+.+?\\s+as\\s+\\(.+?\\)\\s*,?\\s*)*\\s*select\\b", re.IGNORECASE | re.DOTALL)


def is_safe_select(sql: str) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means SQL is rejected."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return False, "empty"
    if _FORBIDDEN_KEYWORDS.search(s):
        m = _FORBIDDEN_KEYWORDS.search(s)
        return False, f"forbidden_keyword:{m.group(0).lower()}"
    if not _SELECT_HEAD.match(s):
        return False, "does_not_start_with_select"
    return True, ""


def make_repair_prompt(question: str, plan_obj, b3_context: str, prev_sql: str, error_msg: str) -> str:
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f\"\"\"
    Your previous SQL produced an error. Generate a fixed SQLite SQL query.
    Return SQL only, no markdown, no prose.

    {b3_context}

    Question: {question}

    Plan:
    {plan_pretty}

    Previous SQL (FAILED):
    {prev_sql}

    Error message:
    {error_msg[:300]}

    Fixed SQL:
    \"\"\").strip()


def consistency_pick(candidate_results):
    """candidate_results = list of (sql, executable, rows_or_None, error).

    Group executable candidates by their result (sorted row tuple).
    Return the SQL whose result group is largest (consistency); tie-break: first.
    If no executable, return the first candidate (signals failure to caller).
    """
    if not candidate_results:
        return None, "no_candidates"
    executable = [(sql, rows) for sql, ex, rows, _ in candidate_results if ex]
    if not executable:
        return candidate_results[0][0], "no_executable"
    from collections import Counter
    counts = Counter(tuple(sorted(r)) for _, r in executable)
    best_result, _ = counts.most_common(1)[0]
    for sql, rows in executable:
        if tuple(sorted(rows)) == best_result:
            return sql, "consistency_winner"
    return executable[0][0], "fallback"
'''
(EVAL / 'baselines_b4.py').write_text(b4_src, encoding='utf-8')


# ===== Design notes =====
b3_design = f'''# B3 Design Decision

Date: {ts}

## Scope
B3 = B2_v1 + dual retrieval. Adds two information sources to the prompt:
1. Schema (lexical schema linker — same as B1; reduced relevant tables).
2. Knowledge (synthetic per-table proxy documentation derived from schema metadata).

## Knowledge proxy
The thesis target is enterprise-data-from-heterogeneous-sources, which expects
real domain documentation. Spider has no such documentation. We construct a proxy:
for each table, we emit a short text describing the entity (table name pretty-print),
its columns with PK/FK flags and types from `tables.json`. This is **honestly
labeled as proxy** in `b3_retrieval_audit.md` and in code comments.

For real enterprise data, this proxy would be replaced with curated docs,
glossaries, ontology snippets, etc.

## Retrieval
Both channels use lexical overlap (table name × 2, column name × 1, knowledge
doc tokens × 1). Top-k tables and top-k knowledge snippets are combined.
No embeddings; consistent with the B1 baseline weight scheme.

## Why no embeddings yet
- Embeddings add a heavy dependency (sentence-transformers / FAISS).
- Spider's small per-DB schema (avg ~5 tables) makes lexical retrieval
  competitive within a single DB.
- Cross-DB embedding retrieval is the next-iteration upgrade.

## Out of B3 scope
- Repair / retry on SQL execution failure (B4).
- Multi-candidate generation + selection (B4).
- Cross-DB retrieval (B1R/B2R, separate baselines).
- Real grammar-constrained decoding (planned for B4 if time permits — currently approximated).

## Acceptance for B3 smoke10
- B3 plan_valid_count ≥ 9/10 (do not regress relative to B2_v1).
- B3 EX ≥ B2_v1 EX (0.8) on smoke10.
'''
(OUTPUTS / 'logs' / 'b3_design_decision.md').write_text(b3_design, encoding='utf-8')


b4_design = f'''# B4 (B4-lite) Design Decision

Date: {ts}

## Scope of "minimal viable full system"
Per ТЗ, B4 should close: validation + safety/SELECT-only constraints + bounded repair
+ multi-candidate generation + execution-guided selection + (ideally) constrained decoding.

## What this iteration implements (B4-lite)
1. **SELECT-only guard** (full): regex AST gate rejects SQL containing INSERT, UPDATE,
   DELETE, DROP, CREATE, ALTER, TRUNCATE, REPLACE, PRAGMA, ATTACH, DETACH, GRANT, REVOKE.
   Implemented in `is_safe_select`. Real test: blocks anything that mutates state.
2. **Bounded repair loop** (full, depth=1): if no candidate executes successfully,
   the agent regenerates ONCE with the error message appended to the prompt.
3. **Multi-candidate generation** (3 candidates): `model.generate` with
   `num_return_sequences=3`, temperature=0.7, top_p=0.95. Single forward batch.
4. **Execution-guided selection**: candidates are executed; selection picks the SQL
   whose result row-multiset agrees with the most other candidates (consistency).
   Tie-break: first executable. If none executable, repair once.
5. **Constrained decoding** (approximated): NOT true grammar-constrained generation
   (XGrammar / Outlines / Guidance is omitted in this iteration to keep scope honest).
   We approximate with the regex/AST guard (see #1). Item is documented in
   `outputs/logs/b4_validation_policy.md`.

## Why B4-lite, not full B4
- True grammar-constrained decoding requires patching the model's logits at
  generation time. The runtime stack (Qwen 4-bit + bitsandbytes) interacts
  awkwardly with grammar libraries; integration cost is non-trivial.
- The regex/AST guard catches the actually dangerous outputs (state mutation),
  which is the production-relevant subset of constrained decoding.
- Multi-candidate + consistency selection achieves much of what XGrammar
  buys at evaluation time: it filters out malformed SQL by execution, not by grammar.

This is an honest deviation from the proposal and is documented as such.

## Acceptance for B4-lite smoke10
- B4 plan_valid_count ≥ 9/10 (do not regress).
- B4 EX ≥ B2_v1 EX (0.8) on smoke10.
- Zero unsafe SQL pass through (≥1 candidate must clear SELECT-only guard per item or repair triggers).
'''
(OUTPUTS / 'logs' / 'b4_design_decision.md').write_text(b4_design, encoding='utf-8')


b4_policy = f'''# B4 Validation Policy

Date: {ts}

## SELECT-only guard
Implemented as a regex AST gate (`is_safe_select` in `baselines_b4.py`).
Forbidden keywords (case-insensitive, word-boundary):
- INSERT, UPDATE, DELETE
- DROP, CREATE, ALTER, TRUNCATE, REPLACE
- PRAGMA, ATTACH, DETACH, GRANT, REVOKE

A candidate SQL must:
- Be non-empty after stripping whitespace and trailing semicolon.
- NOT contain any forbidden keyword as a word.
- Start with `SELECT` (optionally preceded by a CTE `WITH ... AS (...)` block).

If a candidate fails, it is dropped from the candidate pool. If no candidate
clears the guard, repair is invoked once.

## Repair policy
- Triggered only when zero candidates execute successfully.
- One retry per item (bounded to 1).
- The retry prompt includes the previous SQL and the SQLite error message
  (truncated to 300 chars).
- The retry candidate is also subject to the SELECT-only guard and execution check.
- If retry also fails, the item is recorded as `error_type=no_executable_candidate`.

## Selection policy
- Group executable candidates by their result (sorted row tuple).
- Pick the SQL whose result-group is largest (consistency).
- Tie-break: first candidate in original generation order.
- This favours answers that multiple decodings agree on, which is a cheap
  proxy for self-consistency.

## What this policy does NOT do (deferred)
- True grammar-constrained decoding (XGrammar/Outlines/Guidance) — approximated by post-hoc guard.
- Cost-based query planning checks (no EXPLAIN cost analysis).
- Schema-aware AST validation (no rejection of unknown tables/columns by AST).
- Differential testing vs gold (production gate would, evaluator does).
'''
(OUTPUTS / 'logs' / 'b4_validation_policy.md').write_text(b4_policy, encoding='utf-8')


print(f'WROTE {EVAL / "baselines_b3.py"} ({(EVAL / "baselines_b3.py").stat().st_size} B)')
print(f'WROTE {EVAL / "baselines_b4.py"} ({(EVAL / "baselines_b4.py").stat().st_size} B)')
print(f'WROTE {OUTPUTS / "logs" / "b3_design_decision.md"}')
print(f'WROTE {OUTPUTS / "logs" / "b4_design_decision.md"}')
print(f'WROTE {OUTPUTS / "logs" / "b4_validation_policy.md"}')
print('STATUS=DONE')
