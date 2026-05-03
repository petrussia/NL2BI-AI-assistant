"""query_rewrite_v2 — light-touch query normalization for retrieval.

We deliberately keep this conservative: aggressive rewriting hurts more
than it helps once retrieval is already bidirectional. Operations:
- lowercase
- strip punctuation (keeps digits and underscores)
- expand business glossary aliases (singular<->plural for common nouns)
- NOT: stemming, NOT: stop-word removal (BM25 handles it well enough on
  short queries; removing stop words breaks "between A and B" intents).
"""
from __future__ import annotations

import re

_PUNCT = re.compile(r'[^\w\s]')
_WS = re.compile(r'\s+')


def normalize_for_retrieval(question: str) -> str:
    s = (question or '').lower()
    s = _PUNCT.sub(' ', s)
    s = _WS.sub(' ', s).strip()
    return s


def expand_glossary(question: str, glossary: dict[str, list[str]]) -> str:
    """Append glossary expansions to the question (BM25-friendly).

    `glossary` maps canonical term -> list of synonyms. We append
    " || syn1 syn2 ..." so that exact-match BM25 fires on synonyms
    without distorting the original token order.
    """
    s = normalize_for_retrieval(question)
    extras: list[str] = []
    for canonical, syns in glossary.items():
        if canonical.lower() in s:
            extras.extend(syns)
        else:
            for syn in syns:
                if syn.lower() in s:
                    extras.append(canonical); break
    if not extras: return s
    return s + ' || ' + ' '.join(dict.fromkeys(extras))


def make_grams(text: str, n: int = 3) -> list[str]:
    """Character n-gram tokens for fuzzy lexical matching."""
    s = re.sub(r'\s+', ' ', text or '').strip().lower()
    if len(s) < n: return [s] if s else []
    return [s[i:i+n] for i in range(len(s) - n + 1)]
