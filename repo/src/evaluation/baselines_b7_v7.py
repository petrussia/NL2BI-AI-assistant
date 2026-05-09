"""baselines_b7_v7 — B6_v7 controller + rich evidence layer (Priority 2).

Wraps the Phase 6 winner with the v7 semantic evidence layer. The
controller and judge logic are unchanged; we only swap the
`per_item_evidence` string injected into the candidate generator and the
judge prompt.

Ablations supported via `evidence_modes`:
  - 'gold_only'   = baseline (matches Phase A B2_v5 evidence behaviour)
  - 'profiles_only' = drop gold; only schema + value-hint probes
  - 'generated_only'= drop gold; only generated aliases
  - 'rich'        = gold + schema + profiles + aliases (the full B7d variant)
  - 'none'        = no evidence at all (sanity check)
"""
from __future__ import annotations

import sqlite3
from typing import Callable

from baselines_b6_v7 import run_b6v7_step, DEFAULT_POLICY
from evidence_semantics_v7 import build_evidence_pack
from schema_linker_bidirectional_v2 import link


def _resolve_db_path(ir, *, spider_db_dir=None, bird_db_root=None) -> str | None:
    if spider_db_dir is not None:
        p = spider_db_dir / ir.db_id / f'{ir.db_id}.sqlite'
        if p.exists(): return str(p)
    if bird_db_root is not None:
        p = bird_db_root / ir.db_id / f'{ir.db_id}.sqlite'
        if p.exists(): return str(p)
    return None


def run_b7v7_step(question: str, ir, *,
                   gen, executor=None,
                   evidence_store=None,
                   per_item_evidence: str = '',
                   plan_schema_path: str | None = None,
                   include_planner: bool = True,
                   include_evidence: bool = True,
                   non_harm_margin: float = 0.06,
                   max_repair_rounds: int = 1,
                   planner_gen=None,
                   judge_gen: Callable | None = None,
                   judge_policy: dict | None = None,
                   benchmark: str = 'unknown',
                   evidence_mode: str = 'rich',
                   db_path: str | None = None,
                   evidence_char_budget: int = 600,
                   evidence_k: int = 8) -> dict:
    """One step of B7_v7. Mostly delegates to b6_v7; the only difference
    is that we build the evidence pack with `evidence_semantics_v7` first
    and pass it as `per_item_evidence` to the same controller."""
    # 1. Decide what flavours of evidence to include
    flags = {
        'rich':           dict(include_schema=True,  include_value_hints=True,  include_aliases=True),
        'gold_only':      dict(include_schema=False, include_value_hints=False, include_aliases=False),
        'profiles_only':  dict(include_schema=True,  include_value_hints=True,  include_aliases=False),
        'generated_only': dict(include_schema=False, include_value_hints=False, include_aliases=True),
        'none':           dict(include_schema=False, include_value_hints=False, include_aliases=False),
    }.get(evidence_mode, None)
    if flags is None:
        flags = dict(include_schema=True, include_value_hints=True, include_aliases=True)

    use_gold = (evidence_mode in ('rich', 'gold_only', 'profiles_only')) and bool(per_item_evidence)
    gold_text = per_item_evidence if use_gold else ''

    # 2. Pre-link to get selected_tables for relevance ranking inside evidence
    selected_tables: list[str] = []
    try:
        link_res = link(question, ir, k_tables=5, expand_extra=4)
        selected_tables = link_res.selected_tables or []
    except Exception:
        selected_tables = []

    if evidence_mode == 'none':
        rendered_evidence = ''
        evidence_items_n = 0
    else:
        rendered_evidence, ranked = build_evidence_pack(
            question, ir, db_path,
            per_item_evidence=gold_text,
            char_budget=evidence_char_budget,
            k_retrieve=evidence_k,
            selected_tables=selected_tables,
            **flags,
        )
        evidence_items_n = len(ranked)

    # 3. Hand off to the b6_v7 controller (same selector + verifier + repair)
    out = run_b6v7_step(
        question, ir,
        gen=gen, executor=executor,
        evidence_store=evidence_store,
        per_item_evidence=rendered_evidence,
        plan_schema_path=plan_schema_path,
        include_planner=include_planner,
        include_evidence=include_evidence,
        non_harm_margin=non_harm_margin,
        max_repair_rounds=max_repair_rounds,
        planner_gen=planner_gen,
        judge_gen=judge_gen,
        judge_policy=judge_policy,
        benchmark=benchmark,
    )
    out['evidence_mode'] = evidence_mode
    out['evidence_chars_rendered'] = len(rendered_evidence)
    out['evidence_items_n'] = evidence_items_n
    out['used_gold_evidence'] = use_gold
    return out
