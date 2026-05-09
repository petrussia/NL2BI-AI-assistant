"""difficulty_router_v2 — cheap heuristic to decide whether the planner is worth invoking.

Used by baselines_b3_v5: easy queries skip the planner entirely (B0-style direct
generation on retrieved schema), hard queries get the planner+compiler path.

Rationale: the planner is expensive (extra LM call) and can hurt quality if
it gets the plan wrong. We only pay that cost for queries that look like they
benefit from explicit structure.
"""
from __future__ import annotations
import re

# Tokens that signal a query likely needs aggregation / multi-table reasoning
_AGG_KEYWORDS = (
    'how many', 'count', 'total', 'sum of', 'average', 'avg', 'mean', 'maximum',
    'max of', 'min of', 'minimum', 'highest', 'lowest', 'most', 'fewest',
    'top ', 'bottom ', 'first ', 'last ',
    'percentage', 'percent', 'ratio', 'fraction', 'proportion',
    'difference', 'distinct',
    'group by', 'per ', 'each ',
)
_TIME_KEYWORDS = (
    'year', 'month', 'day', 'week', 'quarter', 'date', 'time',
    'before', 'after', 'between', 'since', 'until',
)
_SET_OP_KEYWORDS = (
    'and ', 'but not', 'except', 'in common', 'either', 'both ',
    'union of', 'intersect', 'or have',
)
_NESTED_KEYWORDS = (
    'who has the', 'which has the', 'find the customer who',
    'find the ... whose',
    'all ... that have',
    'any ... that',
)


def classify(question: str, *,
              n_tables_in_db: int = 1,
              n_tables_retrieved: int = 1) -> dict:
    """Return {'difficulty': 'easy'|'hard', 'reasons': [...], 'score': float}.

    Score is a soft signal in [0,1] — used for logging and for the controller
    to decide whether to keep the planner output even on borderline cases.
    """
    q = (question or '').lower().strip()
    reasons: list[str] = []

    # Word count heuristic: very short questions are usually easy
    n_words = len(re.findall(r'\w+', q))
    if n_words <= 6: reasons.append(f'short_query({n_words}w)')
    if n_words >= 18: reasons.append(f'long_query({n_words}w)')

    # Keyword scans
    has_agg = any(kw in q for kw in _AGG_KEYWORDS)
    has_time = any(kw in q for kw in _TIME_KEYWORDS)
    has_set = any(kw in q for kw in _SET_OP_KEYWORDS)
    has_nested = any(kw in q for kw in _NESTED_KEYWORDS)
    if has_agg: reasons.append('aggregation_kw')
    if has_time: reasons.append('temporal_kw')
    if has_set: reasons.append('set_op_kw')
    if has_nested: reasons.append('nested_kw')

    # Schema scope: many retrieved tables ⇒ likely multi-table
    if n_tables_retrieved >= 3: reasons.append(f'multi_table({n_tables_retrieved})')
    if n_tables_in_db >= 8 and n_tables_retrieved >= 2: reasons.append('large_db_multi_table')

    # Score
    score = 0.0
    if n_words >= 10: score += 0.15
    if has_agg: score += 0.30
    if has_time: score += 0.15
    if has_set: score += 0.20
    if has_nested: score += 0.20
    if n_tables_retrieved >= 3: score += 0.20
    score = min(1.0, score)

    difficulty = 'hard' if score >= 0.30 else 'easy'

    # Override: very short factoid is always easy
    if n_words <= 4 and not (has_set or has_nested):
        difficulty = 'easy'; reasons.append('override_factoid')

    return {'difficulty': difficulty, 'reasons': reasons, 'score': round(score, 3),
            'n_words': n_words}
