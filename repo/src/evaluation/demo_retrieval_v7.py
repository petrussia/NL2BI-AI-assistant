"""demo_retrieval_v7 — Spider train demonstration retrieval (DAIL-style).

Indexes Spider train (train_spider.json + train_others.json) by question
text (BM25 over tokens) AND by structural features inferred from the gold
SQL skeleton. For each dev question, returns top-k similar train demos,
with strong preference for same-db_id demos (which carry the most
transfer signal).

Public API:
  DemoRetriever(train_examples)
    .retrieve(question, db_id, k=3) -> list[dict]
    .render(demos, max_chars=900) -> str

Notes:
  - Train/test isolation: only Spider TRAIN entries are indexed.
  - SQL skeleton extraction is regex-based (cheap, dialect-agnostic).
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict


_TOK_RE = re.compile(r'[a-zA-Z][a-zA-Z0-9_]*')


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOK_RE.findall(text or '')]


def _sql_skeleton_features(sql: str) -> dict:
    s = (sql or '').lower()
    return {
        'has_join':     'join' in s,
        'has_group_by': 'group by' in s,
        'has_having':   'having' in s,
        'has_order_by': 'order by' in s,
        'has_limit':    'limit' in s,
        'has_distinct': 'distinct' in s,
        'has_subq':     s.count('select') > 1,
        'has_count':    'count(' in s,
        'has_avg':      'avg(' in s,
        'has_sum':      'sum(' in s,
        'has_max':      'max(' in s,
        'has_min':      'min(' in s,
        'has_in':       ' in (' in s or ' in(' in s,
        'has_like':     'like' in s,
        'has_union':    'union' in s,
        'has_intersect':'intersect' in s,
        'has_except':   'except' in s,
        'has_between':  'between' in s,
    }


def _question_intent_features(question: str) -> dict:
    q = (question or '').lower()
    feats = {
        'has_join':     False,  # we don't predict joins from question
        'has_group_by': any(w in q for w in (' for each ', ' per ', ' by each ', ' grouped by ', ' for every ')),
        'has_having':   any(w in q for w in (' more than ', ' less than ', ' at least ', ' at most ', ' fewer than ', ' more than ')),
        'has_order_by': any(w in q for w in (' ordered by ', ' sorted by ', ' top ', ' bottom ', ' largest ', ' smallest ', ' highest ', ' lowest ', ' most ', ' fewest ', ' first ', ' last ')),
        'has_limit':    any(w in q for w in (' top ', ' bottom ', ' first ', ' last ', ' one ', ' single ')),
        'has_distinct': any(w in q for w in (' distinct ', ' different ', ' unique ', ' separate ')),
        'has_subq':     any(w in q for w in (' who has the ', ' which has the ', ' all that ', ' any that ', ' whose ')),
        'has_count':    any(w in q for w in ('how many', ' count ', ' number of ', ' total number ')),
        'has_avg':      any(w in q for w in (' average ', ' avg ', ' mean ')),
        'has_sum':      any(w in q for w in (' total ', ' sum ', ' aggregate ')),
        'has_max':      any(w in q for w in (' max', ' maximum', ' highest', ' largest', ' greatest', ' top ')),
        'has_min':      any(w in q for w in (' min', ' minimum', ' lowest', ' smallest', ' fewest', ' bottom ')),
        'has_in':       any(w in q for w in (' in (', ' among ', ' is one of ')),
        'has_like':     any(w in q for w in (' contains ', ' starts with ', ' ends with ', ' matches ', ' name ')),
        'has_union':    any(w in q for w in (' or ', ' either ')),
        'has_intersect':any(w in q for w in (' both ', ' in common ', ' and also ')),
        'has_except':   any(w in q for w in (' but not ', ' except ', ' excluding ', ' without ')),
        'has_between':  any(w in q for w in (' between ', ' from ', ' to ')),
    }
    return feats


def _feature_jaccard(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    if not keys: return 0.0
    pos_a = {k for k in keys if a.get(k)}
    pos_b = {k for k in keys if b.get(k)}
    inter = len(pos_a & pos_b)
    union = len(pos_a | pos_b) or 1
    return inter / union


# ---------------- BM25 over a list of token lists ----------------

class _BM25:
    def __init__(self, corpus: list[list[str]], k1=1.5, b=0.75):
        self.k1 = k1; self.b = b
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = sum(self.doc_len) / max(1, len(self.doc_len))
        self.tf = []; self.df = {}
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


# ---------------- main retriever ----------------

class DemoRetriever:
    """Indexes Spider train; retrieves top-k demos for (question, db_id)."""

    def __init__(self, train_examples: list[dict]):
        self._items: list[dict] = []
        self._by_db: dict[str, list[int]] = defaultdict(list)
        for i, ex in enumerate(train_examples):
            entry = {
                'idx': i,
                'db_id': ex['db_id'],
                'question': ex.get('question', ''),
                'sql': ex.get('query', ''),
                'sql_features': _sql_skeleton_features(ex.get('query', '')),
                'q_tokens': _tokenize(ex.get('question', '')),
            }
            self._items.append(entry)
            self._by_db[ex['db_id']].append(i)
        # Global BM25 corpus
        self._global_bm25 = _BM25([e['q_tokens'] for e in self._items])
        # Per-db BM25 indices for fast same-db lookup
        self._db_bm25: dict[str, tuple[_BM25, list[int]]] = {}
        for db, idx_list in self._by_db.items():
            corp = [self._items[i]['q_tokens'] for i in idx_list]
            self._db_bm25[db] = (_BM25(corp), idx_list)

    def retrieve(self, question: str, db_id: str, k: int = 3,
                  feature_weight: float = 0.3) -> list[dict]:
        """Return top-k train demos. Same-db demos are strongly preferred.
        If the dev db_id is unseen in train, falls back to global BM25."""
        q_tokens = _tokenize(question)
        q_feats = _question_intent_features(question)
        results: list[tuple[float, dict]] = []
        # Stage 1 — same-db retrieval (preferred)
        if db_id in self._db_bm25:
            bm, idx_list = self._db_bm25[db_id]
            bm_scores = bm.score(q_tokens)
            # min-max normalize bm_scores in same-db pool
            if bm_scores and max(bm_scores) > 0:
                mx = max(bm_scores); mn = min(bm_scores)
                rng = (mx - mn) or 1.0
                norm = [(s - mn) / rng for s in bm_scores]
            else:
                norm = [0.0] * len(bm_scores)
            for j, idx in enumerate(idx_list):
                e = self._items[idx]
                fj = _feature_jaccard(q_feats, e['sql_features'])
                score = (1 - feature_weight) * norm[j] + feature_weight * fj
                # Same-db boost — flat +0.5 added to score
                results.append((score + 0.5, e))
        # Stage 2 — cross-db fallback (only if same-db pool empty or sparse)
        if len([r for r in results if r[0] > 0.5]) < k:
            # Use global BM25 to find top demos from any db
            scores = self._global_bm25.score(q_tokens)
            if scores and max(scores) > 0:
                mx = max(scores); mn = min(scores)
                rng = (mx - mn) or 1.0
                norm = [(s - mn) / rng for s in scores]
            else:
                norm = [0.0] * len(scores)
            for i, e in enumerate(self._items):
                if e['db_id'] == db_id: continue  # already considered
                fj = _feature_jaccard(q_feats, e['sql_features'])
                score = (1 - feature_weight) * norm[i] + feature_weight * fj
                results.append((score, e))
        results.sort(key=lambda x: -x[0])
        return [e for _, e in results[:k]]

    def render(self, demos: list[dict], max_chars: int = 900) -> str:
        """Render demos as a compact 'Examples' block for prompt injection."""
        if not demos: return ''
        parts: list[str] = ['Similar example queries (for guidance only — pick the right table/columns from the schema below):']
        total = len(parts[0])
        for i, e in enumerate(demos, 1):
            block = (f'\nExample {i}:\nQ: {e["question"]}\nSQL: {e["sql"].strip()}')
            if total + len(block) > max_chars: break
            parts.append(block); total += len(block)
        return '\n'.join(parts)
