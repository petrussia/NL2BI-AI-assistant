"""spider2_bq_candidate_generator_v8 — produce a small candidate pool
for one Spider2 BigQuery item.

Each candidate is a dict with at least:
  source: 'C0_direct' | 'C1_retrieval_docs' | 'C2_cte_decomp'
  sql: str (raw extracted SQL)
  prompt_chars: int (audit)
  audit: dict (selected_keys, doc_titles, etc.)
  # filled in later by verifier:
  verifier: dict
"""
from __future__ import annotations

from typing import Callable

from spider2_bq_schema_index_v8 import BqSchemaIndex
from spider2_bq_retrieval_v8 import RetrievalBundle
from spider2_bq_prompting_v8 import (
    direct_prompt, retrieval_prompt, cte_prompt,
)
from spider2_agent_v7 import _extract_sql  # WITH-preserving extractor


def _candidate_audit(bundle: RetrievalBundle) -> dict:
    return {
        'selected_keys': bundle.selected_keys[:],
        'doc_titles': [d.title for d in bundle.docs],
        'doc_sources': sorted({d.source for d in bundle.docs}),
        'fallback_used': bundle.fallback_used,
        'rationale': bundle.rationale[:],
    }


def make_candidates(question: str, idx: BqSchemaIndex,
                      bundle: RetrievalBundle, *,
                      gen: Callable,
                      include_direct: bool = True,
                      include_retrieval: bool = True,
                      include_cte: bool = True,
                      max_new_sql: int = 800,
                      max_new_cte: int = 1100) -> list[dict]:
    """Generate up to 3 candidate drafts. Verifier runs separately.

    Returns list of candidate dicts (each with `source`, `sql`, `prompt_chars`,
    `audit`). Caller is responsible for verification + selection + repair.
    """
    cands: list[dict] = []

    if include_direct:
        p0 = direct_prompt(question, idx, bundle, max_cols=22)
        s0 = _extract_sql(gen(p0, max_new=max_new_sql))
        cands.append({'source': 'C0_direct', 'sql': s0,
                       'prompt_chars': len(p0),
                       'audit': _candidate_audit(bundle)})

    if include_retrieval:
        p1 = retrieval_prompt(question, idx, bundle, max_cols=22)
        s1 = _extract_sql(gen(p1, max_new=max_new_sql))
        cands.append({'source': 'C1_retrieval_docs', 'sql': s1,
                       'prompt_chars': len(p1),
                       'audit': _candidate_audit(bundle)})

    if include_cte:
        p2 = cte_prompt(question, idx, bundle, max_cols=22)
        s2 = _extract_sql(gen(p2, max_new=max_new_cte))
        cands.append({'source': 'C2_cte_decomp', 'sql': s2,
                       'prompt_chars': len(p2),
                       'audit': _candidate_audit(bundle)})

    return cands
