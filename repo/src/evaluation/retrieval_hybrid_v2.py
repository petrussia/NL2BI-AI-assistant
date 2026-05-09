"""retrieval_hybrid_v2 — multi-corpus, optionally bidirectional, hybrid retrieval.

Corpora (each scored independently then RRF-fused):
  table_docs    : "<table_name> <comment> <column_name_concat>"
  column_docs   : "<table_name>.<column_name> <comment> <dtype>"
  glossary      : business terms / aliases (per-db)
  value_hints   : low-cardinality value tokens (per-column)
  evidence      : per-db / per-table / per-column hint snippets

Lanes:
  R1 FAST   : BM25 (rank_bm25) + char n-gram (custom) on the lexical side.
              Optional sentence-transformers dense (SentenceTransformer)
              when available — we lazily import it so the module works
              without the heavy dependency installed.
  R2 PREMIUM: dense embedding + reranker — placeholder hooks left for
              the next session; current default is FAST.

Output of `retrieve_for_question` is a `RetrievalResult` carrying
top tables, top columns, evidence refs, raw scores and a confidence.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from query_rewrite_v2 import normalize_for_retrieval, make_grams


# ---------------- light BM25 implementation ----------------

class _BM25:
    """Tiny BM25Okapi reimplementation — avoids forcing rank_bm25 import."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1; self.b = b
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = sum(self.doc_len) / max(1, len(self.doc_len))
        self.df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for d in corpus:
            seen = {}
            for t in d:
                seen[t] = seen.get(t, 0) + 1
            self.tf.append(seen)
            for t in seen:
                self.df[t] = self.df.get(t, 0) + 1
        self.N = len(corpus)
        self.idf = {t: math.log(1 + (self.N - df + 0.5)/(df + 0.5))
                    for t, df in self.df.items()}

    def score(self, query: list[str]) -> list[float]:
        scores = [0.0] * self.N
        for qt in query:
            idf = self.idf.get(qt)
            if idf is None: continue
            for i, tfd in enumerate(self.tf):
                f = tfd.get(qt, 0)
                if f == 0: continue
                dl = self.doc_len[i]
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += idf * (f * (self.k1 + 1)) / denom
        return scores


# ---------------- corpus builders ----------------

def _tokenize(text: str) -> list[str]:
    return re.findall(r'[a-z0-9_]+', (text or '').lower())


def _build_table_corpus(ir) -> tuple[list[str], list[list[str]]]:
    keys: list[str] = []
    docs: list[list[str]] = []
    for t in ir.tables:
        keys.append(t.name)
        col_text = ' '.join(c.original_name for c in t.columns)
        docs.append(_tokenize(f'{t.original_name} {t.comment} {col_text}'))
    return keys, docs


def _build_column_corpus(ir) -> tuple[list[tuple[str,str]], list[list[str]]]:
    keys: list[tuple[str,str]] = []
    docs: list[list[str]] = []
    for t in ir.tables:
        for c in t.columns:
            keys.append((t.name, c.name))
            docs.append(_tokenize(
                f'{t.original_name} {c.original_name} {c.dtype} {c.comment}'
            ))
    return keys, docs


def _build_evidence_corpus(store, db_id: str) -> tuple[list, list[list[str]]]:
    items = store.for_db(db_id) if store else []
    keys = items
    docs = [_tokenize(it.text) for it in items]
    return keys, docs


# ---------------- result containers ----------------

@dataclass
class RetrievalResult:
    db_id: str
    selected_tables: list[str] = field(default_factory=list)
    selected_table_indexes: list[int] = field(default_factory=list)
    selected_columns: list[tuple[str,str]] = field(default_factory=list)
    table_scores: dict[str, float] = field(default_factory=dict)
    column_scores: dict[str, float] = field(default_factory=dict)
    evidence_refs: list = field(default_factory=list)
    confidence: float = 0.0
    reduction_ratio: float = 1.0
    fallback_used: bool = False
    rationale: list[str] = field(default_factory=list)


# ---------------- main entry points ----------------

