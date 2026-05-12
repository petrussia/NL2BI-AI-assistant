"""B3_v3: hybrid retrieval over schema chunks + direct SQL (NO planner).

This is the *key* v3 ablation: it isolates the contribution of better retrieval
from the contribution of the planner stack. If B3_v3 beats B0 on multidb_30 or
bird_minidev_30 while B2_v2/B4_v2 do not, the conclusion is:
**retrieval helps, planner does not** — a strong scientific result.

Stack:
1. ``retrieval_hybrid.hybrid_retrieve_tables`` — BM25 + char n-gram + RRF fusion
   over table/column/fk chunks (no GPU model needed by default).
2. Anti-overpruning: if reduction is too aggressive AND confidence is high,
   keep the reduced selection; if confidence is low OR selection is too close
   to full schema, escalate to full-schema (B0).
3. Direct SQL prompt over the resulting schema view (no JSON plan, no
   multi-cand, no repair).

Public API:
- retrieve_for_b3v3(question, db_id, tables_meta) -> dict
- make_b3v3_prompt(question, db_id, tables_meta, build_full_schema, build_reduced_schema)
"""
from __future__ import annotations
import textwrap

from retrieval_hybrid import hybrid_retrieve_tables


def retrieve_for_b3v3(question: str, db_id: str, tables_meta: dict,
                       k_tables: int = 5,
                       low_confidence_threshold: float = 0.55,
                       full_schema_escape_ratio: float = 0.85) -> dict:
    """Run hybrid retrieval and decide: reduced view or full-schema escalation."""
    info = hybrid_retrieve_tables(question, tables_meta, db_id,
                                  k_tables=k_tables,
                                  use_bm25=True, use_ngram=True)
    fallback = (info["confidence"] < low_confidence_threshold
                or info["reduction_ratio"] >= full_schema_escape_ratio)
    info["fallback_used"] = bool(fallback)
    info["prompt_strategy"] = ("full_schema_fallback" if fallback
                                else "reduced_via_hybrid_retrieval")
    return info


def make_b3v3_prompt(question: str, db_id: str, tables_meta: dict,
                      build_full_schema, build_reduced_schema) -> tuple[str, dict]:
    """Build a direct-SQL prompt using hybrid retrieval. Returns (prompt, retrieval_info)."""
    info = retrieve_for_b3v3(question, db_id, tables_meta)
    if info["fallback_used"]:
        schema = build_full_schema(db_id)
    else:
        schema = build_reduced_schema(db_id, info["selected_table_indexes"])
    prompt = textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema}

    Question: {question}
    SQL:
    """).strip()
    return prompt, info
