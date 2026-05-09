"""baselines_b2_v5 — Hybrid retrieval + evidence direct (v2 stack).

Same as b1_v5 but additionally injects:
  - top-k benchmark `evidence` snippets (BIRD per-item; per-db corpus
    for Spider/Spider2-Lite when available)
  - per-table comments / column comments embedded in the rendered schema

Goal: isolate the contribution of *evidence content*, holding the
retrieval algorithm constant against b1_v5.
"""
from __future__ import annotations

import re
import textwrap

from schema_ir_v2 import render_compact_schema
from schema_linker_bidirectional_v2 import link
from retrieval_hybrid_v2 import retrieve_evidence
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


def _build_prompt(schema_text: str, question: str,
                   evidence_block: str = '') -> str:
    extra = ('\n\nDomain hints (from benchmark; may be partially relevant):\n'
              + evidence_block) if evidence_block else ''
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Prefer to apply the domain hints when they
    refer to the question; otherwise ignore them. Return SQL only, no
    markdown and no explanation.

    {schema_text}{extra}

    Question: {question}
    SQL:
    """).strip()


def run_b2v5_step(question: str, ir, *,
                   gen,
                   evidence_store=None,
                   per_item_evidence: str = '',
                   k_evidence: int = 3) -> dict:
    res = link(question, ir, k_tables=5, expand_extra=4)
    if res.fallback_used:
        schema_text = render_compact_schema(ir, include_comments=True)
    else:
        schema_text = render_compact_schema(
            ir, include_comments=True,
            subset_tables=res.selected_tables,
        )

    # Assemble evidence block: per-item primary, retrieved secondary
    parts: list[str] = []
    if per_item_evidence:
        parts.append('- ' + per_item_evidence.strip())
    if evidence_store is not None:
        retrieved = retrieve_evidence(question, evidence_store, ir.db_id,
                                       k_evidence=k_evidence)
        for it in retrieved:
            txt = (getattr(it, 'text', '') or '').strip()
            if txt and ('- ' + txt) not in parts:
                parts.append('- ' + txt)
    evidence_block = '\n'.join(parts[:k_evidence + 1])

    prompt = _build_prompt(schema_text, question, evidence_block)
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
        'evidence_used': bool(evidence_block),
        'evidence_chars': len(evidence_block),
        'rationale': res.rationale,
    }
