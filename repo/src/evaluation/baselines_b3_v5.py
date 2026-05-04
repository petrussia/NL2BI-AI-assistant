"""baselines_b3_v5 — gated planner + compiler + B0 anchor controller.

Architecture per project plan:
  1. Always start by computing the B0 anchor candidate (full schema, direct LLM).
     That candidate is the *floor*: B3_v5 must beat it or fall back to it.
  2. difficulty_router classifies the question. Easy queries skip planning
     entirely and return the anchor.
  3. For hard queries, run the planner (LLM-driven JSON generation),
     parse + validate + link to IR.
  4. If the plan is valid, run sql_compiler_v2:
        - status='ok' → use compiled SQL as the main candidate.
        - status='skeleton' → use compiled skeleton as a *guided hint* for a
          second LLM call that must finish the SQL.
  5. Verify both candidates by safe-select; default to anchor when in doubt
     (non-harm rule).

Returns a dict with the chosen sql + audit fields needed for downstream
verifier_ranker_v2 in Phase C.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

from schema_ir_v2 import render_compact_schema
from schema_linker_bidirectional_v2 import link
from dialect_utils_v2 import is_safe_select
from difficulty_router_v2 import classify
from planner_v2 import (
    make_planner_prompt, parse_plan, validate_plan, link_plan_to_ir,
)
from sql_compiler_v2 import compile_plan


def _extract_sql(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"(?is)(select\b.*)", text)
    if m: text = m.group(1).strip()
    text = text.split("\n\n")[0].strip()
    if ";" in text: text = text.split(";", 1)[0].strip()
    return text.rstrip(";") + ";"


def _build_b0_prompt(schema_text: str, question: str) -> str:
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema_text}

    Question: {question}
    SQL:
    """).strip()


