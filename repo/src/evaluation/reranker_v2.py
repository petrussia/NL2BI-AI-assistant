"""reranker_v2 — Qwen3-Reranker wrapper for verifier_ranker_v2.

Loads Qwen/Qwen3-Reranker-0.6B (cross-encoder) lazily on first use. Provides
batched scoring of (query, document) pairs returning a probability in [0,1].
The Qwen3-Reranker is a causal LM that emits a yes/no token; we read the
log-probability of the "yes" token.

Used by:
- verifier_ranker_v2 to score (question, candidate_sql) — closes the BIRD
  discrimination gap from Phase C where exec/parse/intent signals can't
  distinguish two valid candidates that produce different rows.
- retrieval_hybrid_v2 (optional) for top-k re-ranking after BM25+dense
  recall.
"""
from __future__ import annotations

from typing import Iterable

DEFAULT_MODEL = 'Qwen/Qwen3-Reranker-0.6B'

# Qwen3-Reranker uses an explicit instruction template
INSTR = (
    'Given a SQL query and a natural-language question describing what the '
    'query should compute, judge whether the SQL correctly answers the '
    'question. Answer "yes" if the SQL is a faithful answer, "no" otherwise.'
)


class _Lazy:
    """Caches the loaded model+tokenizer so reuse is free across calls."""
    model = None
    tokenizer = None
    yes_id = None
    no_id = None
    device = 'cuda'


def _ensure_loaded(model_id: str = DEFAULT_MODEL, dtype: str = 'bf16'):
    if _Lazy.model is not None: return
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    _Lazy.tokenizer = AutoTokenizer.from_pretrained(model_id)
    _torch_dtype = torch.bfloat16 if dtype == 'bf16' else torch.float16
    _Lazy.model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=_torch_dtype, device_map='cuda',
    )
    _Lazy.model.eval()
    # Cache yes/no token ids
    yes_ids = _Lazy.tokenizer.encode('yes', add_special_tokens=False)
    no_ids = _Lazy.tokenizer.encode('no', add_special_tokens=False)
    _Lazy.yes_id = yes_ids[-1]
    _Lazy.no_id = no_ids[-1]


def _format_pair(question: str, sql: str, schema_hint: str = '') -> str:
    sh = ('\nSchema (truncated):\n' + schema_hint[:600]) if schema_hint else ''
    return (
        f'<Instruct>: {INSTR}\n'
        f'<Question>: {question}{sh}\n'
        f'<SQL>: {sql[:1200]}\n'
        f'<Answer>: '
    )


def score_pairs(pairs: Iterable[tuple[str, str]], *,
                 schema_hint: str = '',
                 model_id: str = DEFAULT_MODEL,
                 batch_size: int = 8) -> list[float]:
    """Returns a probability in [0,1] per pair (1.0 = SQL fits the question).

    Falls back to 0.5 (neutral) if the reranker cannot be loaded.
    """
    pairs = list(pairs)
    if not pairs: return []
    try:
        _ensure_loaded(model_id)
    except Exception:
        return [0.5] * len(pairs)

    import torch
    out: list[float] = []
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i:i+batch_size]
        prompts = [_format_pair(q, s, schema_hint) for q, s in batch]
        enc = _Lazy.tokenizer(prompts, return_tensors='pt',
                                padding=True, truncation=True,
                                max_length=2048).to(_Lazy.device)
        with torch.inference_mode():
            logits = _Lazy.model(**enc).logits  # (B, T, V)
        # Take the last non-pad position per row
        attn = enc['attention_mask']
        last_idx = attn.sum(dim=1) - 1
        for r in range(logits.shape[0]):
            li = last_idx[r].item()
            row = logits[r, li]
            yes_l = row[_Lazy.yes_id].item()
            no_l = row[_Lazy.no_id].item()
            # Soft-max on yes/no only — narrow but gives a clean probability
            import math
            ey, en = math.exp(yes_l), math.exp(no_l)
            p = ey / (ey + en + 1e-9)
            out.append(float(p))
    return out


def score(question: str, sql: str, *, schema_hint: str = '') -> float:
    """Single pair convenience wrapper."""
    return score_pairs([(question, sql)], schema_hint=schema_hint)[0]
