"""B1_v3: bidirectional schema linking + direct SQL.

Uses ``schema_linking_bidirectional.link_bidirectional`` to choose tables
(table-first AND column-first passes merged with link_confidence) and emits
a B1-style direct SQL prompt over the reduced schema. If link confidence is
low or the linker selects almost the whole schema, it transparently degrades
to full schema (B0-equivalent prompt).

Public API:
- link_for_b1v3(question, db_id, tables_meta) -> dict (passthrough to linker
  with extra `prompt_strategy` field)
- make_b1v3_prompt(question, db_id, tables_meta, build_full_schema, build_reduced_schema)
"""
from __future__ import annotations
import textwrap

from schema_linking_bidirectional import link_bidirectional


def link_for_b1v3(question: str, db_id: str, tables_meta: dict,
                  k_tables: int = 5) -> dict:
    """Run the bidirectional linker and tag the prompt strategy decision."""
    out = link_bidirectional(question, db_id, tables_meta, k_tables=k_tables)
    out["prompt_strategy"] = ("full_schema_fallback" if out["fallback_used"]
                              else "reduced_via_bidirectional_linker")
    return out


def make_b1v3_prompt(question: str, db_id: str, tables_meta: dict,
                      build_full_schema, build_reduced_schema) -> tuple[str, dict]:
    """Build a B1-style prompt using the bidirectional linker. Returns (prompt, link_info)."""
    info = link_for_b1v3(question, db_id, tables_meta)
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
