"""baselines_b1_v5 — Hybrid retrieval direct (v2 stack).

One LLM call. Uses schema_linker_bidirectional_v2 to pick a reduced
schema (or fall back to full); no benchmark evidence is injected.
This is the *retrieval-only* baseline for Phase A ablation against:
  B0 (full schema, no retrieval)  — anchor
  B2_v5 (retrieval + evidence)
"""
from __future__ import annotations

import re
import textwrap

from schema_ir_v2 import render_compact_schema
from schema_linker_bidirectional_v2 import link
from dialect_utils_v2 import is_safe_select


def _extract_sql(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"(?is)(select\b.*)", text)
    if m: text = m.group(1).strip()
    text = text.split("\n\n")[0].strip()
    if ";" in text: text = text.split(";", 1)[0].strip()
    return text.rstrip(";") + ";"


def _build_prompt(schema_text: str, question: str) -> str:
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema_text}

    Question: {question}
    SQL:
    """).strip()


def run_b1v5_step(question: str, ir, *, gen) -> dict:
    """Returns the prediction record fragment (caller adds metadata fields)."""
    res = link(question, ir, k_tables=5, expand_extra=4)
    if res.fallback_used:
        schema_text = render_compact_schema(ir, include_comments=False)
    else:
        schema_text = render_compact_schema(
            ir, include_comments=False,
            subset_tables=res.selected_tables,
        )
    prompt = _build_prompt(schema_text, question)
    raw = gen(prompt, max_new=256)
    sql = _extract_sql(raw)
    safe, safe_reason = is_safe_select(sql, ir.dialect)
    return {
        'sql': sql,
        'prompt': prompt,
        'safe': safe,
        'safe_reason': safe_reason,
        'selected_tables': res.selected_tables,
        'selected_table_indexes': res.selected_table_indexes,
        'selected_columns': res.selected_columns,
        'reduction_ratio': res.reduction_ratio,
        'link_confidence': res.confidence,
        'fallback_used': res.fallback_used,
        'rationale': res.rationale,
    }
