"""spider2_snow_schema_retrieval_v8 — schema retrieval for SF lane.

Currently re-exports from `spider2_sf_schema_index_v8`. This module
exists so that Spider2-Snow-specific retrieval behavior (e.g.
CHANGES, STREAMS, semi-structured profiling) can diverge later
without rewriting callers.

Future TODO: add IS column-statistics-based pruning when working
with very wide tables (>100 cols).
"""
from __future__ import annotations

from spider2_sf_schema_index_v8 import (  # noqa: F401  (re-exports)
    SfSchemaIndex, SfTable, SfColumn,
    build_index_from_db_dir, render_subset,
)


def retrieve_relevant_keys(idx: SfSchemaIndex, question: str,
                              k_tables: int = 6) -> list[str]:
    """Token-overlap retrieval over table_name + column descriptions.
    Lightweight, deterministic. Returns up to `k_tables` fq_names.
    """
    q_tokens = {tok.lower() for tok in _tokenize(question) if len(tok) > 2}
    if not q_tokens:
        return [t.fq_name for t in idx.tables[:k_tables]]
    scored: list[tuple[float, str]] = []
    for t in idx.tables:
        toks = set()
        toks.update(_tokenize(t.table_name))
        toks.update(_tokenize(t.description or ''))
        for c in t.columns:
            toks.update(_tokenize(c.name))
            toks.update(_tokenize(c.description or ''))
        toks_low = {x.lower() for x in toks if len(x) > 2}
        if not toks_low:
            continue
        overlap = len(q_tokens & toks_low) / max(1, len(q_tokens | toks_low))
        scored.append((overlap, t.fq_name))
    scored.sort(reverse=True)
    keys = [n for _, n in scored[:k_tables] if _ > 0]
    if not keys:
        keys = [t.fq_name for t in idx.tables[:k_tables]]
    return keys


def _tokenize(text: str) -> list[str]:
    import re
    return re.findall(r'[A-Za-z][A-Za-z0-9_]+', text or '')
