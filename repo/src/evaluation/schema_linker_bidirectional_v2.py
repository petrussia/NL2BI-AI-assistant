"""schema_linker_bidirectional_v2 — composes retrieval + FK expansion.

Public surface:
  link(question, ir, *, k_tables=5, expand_extra=4) -> RetrievalResult

Adds three things on top of retrieval_hybrid_v2.bidirectional_retrieve:
  - FK expansion (so we never miss a join bridge)
  - confidence-driven fallback to full schema
  - column-level rationale for the planner
"""
from __future__ import annotations

from dataclasses import replace

from retrieval_hybrid_v2 import bidirectional_retrieve, RetrievalResult
from join_path_expander_v2 import expand_anchors


def link(question: str, ir, *,
         k_tables: int = 5,
         expand_extra: int = 4,
         expand_max_hops: int = 4,
         low_confidence_threshold: float = 0.55,
         full_schema_escape_ratio: float = 0.85) -> RetrievalResult:
    res = bidirectional_retrieve(question, ir, k_tables=k_tables)

    # FK expansion to ensure join bridges are present.
    if res.selected_tables:
        expanded, paths = expand_anchors(ir, res.selected_tables,
                                         max_extra=expand_extra,
                                         max_hops=expand_max_hops)
        if expanded != res.selected_tables:
            t_idx = {t.name: i for i, t in enumerate(ir.tables)}
            res.selected_tables = expanded
            res.selected_table_indexes = [t_idx[t] for t in expanded if t in t_idx]
            res.reduction_ratio = (len(ir.tables) - len(res.selected_table_indexes)) / max(1, len(ir.tables))
            res.rationale.append(f'fk_expand={[p for p in paths if len(p) > 2][:2]}')

    # Decide fallback. If we'd over-prune (reduction < 0.15) or confidence
    # is low, escalate to full-schema in the prompt assembler.
    if res.confidence < low_confidence_threshold or res.reduction_ratio >= full_schema_escape_ratio:
        res.fallback_used = True
        res.rationale.append(
            f'fallback: conf={res.confidence:.2f} red={res.reduction_ratio:.2f}'
        )

    return res
