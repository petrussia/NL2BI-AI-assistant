"""candidate_generator_v2 — produce a small set of SQL candidates per question.

Used by b4_v5. Re-uses the existing v5 baselines (b1_v5/b2_v5/b3_v5) and the
B0-anchor prompt. Each candidate carries source label, generated SQL,
SchemaIR-derived audit (selected_tables, fallback_used, plan, etc.) and an
estimate of how expensive it was (LM calls).

Design contract: easy queries get ≤2 candidates (anchor + retrieval). Hard
queries get up to 4 (add planner+compiler and optionally a retrieval+evidence
variant). The verifier then picks the winner; b4_v5 enforces the non-harm rule.
"""
from __future__ import annotations

import re
import textwrap

from schema_ir_v2 import render_compact_schema
from schema_linker_bidirectional_v2 import link
from dialect_utils_v2 import is_safe_select
from difficulty_router_v2 import classify
from baselines_b1_v5 import _extract_sql as _extract_sql
from baselines_b2_v5 import run_b2v5_step
from baselines_b3_v5 import run_b3v5_step


def _b0_prompt(schema_text: str, question: str) -> str:
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema_text}

    Question: {question}
    SQL:
    """).strip()


def _retrieval_only_prompt(schema_text: str, question: str) -> str:
    return _b0_prompt(schema_text, question)  # same shape, schema differs


def make_candidates(question: str, ir, *, gen,
                     planner_gen=None,
                     evidence_store=None,
                     per_item_evidence: str = '',
                     plan_schema_path: str | None = None,
                     include_planner: bool = True,
                     include_evidence: bool = True,
                     anchor_prompt_extra: str = '') -> list[dict]:
    """Returns a list of candidate dicts, each with at least:
        source, sql, safe, safe_reason, lm_calls, audit (free-form)
    """
    candidates: list[dict] = []

    # Build retrieval result once and reuse
    res = link(question, ir, k_tables=5, expand_extra=4)
    full_schema = render_compact_schema(ir, include_comments=False)
    if res.fallback_used:
        reduced_schema = render_compact_schema(ir, include_comments=True)
    else:
        reduced_schema = render_compact_schema(ir, include_comments=True,
                                                subset_tables=res.selected_tables)

    # ---- C0: B0 anchor (full schema, no retrieval) ----
    # If `anchor_prompt_extra` is provided (S1_demo_v7 demo block), prepend
    # to the anchor prompt so the model sees similar gold examples first.
    if anchor_prompt_extra:
        p0 = anchor_prompt_extra.rstrip() + '\n\n' + _b0_prompt(full_schema, question)
    else:
        p0 = _b0_prompt(full_schema, question)
    s0 = _extract_sql(gen(p0, max_new=256))
    safe0, why0 = is_safe_select(s0, ir.dialect)
    candidates.append({
        'source': 'C0_anchor', 'sql': s0, 'safe': safe0, 'safe_reason': why0,
        'lm_calls': 1, 'audit': {'fallback_used': False, 'mode': 'b0_full_schema'},
    })

    # ---- C1: retrieval-only direct ----
    p1 = _retrieval_only_prompt(reduced_schema, question)
    s1 = _extract_sql(gen(p1, max_new=256))
    safe1, why1 = is_safe_select(s1, ir.dialect)
    candidates.append({
        'source': 'C1_retrieval_direct', 'sql': s1, 'safe': safe1, 'safe_reason': why1,
        'lm_calls': 1,
        'audit': {'selected_tables': res.selected_tables,
                   'fallback_used': res.fallback_used,
                   'confidence': res.confidence,
                   'reduction_ratio': res.reduction_ratio},
    })

    # ---- C2: retrieval + evidence direct (only if evidence might help) ----
    if include_evidence and (per_item_evidence or evidence_store is not None):
        step2 = run_b2v5_step(question, ir, gen=gen,
                               evidence_store=evidence_store,
                               per_item_evidence=per_item_evidence,
                               k_evidence=3)
        candidates.append({
            'source': 'C2_retrieval_evidence', 'sql': step2['sql'],
            'safe': step2['safe'], 'safe_reason': step2['safe_reason'],
            'lm_calls': 1,
            'audit': {
                'selected_tables': step2.get('selected_tables', []),
                'fallback_used': step2.get('fallback_used', False),
                'confidence': step2.get('link_confidence', 0.0),
                'evidence_used': step2.get('evidence_used', False),
                'evidence_chars': step2.get('evidence_chars', 0),
            },
        })

    # ---- C3: gated planner + compiler (only if router says hard) ----
    cls = classify(question, n_tables_in_db=len(ir.tables),
                    n_tables_retrieved=len(res.selected_tables))
    if include_planner and cls['difficulty'] == 'hard':
        step3 = run_b3v5_step(question, ir, gen=gen,
                               planner_gen=planner_gen,
                               evidence_store=evidence_store,
                               per_item_evidence=per_item_evidence,
                               plan_schema_path=plan_schema_path,
                               force_planner=True)
        candidates.append({
            'source': 'C3_planner_compiled', 'sql': step3['sql'],
            'safe': step3['safe'], 'safe_reason': step3['safe_reason'],
            'lm_calls': step3.get('audit',{}).get('difficulty',{}).get('n_words',0) and 2 or 2,
            'audit': {
                'planner_used': step3.get('planner_used', False),
                'plan_valid': step3.get('plan_valid', False),
                'compiler_status': step3.get('compiler_status',''),
                'fallback_used': step3.get('fallback_used', False),
                'fallback_reason': step3.get('fallback_reason',''),
                'plan_compile_families': step3.get('audit',{}).get('compile',{}).get('families',[]),
                'sub_source': step3.get('selected_candidate_source',''),
            },
        })

    # Tag every candidate with the difficulty signal so the verifier can use it
    for c in candidates:
        c['difficulty'] = cls
    return candidates
