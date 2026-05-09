"""spider2_candidate_factory_v18 — emit candidate SQLs from JSON plan + Coder-7B.

For Phase 18.0 we ship 2 candidate families (the user's brief asks for 4;
A and B are the foundation, C/D are deferred to v18.1):

  A. deterministic SQL renderer over the validated structured plan
  B. Coder-7B direct emitter on the same compact schema pack

Each candidate is a dict:
  { 'family': 'A' | 'B',
    'sql_raw': str,
    'sql': str (post-extract / strip),
    'meta': {...} }
"""
from __future__ import annotations

import re
from typing import Optional


def _extract_sql(raw: str) -> str:
    if not raw:
        return ''
    m = re.search(r'```sql\s*\n?([\s\S]*?)```', raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n?([\s\S]*?)```', raw)
    if m:
        cand = m.group(1).strip()
        if any(kw in cand.upper() for kw in ('SELECT', 'WITH')):
            return cand
    upper = raw.upper()
    for tag in ('WITH ', 'SELECT '):
        idx = upper.find(tag)
        if idx >= 0:
            return raw[idx:].strip()
    return raw.strip()


def family_A_deterministic(plan: dict, pack: dict, *, lane: str = 'bq') -> dict:
    from sql_renderer_v18 import render_bq
    sql = render_bq(plan, pack=pack) if lane == 'bq' else render_bq(plan, pack=pack)
    return {'family': 'A', 'sql_raw': sql, 'sql': sql,
              'meta': {'tables_used': plan.get('selected_tables', [])}}


def family_B_coder7b(question: str, pack: dict, external_knowledge: str = '',
                      *, _gen_fn=None) -> dict:
    """Family B uses Qwen2.5-Coder-7B-Instruct as a control direct emitter.

    `_gen_fn` is the deterministic-decoding callable to use; defaults to
    the global `_gen` set up by the v17 launcher. The caller can also pass
    in a custom function. Returns family-B candidate dict.
    """
    from sql_renderer_v18 import render_coder7b_direct_prompt
    prompt = render_coder7b_direct_prompt(question, pack, external_knowledge)
    if _gen_fn is None:
        _gen_fn = globals().get('_gen') or __builtins__.__dict__.get('_gen')  # type: ignore[arg-type]
    if _gen_fn is None:
        raise NotImplementedError('No _gen function available for family B')
    raw = _gen_fn(prompt, max_new=900)
    return {'family': 'B', 'sql_raw': raw, 'sql': _extract_sql(raw),
              'meta': {'prompt_chars': len(prompt)}}


def emit_candidates(question: str, pack: dict, plan: Optional[dict],
                       external_knowledge: str = '',
                       *, lane: str = 'bq', _gen_fn=None) -> list:
    cands = []
    if plan is not None:
        try:
            cands.append(family_A_deterministic(plan, pack, lane=lane))
        except Exception as e:
            cands.append({'family': 'A', 'sql': '', 'sql_raw': '',
                          'meta': {'error': f'{type(e).__name__}:{str(e)[:200]}'}})
    if _gen_fn is not None:
        try:
            cands.append(family_B_coder7b(question, pack, external_knowledge,
                                            _gen_fn=_gen_fn))
        except Exception as e:
            cands.append({'family': 'B', 'sql': '', 'sql_raw': '',
                          'meta': {'error': f'{type(e).__name__}:{str(e)[:200]}'}})
    return cands
