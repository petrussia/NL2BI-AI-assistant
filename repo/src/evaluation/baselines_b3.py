"""B3 minimal viable: dual retrieval (schema + knowledge proxy) + Plan->SQL.

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
    parts = re.split(r"[\s_]+", str(s).lower())
    return {p for p in parts if p and p not in STOP and len(p) > 1}


def _camel_split(s: str):
    s2 = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s))
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
    return "\n".join(parts)


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
    return "\n".join(schema_lines + know_lines)


def make_b3_plan_prompt(question: str, b3_context: str) -> str:
    """B3 planner prompt: same shape as B2_v1 but with dual-retrieval context."""
    return textwrap.dedent(f"""
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
    """).strip()


def make_b3_sql_prompt(question: str, plan_obj, b3_context: str) -> str:
    import json as _json
    plan_pretty = _json.dumps(plan_obj, ensure_ascii=False, indent=2)
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Use the schema, the knowledge descriptions,
    and the JSON plan to emit one SQLite SQL query. Return SQL only, no markdown.
    Honour the plan's distinct flag and any subquery filter values verbatim.

    {b3_context}

    Question: {question}

    Plan:
    {plan_pretty}

    SQL:
    """).strip()
