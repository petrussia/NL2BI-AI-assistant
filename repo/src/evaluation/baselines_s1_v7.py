"""baselines_s1_v7 — DAIL-style demonstration retrieval over B6_v7 controller.

Builds a top-k demo block from Spider train and prepends it to the C0_anchor
prompt only. C1/C2/C3 candidates remain unchanged so the verifier can still
choose between demo-augmented anchor and the retrieval / planner branches.

Public API:
  run_s1v7_step(question, ir, *, gen, executor=None, demo_retriever=None,
                evidence_store=None, per_item_evidence='', ...)
    -> dict (same shape as b6_v7, plus demo_chars_rendered)

Why demo only on anchor (not on all candidates)?
  - Verifier non-harm tie-break still works between demo-anchor and other
    candidates.
  - Cost of demo retrieval is amortized over a single LLM call instead
    of replicated across 4 candidates.
  - C2_evidence already encodes per-item gold evidence; mixing demos
    into C2 dilutes evidence with examples.
"""
from __future__ import annotations

from typing import Callable

from baselines_b6_v7 import run_b6v7_step


def run_s1v7_step(question: str, ir, *,
                   gen, executor=None,
                   demo_retriever=None,
                   evidence_store=None, per_item_evidence: str = '',
                   plan_schema_path: str | None = None,
                   include_planner: bool = True,
                   include_evidence: bool = True,
                   non_harm_margin: float = 0.06,
                   max_repair_rounds: int = 1,
                   planner_gen=None,
                   judge_gen: Callable | None = None,
                   judge_policy: dict | None = None,
                   benchmark: str = 'spider',
                   demo_k: int = 3,
                   demo_max_chars: int = 900) -> dict:
    """One step of S1_demo_v7. Wraps b6_v7 with anchor demos prepended."""
    demo_block = ''
    demo_n = 0
    if demo_retriever is not None:
        try:
            demos = demo_retriever.retrieve(question, ir.db_id, k=demo_k)
            demo_block = demo_retriever.render(demos, max_chars=demo_max_chars)
            demo_n = len(demos)
        except Exception:
            demo_block = ''; demo_n = 0
    out = run_b6v7_step(
        question, ir,
        gen=gen, executor=executor,
        evidence_store=evidence_store,
        per_item_evidence=per_item_evidence,
        plan_schema_path=plan_schema_path,
        include_planner=include_planner,
        include_evidence=include_evidence,
        non_harm_margin=non_harm_margin,
        max_repair_rounds=max_repair_rounds,
        planner_gen=planner_gen,
        judge_gen=judge_gen,
        judge_policy=judge_policy,
        benchmark=benchmark,
        anchor_prompt_extra=demo_block,
    )
    out['demo_chars_rendered'] = len(demo_block)
    out['demo_n'] = demo_n
    return out