def retrieve_tables(question: str, ir, *,
                     k_tables: int = 5,
                     bm25_weight: float = 1.0,
                     ngram_weight: float = 0.5) -> tuple[list[str], dict[str,float]]:
    """Score tables by lexical overlap of question vs. (name + comment + cols)."""
    keys, docs = _build_table_corpus(ir)
    bm = _BM25(docs)
    q_tokens = _tokenize(normalize_for_retrieval(question))
    bm_scores = bm.score(q_tokens)
    # n-gram complement: char-3gram intersection, normalised by table doc gram count
    q_grams = set(make_grams(question, 3))
    ng_scores = []
    for d in docs:
        d_text = ' '.join(d)
        d_grams = set(make_grams(d_text, 3))
        if not d_grams:
            ng_scores.append(0.0); continue
        inter = len(q_grams & d_grams)
        ng_scores.append(inter / len(d_grams))
    # Min-max normalise both then weighted sum
    def mm(xs):
        if not xs: return xs
        lo, hi = min(xs), max(xs)
        if hi - lo < 1e-9: return [0.0] * len(xs)
        return [(x - lo) / (hi - lo) for x in xs]
    bm_n = mm(bm_scores); ng_n = mm(ng_scores)
    fused = [bm25_weight * b + ngram_weight * g for b, g in zip(bm_n, ng_n)]
    ranked = sorted(zip(keys, fused), key=lambda x: -x[1])
    out = [k for k, _ in ranked[:k_tables]]
    return out, dict(ranked)


def retrieve_columns(question: str, ir, *,
                      k_columns: int = 12) -> tuple[list[tuple[str,str]], dict]:
    keys, docs = _build_column_corpus(ir)
    if not keys: return [], {}
    bm = _BM25(docs)
    q_tokens = _tokenize(normalize_for_retrieval(question))
    bm_scores = bm.score(q_tokens)
    ranked = sorted(zip(keys, bm_scores), key=lambda x: -x[1])
    out = [k for k, _ in ranked[:k_columns]]
    return out, {f'{t}.{c}': s for (t, c), s in ranked}


def retrieve_evidence(question: str, store, db_id: str, *,
                       k_evidence: int = 5):
    keys, docs = _build_evidence_corpus(store, db_id)
    if not keys: return []
    bm = _BM25(docs)
    q_tokens = _tokenize(normalize_for_retrieval(question))
    sc = bm.score(q_tokens)
    ranked = sorted(zip(keys, sc), key=lambda x: -x[1])
    return [k for k, _ in ranked[:k_evidence]]


def bidirectional_retrieve(question: str, ir, *,
                            k_tables: int = 5,
                            k_columns: int = 12) -> RetrievalResult:
    """Run table-first AND column-first retrieval, then RRF-fuse table indexes.

    Confidence = mean of fused-rank-rrf top-k weights.
    """
    table_idx_by_name = {t.name: i for i, t in enumerate(ir.tables)}

    # Table-first
    tf_tables, tf_scores = retrieve_tables(question, ir, k_tables=k_tables)
    # Column-first → derive tables from owning columns
    col_keys, col_score_map = retrieve_columns(question, ir, k_columns=k_columns)
    cf_tables_ranked: list[str] = []
    seen: set[str] = set()
    for (t, c) in col_keys:
        if t not in seen:
            cf_tables_ranked.append(t); seen.add(t)
        if len(cf_tables_ranked) >= k_tables: break

    # RRF fuse
    rrf: dict[str, float] = {}
    for r, t in enumerate(tf_tables):
        rrf[t] = rrf.get(t, 0.0) + 1.0 / (60 + r)
    for r, t in enumerate(cf_tables_ranked):
        rrf[t] = rrf.get(t, 0.0) + 1.0 / (60 + r)
    fused_tables = sorted(rrf.keys(), key=lambda t: -rrf[t])[:k_tables]

    # Compute confidence as the slope of top-k RRF scores
    if rrf:
        top_score = max(rrf.values())
        confidence = min(1.0, top_score / 0.034)  # 1/(60+0)+1/(60+0) = ~0.0333
    else:
        confidence = 0.0

    selected_indexes = [table_idx_by_name[t] for t in fused_tables
                        if t in table_idx_by_name]
    reduction_ratio = (len(ir.tables) - len(selected_indexes)) / max(1, len(ir.tables))

    # Selected columns: union of column-first results restricted to fused tables
    sel_cols = [(t, c) for (t, c) in col_keys if t in set(fused_tables)]

    return RetrievalResult(
        db_id=ir.db_id,
        selected_tables=fused_tables,
        selected_table_indexes=selected_indexes,
        selected_columns=sel_cols,
        table_scores=rrf,
        column_scores=col_score_map,
        confidence=confidence,
        reduction_ratio=reduction_ratio,
        fallback_used=False,
        rationale=[
            f'tf_top={tf_tables[:3]}',
            f'cf_top={cf_tables_ranked[:3]}',
            f'rrf={fused_tables}',
        ],
    )


