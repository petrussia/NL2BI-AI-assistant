"""B3_v4: hybrid retrieval + direct SQL with optional benchmark evidence.

Differences vs B3_v3:
1. Accepts optional `evidence` (BIRD has it; Spider does not). Evidence is
   injected as a separate "Domain hint" section in the prompt. **Never used as
   gold-SQL source.**
2. Tightened anti-overpruning: if reduction_ratio >= 0.85 OR confidence < 0.55
   → escalate to B0 (full schema, no extra signals).
3. Records reduction_ratio and link_confidence in the same structure for
   downstream stats/plotting.
"""
from __future__ import annotations
import textwrap
from retrieval_hybrid import hybrid_retrieve_tables


def retrieve_for_b3v4(question: str, db_id: str, tables_meta: dict,
                      k_tables: int = 5,
                      low_confidence_threshold: float = 0.55,
                      full_schema_escape_ratio: float = 0.85) -> dict:
    info = hybrid_retrieve_tables(question, tables_meta, db_id,
                                  k_tables=k_tables, use_bm25=True, use_ngram=True)
    fallback = (info["confidence"] < low_confidence_threshold
                or info["reduction_ratio"] >= full_schema_escape_ratio)
    info["fallback_used"] = bool(fallback)
    info["prompt_strategy"] = ("full_schema_fallback" if fallback
                                else "reduced_via_hybrid_retrieval")
    return info


def make_b3v4_prompt(question: str, db_id: str, tables_meta: dict,
                      build_full_schema, build_reduced_schema,
                      evidence: str = "") -> tuple[str, dict]:
    info = retrieve_for_b3v4(question, db_id, tables_meta)
    if info["fallback_used"]:
        schema = build_full_schema(db_id)
    else:
        schema = build_reduced_schema(db_id, info["selected_table_indexes"])
    extra = ""
    if evidence and not info["fallback_used"]:
        extra = f"\n\nDomain hint (from benchmark; may be partially relevant):\n{evidence}"
    prompt = textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema}{extra}

    Question: {question}
    SQL:
    """).strip()
    return prompt, info
