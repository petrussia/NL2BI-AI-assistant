"""B3_v1: adaptive retrieval policy on top of B3.

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
    s2 = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s))
    return s2.replace("_", " ").lower()


STOP = {"a","an","the","of","in","on","at","for","to","from","by","with","is","are","was","were",
        "what","which","who","whom","whose","how","many","much","show","list","find","give","me",
        "all","each","every","any","do","does","did","that","this","there","their","them","they"}


def _toks(s):
    parts = re.split(r"[\s_]+", str(s).lower())
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

    return "\n".join(schema_lines)


def make_b3v1_plan_prompt(question: str, ctx: str) -> str:
    """Compact planner prompt — no in-context Knowledge prose, just structured context."""
    return textwrap.dedent(f"""
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
    """).strip()


def make_b3v1_sql_prompt(question: str, plan_obj, ctx: str) -> str:
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Use the schema and the JSON plan to emit one SQLite SQL query.
    Return SQL only. If plan has "distinct": true, prepend SELECT with DISTINCT.
    If plan filters reference subqueries (values starting with "(SELECT"), keep them verbatim in WHERE.

    {ctx}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    """).strip()
