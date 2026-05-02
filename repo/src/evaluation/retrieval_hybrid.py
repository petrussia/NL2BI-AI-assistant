"""Hybrid retrieval over schema chunks: BM25 sparse + optional dense embeddings,
fused via Reciprocal Rank Fusion. Designed for cheap default execution
(no GPU model load required); a dense model can be plugged in optionally.

Public API:
- chunk_schema(tables_meta, db_id) -> list[ChunkRecord]
- bm25_rank(query, chunks) -> list[(chunk_idx, score)]
- ngram_rank(query, chunks, n=3) -> list[(chunk_idx, score)]
- rrf_fuse(rankings, k=60) -> list[(chunk_idx, fused_score)]
- select_top_tables(fused, chunks, k_tables=5) -> (selected_table_indexes, per_table_score)
"""
from __future__ import annotations
import math
import re
from dataclasses import dataclass


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")
_STOP = {"a","an","the","of","in","on","at","for","to","from","by","with",
         "is","are","was","were","what","which","who","whom","whose","how",
         "many","much","show","list","find","give","me","all","each","every",
         "any","do","does","did","that","this","there","their","them","they",
         "and","or","not","no","yes","be","been","being","has","have","had"}


def _tokenize(text: str) -> list[str]:
    out = []
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text))
    for tok in _TOKEN_RE.findall(text.lower()):
        if tok not in _STOP and len(tok) > 1:
            out.append(tok)
    return out


def _ngrams(text: str, n: int = 3) -> list[str]:
    s = re.sub(r"\s+", " ", str(text).lower().strip())
    if len(s) < n: return [s]
    return [s[i:i+n] for i in range(len(s)-n+1)]


@dataclass
class ChunkRecord:
    """One retrieval chunk derived from the schema. ``table_idx`` is always set;
    ``col_idx`` is set only for column-level chunks."""
    chunk_idx: int
    table_idx: int
    col_idx: int | None  # None for table chunks, set for column chunks
    kind: str            # "table" | "column" | "fk"
    text: str            # human-readable text used for both BM25 and dense


def chunk_schema(tables_meta: dict, db_id: str) -> list[ChunkRecord]:
    """Build retrieval chunks from a Spider-style tables.json entry."""
    tn = tables_meta.get("table_names_original") or tables_meta.get("table_names") or []
    cn = tables_meta.get("column_names_original") or tables_meta.get("column_names") or []
    fks = tables_meta.get("foreign_keys") or []
    out: list[ChunkRecord] = []
    cidx = 0
    # Table chunks
    by_table_cols: dict[int, list[str]] = {i: [] for i in range(len(tn))}
    for ti, col in cn:
        if ti >= 0:
            by_table_cols.setdefault(ti, []).append(col)
    for ti, name in enumerate(tn):
        text = f"table {name} columns " + " ".join(by_table_cols.get(ti, []))
        out.append(ChunkRecord(cidx, ti, None, "table", text)); cidx += 1
    # Column chunks
    for global_ci, (ti, col) in enumerate(cn):
        if ti < 0: continue
        text = f"column {col} of table {tn[ti]}"
        out.append(ChunkRecord(cidx, ti, global_ci, "column", text)); cidx += 1
    # FK chunks
    for a, b in fks:
        if a < 0 or b < 0 or a >= len(cn) or b >= len(cn): continue
        ta, ca = cn[a]; tb, cb = cn[b]
        if ta < 0 or tb < 0: continue
        text = f"foreign key {tn[ta]}.{ca} to {tn[tb]}.{cb}"
        out.append(ChunkRecord(cidx, ta, None, "fk", text)); cidx += 1
    return out


# ----------------------- BM25 (Okapi) -----------------------

def bm25_rank(query: str, chunks: list[ChunkRecord], k1: float = 1.5, b: float = 0.75) -> list[tuple[int, float]]:
    """Standard Okapi-BM25 over chunk texts. Returns list[(chunk_idx, score)] desc."""
    docs = [_tokenize(c.text) for c in chunks]
    if not docs: return []
    N = len(docs)
    avgdl = sum(len(d) for d in docs) / N
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    q_terms = _tokenize(query)
    scores: list[tuple[int, float]] = []
    for i, d in enumerate(docs):
        score = 0.0
        dl = len(d) or 1
        # term-frequency in this doc
        tf: dict[str, int] = {}
        for t in d: tf[t] = tf.get(t, 0) + 1
        for q in q_terms:
            n = df.get(q, 0)
            if n == 0: continue
            idf = math.log(1 + (N - n + 0.5) / (n + 0.5))
            term_tf = tf.get(q, 0)
            denom = term_tf + k1 * (1 - b + b * dl / avgdl)
            score += idf * (term_tf * (k1 + 1) / max(denom, 1e-9))
        scores.append((chunks[i].chunk_idx, score))
    scores.sort(key=lambda x: -x[1])
    return scores


