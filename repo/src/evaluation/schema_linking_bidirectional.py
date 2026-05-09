"""Bidirectional schema linking: combine table-first and column-first passes
into a single calibrated selection with link_confidence.

Public API:
- link_bidirectional(question, db_id, tables_meta) -> dict with:
    selected_table_indexes, link_confidence, mode_decision,
    reduction_ratio, table_first_set, column_first_set, fallback_used
"""
from __future__ import annotations
import re

from retrieval_hybrid import (
    chunk_schema, bm25_rank, ngram_rank, rrf_fuse,
    select_top_tables, _tokenize,
)


def _table_first_pass(question: str, tables_meta: dict, db_id: str,
                      k_tables: int = 5) -> tuple[list[int], dict[int, float]]:
    """Rank table chunks only, then map to table indexes."""
    chunks = chunk_schema(tables_meta, db_id)
    table_chunks = [c for c in chunks if c.kind == "table"]
    rankings = [bm25_rank(question, table_chunks),
                ngram_rank(question, table_chunks)]
    fused = rrf_fuse(rankings)
    return select_top_tables(fused, table_chunks, k_tables=k_tables)


def _column_first_pass(question: str, tables_meta: dict, db_id: str,
                       k_tables: int = 5) -> tuple[list[int], dict[int, float]]:
    """Rank column chunks; aggregate scores per table; pick top-k tables."""
    chunks = chunk_schema(tables_meta, db_id)
    col_chunks = [c for c in chunks if c.kind == "column"]
    rankings = [bm25_rank(question, col_chunks),
                ngram_rank(question, col_chunks)]
    fused = rrf_fuse(rankings)
    return select_top_tables(fused, col_chunks, k_tables=k_tables)


def link_bidirectional(question: str, db_id: str, tables_meta: dict,
                       k_tables: int = 5,
                       low_confidence_threshold: float = 0.55,
                       full_schema_escape_ratio: float = 0.85) -> dict:
    """Bidirectional schema linker. Runs both passes, merges, and returns a single
    selection plus a calibrated link_confidence in [0, 1].

    Anti-overpruning rule:
    - if merged selection covers fraction of full schema >= full_schema_escape_ratio,
      OR confidence < low_confidence_threshold,
      we mark `fallback_used=True` and recommend escalating to full-schema (B0)
      via the consumer baseline.
    """
    tn = tables_meta.get("table_names_original") or tables_meta.get("table_names") or []
    n_tables = len(tn) or 1

    table_first_set, table_scores = _table_first_pass(question, tables_meta, db_id, k_tables=k_tables)
    column_first_set, col_scores = _column_first_pass(question, tables_meta, db_id, k_tables=k_tables)

    # Merge with weighted vote
    merged_scores: dict[int, float] = {}
    for ti, s in table_scores.items():
        merged_scores[ti] = merged_scores.get(ti, 0.0) + 0.6 * s
    for ti, s in col_scores.items():
        merged_scores[ti] = merged_scores.get(ti, 0.0) + 0.4 * s

    if not merged_scores:
        # Fallback: every table
        return {
            "selected_table_indexes": list(range(n_tables)),
            "link_confidence": 0.0,
            "mode_decision": "fallback_full_schema",
            "reduction_ratio": 1.0,
            "table_first_set": [],
            "column_first_set": [],
            "fallback_used": True,
        }

    ranked = sorted(merged_scores.items(), key=lambda x: -x[1])
    selected = sorted([t for t, _ in ranked[:k_tables]])

    # Confidence: top score over (top + 2nd)
    if len(ranked) >= 2:
        top, second = ranked[0][1], ranked[1][1]
        confidence = top / (top + second) if (top + second) > 0 else 0.5
    else:
        confidence = 1.0

    reduction_ratio = len(selected) / n_tables

    fallback_used = False
    mode_decision = "linker_selection"
    if reduction_ratio >= full_schema_escape_ratio:
        mode_decision = "fallback_full_schema_overpruning_check"
        fallback_used = True
        selected = list(range(n_tables))
    elif confidence < low_confidence_threshold:
        mode_decision = "low_confidence_fallback_full_schema"
        fallback_used = True
        selected = list(range(n_tables))

    return {
        "selected_table_indexes": selected,
        "link_confidence": float(confidence),
        "mode_decision": mode_decision,
        "reduction_ratio": float(len(selected) / n_tables),
        "table_first_set": table_first_set,
        "column_first_set": column_first_set,
        "fallback_used": fallback_used,
    }