# ----------------- R2 (PREMIUM) lane: BM25 + ngram + dense + RRF -----------------

def bidirectional_retrieve_r2(question: str, ir, *,
                                k_tables: int = 5,
                                k_columns: int = 12,
                                dense_retriever=None) -> RetrievalResult:
    """Premium retrieval: same as bidirectional_retrieve but RRF-fuses an
    additional dense-embedding ranking when `dense_retriever` is provided.

    Falls back to identical behaviour as R1 when dense_retriever is None.
    """
    table_idx_by_name = {t.name: i for i, t in enumerate(ir.tables)}

    # Lexical lanes (same as R1)
    tf_tables, _ = retrieve_tables(question, ir, k_tables=max(k_tables, 8))
    col_keys, col_score_map = retrieve_columns(question, ir, k_columns=max(k_columns, 16))
    cf_tables_ranked: list[str] = []
    seen: set[str] = set()
    for (t, c) in col_keys:
        if t not in seen: cf_tables_ranked.append(t); seen.add(t)
        if len(cf_tables_ranked) >= max(k_tables, 8): break

    # Dense lane
    dense_tables: list[str] = []
    dense_cols: list[tuple[str, str]] = []
    if dense_retriever is not None:
        try:
            tab_scores = dense_retriever.score_tables(question, ir.db_id, ir)
            tab_scores.sort(key=lambda x: -x[1])
            dense_tables = [k for k, _ in tab_scores[:max(k_tables, 8)]]
            col_scores = dense_retriever.score_columns(question, ir.db_id, ir)
            col_scores.sort(key=lambda x: -x[1])
            dense_cols = [k for k, _ in col_scores[:max(k_columns, 16)]]
        except Exception:
            dense_tables = []; dense_cols = []

    # RRF fuse table rankings (3-way)
    rrf: dict[str, float] = {}
    for r, t in enumerate(tf_tables): rrf[t] = rrf.get(t, 0.0) + 1.0 / (60 + r)
    for r, t in enumerate(cf_tables_ranked): rrf[t] = rrf.get(t, 0.0) + 1.0 / (60 + r)
    for r, t in enumerate(dense_tables): rrf[t] = rrf.get(t, 0.0) + 1.0 / (60 + r)
    fused_tables = sorted(rrf.keys(), key=lambda t: -rrf[t])[:k_tables]

    # Confidence = top RRF / theoretical max (3 lanes => 3/60 = 0.05)
    if rrf:
        top_score = max(rrf.values())
        max_theoretical = 3 / 60.0 if dense_tables else 2 / 60.0
        confidence = min(1.0, top_score / max_theoretical)
    else:
        confidence = 0.0

    selected_indexes = [table_idx_by_name[t] for t in fused_tables
                        if t in table_idx_by_name]
    reduction_ratio = (len(ir.tables) - len(selected_indexes)) / max(1, len(ir.tables))

    # Fuse column rankings (BM25 + dense) restricted to fused tables
    fused_table_set = set(fused_tables)
    col_rrf: dict[tuple[str, str], float] = {}
    for r, k in enumerate(col_keys):
        col_rrf[k] = col_rrf.get(k, 0.0) + 1.0 / (60 + r)
    for r, k in enumerate(dense_cols):
        col_rrf[k] = col_rrf.get(k, 0.0) + 1.0 / (60 + r)
    sel_cols = sorted([k for k in col_rrf if k[0] in fused_table_set],
                       key=lambda k: -col_rrf[k])[:k_columns]

    return RetrievalResult(
        db_id=ir.db_id,
        selected_tables=fused_tables,
        selected_table_indexes=selected_indexes,
        selected_columns=sel_cols,
        table_scores=rrf,
        column_scores=col_rrf,
        confidence=confidence,
        reduction_ratio=reduction_ratio,
        fallback_used=False,
        rationale=[
            f'tf_top={tf_tables[:3]}',
            f'cf_top={cf_tables_ranked[:3]}',
            f'dense_top={dense_tables[:3]}',
            f'rrf3={fused_tables}',
        ],
    )