# --------------------- Char n-gram (sparse 2nd signal) ---------------------

def ngram_rank(query: str, chunks: list[ChunkRecord], n: int = 3) -> list[tuple[int, float]]:
    """Cosine over character n-gram bag-of-grams. Catches partial-name matches
    that token BM25 misses (e.g. 'singer' in 'singer_in_concert')."""
    q_grams = _ngrams(query, n)
    if not q_grams: return [(c.chunk_idx, 0.0) for c in chunks]
    q_set = set(q_grams); q_norm = math.sqrt(len(q_grams))
    out = []
    for c in chunks:
        d_grams = _ngrams(c.text, n)
        d_set = set(d_grams); d_norm = math.sqrt(len(d_grams)) or 1.0
        intersect = len(q_set & d_set)
        score = intersect / (q_norm * d_norm) if intersect else 0.0
        out.append((c.chunk_idx, score))
    out.sort(key=lambda x: -x[1])
    return out


# --------------------- RRF fusion ---------------------

def rrf_fuse(rankings: list[list[tuple[int, float]]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion. Each input ranking is [(chunk_idx, score)] desc.
    Output: fused [(chunk_idx, rrf_score)] desc."""
    rrf: dict[int, float] = {}
    for ranking in rankings:
        for rank, (cidx, _) in enumerate(ranking):
            rrf[cidx] = rrf.get(cidx, 0.0) + 1.0 / (k + rank + 1)
    out = sorted(rrf.items(), key=lambda x: -x[1])
    return out


# --------------------- Select top tables ---------------------

def select_top_tables(fused: list[tuple[int, float]], chunks: list[ChunkRecord],
                      k_tables: int = 5) -> tuple[list[int], dict[int, float]]:
    """Aggregate fused chunk scores per table; pick top-k tables.

    Returns (selected_table_indexes_sorted, per_table_score_dict)."""
    by_chunk = {c.chunk_idx: c for c in chunks}
    per_table: dict[int, float] = {}
    for cidx, score in fused:
        c = by_chunk.get(cidx)
        if c is None: continue
        per_table[c.table_idx] = per_table.get(c.table_idx, 0.0) + score
    ranked = sorted(per_table.items(), key=lambda x: -x[1])
    selected_unsorted = [t for t, _ in ranked[:k_tables]]
    return sorted(selected_unsorted), per_table


# --------------------- Hybrid retrieval entry-point ---------------------

def hybrid_retrieve_tables(question: str, tables_meta: dict, db_id: str,
                            k_tables: int = 5,
                            use_bm25: bool = True,
                            use_ngram: bool = True) -> dict:
    """One-shot hybrid retrieval for a single question. Returns dict with:
    - selected_table_indexes (sorted)
    - per_table_score
    - top_chunk_examples (first 5)
    - confidence (in [0, 1], based on score gap to next-best table)
    - reduction_ratio
    - signals_used (list)
    """
    chunks = chunk_schema(tables_meta, db_id)
    rankings = []
    signals = []
    if use_bm25:
        rankings.append(bm25_rank(question, chunks)); signals.append("bm25")
    if use_ngram:
        rankings.append(ngram_rank(question, chunks)); signals.append("char_ngram_3")
    if not rankings:
        rankings.append([(c.chunk_idx, 0.0) for c in chunks])
    fused = rrf_fuse(rankings)
    selected, per_table = select_top_tables(fused, chunks, k_tables=k_tables)
    # Confidence = top_table_score / (top_table_score + next_below) if at least 2 tables, else 1.0
    if len(per_table) >= 2:
        sorted_scores = sorted(per_table.values(), reverse=True)
        top, second = sorted_scores[0], sorted_scores[1]
        confidence = top / (top + second) if (top + second) > 0 else 0.5
    else:
        confidence = 1.0
    n_tables = len(tables_meta.get("table_names_original") or tables_meta.get("table_names") or [])
    return {
        "selected_table_indexes": selected,
        "per_table_score": per_table,
        "top_chunks": [{"chunk_idx": cidx, "score": s} for cidx, s in fused[:5]],
        "confidence": float(confidence),
        "reduction_ratio": (len(selected) / n_tables) if n_tables else 1.0,
        "signals_used": signals,
        "n_chunks": len(chunks),
    }