def _build_synth_from_skeleton_prompt(schema_text: str, question: str,
                                       skeleton: str) -> str:
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. A planner produced a partial SQL skeleton
    that does NOT compile or is incomplete. Replace any "/* TODO ... */"
    fragments and finish the SQL so it answers the question. Return SQL only.

    Schema:
    {schema_text}

    Skeleton:
    {skeleton}

    Question: {question}
    Final SQL:
    """).strip()


def _fk_summary(ir, k: int = 60) -> str:
    out = []
    for e in ir.fk_edges[:k]:
        out.append(f'{e.from_table}.{e.from_column} -> {e.to_table}.{e.to_column}')
    return '\n'.join(out)


def run_b3v5_step(question: str, ir, *,
                   gen,
                   planner_gen=None,
                   evidence_store=None,
                   per_item_evidence: str = '',
                   plan_schema_path: str | None = None,
                   force_planner: bool = False) -> dict:
    """If `planner_gen` is provided, the planner LLM call uses it; the
    anchor / synth-from-skeleton / repair calls always use `gen`. Lets us
    swap the planner model without changing anything else (Phase D)."""
    plan_gen = planner_gen if planner_gen is not None else gen
    """One step of the B3_v5 pipeline."""
    audit: dict = {'rationale': []}

    # ---- 0. Retrieval shared with B1_v5/B2_v5 ----
    res = link(question, ir, k_tables=5, expand_extra=4)
    if res.fallback_used:
        reduced_schema = render_compact_schema(ir, include_comments=True)
    else:
        reduced_schema = render_compact_schema(ir, include_comments=True,
                                                subset_tables=res.selected_tables)
    full_schema = render_compact_schema(ir, include_comments=False)
    audit['retrieval'] = {
        'selected_tables': res.selected_tables,
        'fallback_used': res.fallback_used,
        'confidence': res.confidence,
        'reduction_ratio': res.reduction_ratio,
    }

    # ---- 1. Always compute the B0 anchor candidate (the floor) ----
    b0_prompt = _build_b0_prompt(full_schema, question)
    b0_sql = _extract_sql(gen(b0_prompt, max_new=256))
    b0_safe, b0_safe_reason = is_safe_select(b0_sql, ir.dialect)

    # ---- 2. Difficulty routing ----
    cls = classify(question, n_tables_in_db=len(ir.tables),
                    n_tables_retrieved=len(res.selected_tables))
    audit['difficulty'] = cls
    take_planner = force_planner or cls['difficulty'] == 'hard'

    if not take_planner:
        audit['rationale'].append('router=easy → return anchor')
        return {
            'sql': b0_sql,
            'safe': b0_safe, 'safe_reason': b0_safe_reason,
            'selected_candidate_source': 'b0_anchor_easy',
            'planner_used': False, 'plan_valid': False,
            'compiler_status': 'skipped',
            'fallback_used': False, 'fallback_reason': '',
            'b0_sql': b0_sql, 'compiled_sql': '',
            'audit': audit, 'plan': None, 'compile_audit': {},
        }

    # ---- 3. Planner ----
    pl_prompt = make_planner_prompt(
        question, reduced_schema,
        fk_summary=_fk_summary(ir), evidence=per_item_evidence,
        dialect=ir.dialect,
    )
    raw_plan = plan_gen(pl_prompt, max_new=512)
    plan, parse_err = parse_plan(raw_plan)
    if plan is None:
        audit['rationale'].append(f'plan_parse_fail:{parse_err}')
        return {
            'sql': b0_sql,
            'safe': b0_safe, 'safe_reason': b0_safe_reason,
            'selected_candidate_source': 'b0_anchor_plan_parse_fail',
            'planner_used': True, 'plan_valid': False,
            'compiler_status': 'skipped', 'fallback_used': True,
            'fallback_reason': f'plan_parse_fail:{parse_err}',
            'b0_sql': b0_sql, 'compiled_sql': '',
            'audit': audit, 'plan': None, 'compile_audit': {},
        }
    audit['rationale'].append('plan_parsed')
    valid, val_err = validate_plan(plan, plan_schema_path)
    if not valid:
        audit['rationale'].append(f'plan_invalid:{val_err}')
        return {
            'sql': b0_sql,
            'safe': b0_safe, 'safe_reason': b0_safe_reason,
            'selected_candidate_source': 'b0_anchor_plan_invalid',
            'planner_used': True, 'plan_valid': False,
            'compiler_status': 'skipped', 'fallback_used': True,
            'fallback_reason': f'plan_invalid:{val_err}',
            'b0_sql': b0_sql, 'compiled_sql': '',
            'audit': audit, 'plan': plan, 'compile_audit': {},
        }
    link_audit = link_plan_to_ir(plan, ir)
    audit['plan_link'] = link_audit

    # ---- 4. Compile ----
    comp = compile_plan(plan, ir, dialect=ir.dialect)
    compiled_sql = comp['sql']; status = comp['status']
    audit['compile'] = {'status': status, 'families': comp['families_used']}
    if status == 'failed':
        audit['rationale'].append('compile_failed → anchor')
        return {
            'sql': b0_sql,
            'safe': b0_safe, 'safe_reason': b0_safe_reason,
            'selected_candidate_source': 'b0_anchor_compile_failed',
            'planner_used': True, 'plan_valid': True,
            'compiler_status': 'failed', 'fallback_used': True,
            'fallback_reason': 'compile_failed',
            'b0_sql': b0_sql, 'compiled_sql': compiled_sql,
            'audit': audit, 'plan': plan, 'compile_audit': comp['audit'],
        }
    if status == 'skeleton':
        # 4b. Skeleton → second LLM call to finish
        synth_prompt = _build_synth_from_skeleton_prompt(full_schema, question, compiled_sql)
        raw2 = gen(synth_prompt, max_new=256)
        synth_sql = _extract_sql(raw2)
        s_safe, s_safe_reason = is_safe_select(synth_sql, ir.dialect)
        if s_safe:
            audit['rationale'].append('skeleton_synth_used')
            return {
                'sql': synth_sql,
                'safe': True, 'safe_reason': s_safe_reason,
                'selected_candidate_source': 'planner_skeleton_synth',
                'planner_used': True, 'plan_valid': True,
                'compiler_status': 'skeleton', 'fallback_used': False,
                'fallback_reason': '',
                'b0_sql': b0_sql, 'compiled_sql': compiled_sql,
                'audit': audit, 'plan': plan, 'compile_audit': comp['audit'],
            }
        audit['rationale'].append('skeleton_synth_unsafe → anchor')
        return {
            'sql': b0_sql,
            'safe': b0_safe, 'safe_reason': b0_safe_reason,
            'selected_candidate_source': 'b0_anchor_skeleton_unsafe',
            'planner_used': True, 'plan_valid': True,
            'compiler_status': 'skeleton', 'fallback_used': True,
            'fallback_reason': f'skeleton_unsafe:{s_safe_reason}',
            'b0_sql': b0_sql, 'compiled_sql': compiled_sql,
            'audit': audit, 'plan': plan, 'compile_audit': comp['audit'],
        }

    # 4a. Status == 'ok'
    c_safe, c_safe_reason = is_safe_select(compiled_sql, ir.dialect)
    if not c_safe:
        audit['rationale'].append(f'compiled_unsafe:{c_safe_reason} → anchor')
        return {
            'sql': b0_sql,
            'safe': b0_safe, 'safe_reason': b0_safe_reason,
            'selected_candidate_source': 'b0_anchor_compile_unsafe',
            'planner_used': True, 'plan_valid': True,
            'compiler_status': 'ok', 'fallback_used': True,
            'fallback_reason': f'compiled_unsafe:{c_safe_reason}',
            'b0_sql': b0_sql, 'compiled_sql': compiled_sql,
            'audit': audit, 'plan': plan, 'compile_audit': comp['audit'],
        }
    audit['rationale'].append('compiled_used')
    return {
        'sql': compiled_sql,
        'safe': True, 'safe_reason': c_safe_reason,
        'selected_candidate_source': 'planner_compiled',
        'planner_used': True, 'plan_valid': True,
        'compiler_status': 'ok', 'fallback_used': False, 'fallback_reason': '',
        'b0_sql': b0_sql, 'compiled_sql': compiled_sql,
        'audit': audit, 'plan': plan, 'compile_audit': comp['audit'],
    }
