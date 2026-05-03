"""dense_retriever_v2 — Qwen3-Embedding wrapper with per-db doc cache.

Embeds table_docs / column_docs / evidence ONCE per db and caches the
matrix so future queries to the same db are fast (cosine similarity in
numpy on cached vectors).

Used as one of the corpora in retrieval_hybrid_v2 lane R2 (PREMIUM):
RRF-fused with BM25 + char-ngram. The fused ranking is then optionally
re-scored by reranker_v2 (cross-encoder).
"""
from __future__ import annotations

from typing import Sequence
import numpy as np

DEFAULT_MODEL = 'Qwen/Qwen3-Embedding-0.6B'


class _Lazy:
    model = None
    tokenizer = None
    dim = None
    device = 'cuda'


def _ensure_loaded(model_id: str = DEFAULT_MODEL):
    if _Lazy.model is not None: return
    import torch
    from transformers import AutoModel, AutoTokenizer
    _Lazy.tokenizer = AutoTokenizer.from_pretrained(model_id)
    _Lazy.model = AutoModel.from_pretrained(
        model_id, torch_dtype=torch.bfloat16, device_map='cuda',
    )
    _Lazy.model.eval()


def _last_token_pooling(hidden, attention_mask):
    """Qwen3-Embedding uses last-token (EOS) pooling."""
    import torch
    seq_lens = attention_mask.sum(dim=1) - 1
    batch_idx = torch.arange(hidden.shape[0], device=hidden.device)
    return hidden[batch_idx, seq_lens]


def encode(texts: Sequence[str], *, batch_size: int = 16,
            max_length: int = 512, model_id: str = DEFAULT_MODEL) -> np.ndarray:
    """Returns a (N, D) numpy array of L2-normalized embeddings.

    Falls back to a deterministic hash-based pseudo-embedding when the model
    can't be loaded — the rest of the pipeline keeps working but dense
    retrieval becomes a no-op.
    """
    if not texts: return np.zeros((0, 16), dtype=np.float32)
    try:
        _ensure_loaded(model_id)
    except Exception:
        # Hash-based fallback so the pipeline still runs
        return _fallback_embed(texts)

    import torch
    out_chunks = []
    for i in range(0, len(texts), batch_size):
        batch = list(texts[i:i+batch_size])
        enc = _Lazy.tokenizer(batch, return_tensors='pt', padding=True,
                                truncation=True, max_length=max_length).to(_Lazy.device)
        with torch.inference_mode():
            hidden = _Lazy.model(**enc).last_hidden_state
        pooled = _last_token_pooling(hidden, enc['attention_mask'])
        # Normalize
        pooled = pooled / (pooled.norm(dim=1, keepdim=True) + 1e-9)
        out_chunks.append(pooled.float().cpu().numpy())
    arr = np.vstack(out_chunks)
    if _Lazy.dim is None: _Lazy.dim = arr.shape[1]
    return arr


def _fallback_embed(texts: Sequence[str], dim: int = 64) -> np.ndarray:
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        # bag-of-token-hash, normalized
        for tok in (t or '').lower().split():
            h = hash(tok) % dim
            out[i, h] += 1.0
        norm = float(np.linalg.norm(out[i]))
        if norm > 0: out[i] /= norm
    return out


# --------- per-db cache ---------

class DenseRetriever:
    """Caches vectors per db_id so repeated queries are cheap."""

    def __init__(self, model_id: str = DEFAULT_MODEL):
        self.model_id = model_id
        self._cache: dict[str, dict] = {}

    def _build(self, db_id: str, ir):
        # Build per-db corpus: tables, columns, evidence (later)
        table_keys = []; table_texts = []
        for t in ir.tables:
            table_keys.append(t.name)
            cols_concat = ' '.join(c.original_name for c in t.columns)
            table_texts.append(f'{t.original_name} {t.comment} {cols_concat}')
        col_keys = []; col_texts = []
        for t in ir.tables:
            for c in t.columns:
                col_keys.append((t.name, c.name))
                col_texts.append(f'{t.original_name}.{c.original_name} {c.dtype} {c.comment}')
        table_emb = encode(table_texts, model_id=self.model_id)
        col_emb = encode(col_texts, model_id=self.model_id)
        self._cache[db_id] = {
            'table_keys': table_keys, 'table_emb': table_emb,
            'col_keys': col_keys, 'col_emb': col_emb,
        }

    def for_db(self, db_id: str, ir):
        if db_id not in self._cache:
            self._build(db_id, ir)
        return self._cache[db_id]

    def score_tables(self, question: str, db_id: str, ir) -> list[tuple[str, float]]:
        q = encode([question], model_id=self.model_id)[0]
        c = self.for_db(db_id, ir)
        sims = c['table_emb'] @ q
        return list(zip(c['table_keys'], sims.tolist()))

    def score_columns(self, question: str, db_id: str, ir) -> list[tuple[tuple[str,str], float]]:
        q = encode([question], model_id=self.model_id)[0]
        c = self.for_db(db_id, ir)
        sims = c['col_emb'] @ q
        return list(zip(c['col_keys'], sims.tolist()))
