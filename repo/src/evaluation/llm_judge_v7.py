"""llm_judge_v7 — SQL-aware candidate selector via LLM-as-judge.

Designed to close the Phase R2 / Phase C BIRD discrimination gap that the
heuristic verifier and the saturated Qwen3-Reranker-0.6B could not resolve.

Public API:
  judge_candidates(question, ir, candidates_with_meta, *, gen,
                    evidence_text='', schema_summary='', max_new=160)
    -> dict with keys
       best_candidate_id, confidence (0..1), reason, risk_flags

Design:
  - Reuses the main coder LLM (Qwen2.5-Coder-7B-Instruct) as judge.
    No extra model loading; no extra GPU memory.
  - Strict JSON output. CoT explicitly forbidden in the prompt.
  - Compact rubric (no rambling).
  - Robust JSON parse: regex finds the first balanced object even if the
    model emits prose around it.
  - Soft-fails: if no valid JSON, returns {best=None, confidence=0,
    reason='parse_failed', risk_flags=['parse_failed']} so the caller
    falls back to its heuristic pick.

Calibration:
  Caller (`baselines_b6_v7`) decides WHEN to invoke the judge — only
  when the heuristic margin is small AND C2 evidence exists AND
  benchmark warrants it. The judge itself does not gate.
"""
from __future__ import annotations

import json
import re
import textwrap


_JUDGE_INSTRUCTIONS = """
You are a SQL judge. Given a natural-language question, a compact schema
summary, optional domain evidence, and a list of candidate SQL queries
(each with execution metadata), pick the single candidate that best
answers the question.

Hard rules — your output MUST be a SINGLE JSON object with exactly these
keys, no prose, no markdown, no chain-of-thought:
{
  "best_candidate_id": "<id from the input list>",
  "confidence": <float 0..1>,
  "reason": "<one short sentence>",
  "risk_flags": ["<short tag>", ...]
}

Selection rubric (apply in order):
1. Prefer candidates that are executable. Only consider non-executable
   candidates if every candidate failed; in that case, prefer the one
   that parses and matches the question intent.
2. Prefer SQL whose result-shape is consistent with the question:
   "how many" / "count" / "average" / "sum" / "what is the X" → scalar
   or single-row aggregate; "list", "which", "find all" → table; "for
   each" / "by X" → grouped.
3. Prefer SQL that uses the supplied DOMAIN EVIDENCE if the evidence
   explicitly defines a formula, ratio, threshold, or column meaning
   that the question relies on. Penalize SQL that ignores strong
   evidence on a question that needs it.
4. Penalize candidates with obvious errors: missing filters, wrong
   aggregation function, wrong join direction, wrong time/date logic,
   incorrect grouping.
5. Do NOT prefer the anchor merely because it is the anchor. Do NOT
   prefer longer SQL. Do NOT prefer planner SQL by default.
6. If two candidates produce the same result-row signature, prefer the
   one with simpler query and lower estimated risk.

Confidence calibration:
- 0.90+ : the choice is clearly correct given the evidence and shape.
- 0.70  : the choice is likely correct but a close alternative exists.
- 0.50  : a guess; you have weak signal.
- 0.30- : you are unsure or all candidates look bad.

Risk flag vocabulary (zero or more):
"close_call", "no_evidence_used", "all_executable_disagree",
"empty_result", "all_empty", "no_executable", "evidence_conflict",
"bad_aggregation", "bad_join", "bad_filter", "bad_grouping",
"shape_mismatch".
""".strip()


_JSON_RE = re.compile(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', re.DOTALL)


def _candidate_block(c: dict, max_sql_chars: int = 600) -> str:
    sql = (c.get('sql') or '').strip()
    if len(sql) > max_sql_chars: sql = sql[:max_sql_chars] + '...'
    md = c.get('meta', {}) or {}
    meta_parts = [f"source={c.get('source','?')}",
                   f"executable={md.get('executable')}",
                   f"rows={md.get('rows_count', 0)}"]
    if md.get('error_type'): meta_parts.append(f"err={md['error_type']}")
    if md.get('result_shape'): meta_parts.append(f"shape={md['result_shape']}")
    if md.get('rows_signature'):
        sig = md['rows_signature']
        if isinstance(sig, (tuple, list)) and sig:
            sig_str = repr(sig[:3])
            if len(sig_str) > 80: sig_str = sig_str[:80] + '...'
            meta_parts.append(f"sig={sig_str}")
    return f"id={c['id']} | {' | '.join(meta_parts)}\nSQL:\n{sql}"


def make_judge_prompt(question: str, schema_summary: str,
                       evidence_text: str,
                       candidates_with_meta: list[dict]) -> str:
    """Build the judge prompt. Caller is responsible for trimming the
    schema_summary to a sensible size (~400-800 chars)."""
    cand_blocks = "\n\n".join(_candidate_block(c) for c in candidates_with_meta)
    ev = (evidence_text or '').strip()
    ev_block = (f"DOMAIN EVIDENCE (use if relevant; ignore if not):\n{ev[:600]}"
                 if ev else "DOMAIN EVIDENCE: <none>")
    schema_block = (schema_summary or '').strip()[:1200]
    return textwrap.dedent(f"""
    {_JUDGE_INSTRUCTIONS}

    QUESTION:
    {question.strip()}

    SCHEMA (compact):
    {schema_block}

    {ev_block}

    CANDIDATES:
    {cand_blocks}

    JSON:
    """).strip()


def parse_judge_output(raw: str, valid_ids: set[str]) -> dict:
    """Robust parse. Returns dict with best_candidate_id (str|None),
    confidence (float), reason (str), risk_flags (list[str]),
    parse_status ('ok'|'fail'|'invalid_id')."""
    text = (raw or '').strip()
    text = re.sub(r'^```(?:json)?', '', text, flags=re.I).strip()
    text = re.sub(r'```$', '', text).strip()

    # try direct first, then balanced-object regex
    obj = None
    try:
        obj = json.loads(text)
    except Exception:
        for m in _JSON_RE.finditer(text):
            try:
                obj = json.loads(m.group(0)); break
            except Exception:
                continue
    if not isinstance(obj, dict):
        return {'best_candidate_id': None, 'confidence': 0.0,
                'reason': 'parse_failed', 'risk_flags': ['parse_failed'],
                'parse_status': 'fail'}

    bid = obj.get('best_candidate_id')
    conf = obj.get('confidence', 0.5)
    try: conf = float(conf)
    except Exception: conf = 0.5
    conf = max(0.0, min(1.0, conf))
    reason = (obj.get('reason') or '').strip()[:200]
    rf = obj.get('risk_flags') or []
    if not isinstance(rf, list): rf = [str(rf)]
    rf = [str(x)[:40] for x in rf][:8]

    status = 'ok'
    if bid is None or str(bid) not in valid_ids:
        status = 'invalid_id'
        bid = None
    else:
        bid = str(bid)
    return {'best_candidate_id': bid, 'confidence': conf,
            'reason': reason, 'risk_flags': rf,
            'parse_status': status}


def judge_candidates(question: str, ir,
                      candidates_with_meta: list[dict], *,
                      gen,
                      evidence_text: str = '',
                      schema_summary: str = '',
                      max_new: int = 160) -> dict:
    """End-to-end judge call.

    `candidates_with_meta`: list of dicts with at minimum
        {'id': str, 'source': str, 'sql': str, 'meta': {executable, rows_count,
                                                          error_type,
                                                          result_shape?,
                                                          rows_signature?}}.
    Returns a dict with the parsed verdict plus the raw output and the
    actual prompt (for audit).
    """
    if not candidates_with_meta:
        return {'best_candidate_id': None, 'confidence': 0.0,
                'reason': 'no_candidates', 'risk_flags': ['no_candidates'],
                'parse_status': 'fail', 'raw': '', 'prompt_chars': 0}
    valid_ids = {str(c['id']) for c in candidates_with_meta}
    prompt = make_judge_prompt(question, schema_summary, evidence_text,
                                candidates_with_meta)
    try:
        raw = gen(prompt, max_new=max_new)
    except Exception as exc:
        return {'best_candidate_id': None, 'confidence': 0.0,
                'reason': f'judge_call_exc:{type(exc).__name__}',
                'risk_flags': ['judge_call_exc'],
                'parse_status': 'fail', 'raw': '', 'prompt_chars': len(prompt)}
    verdict = parse_judge_output(raw, valid_ids)
    verdict['raw'] = (raw or '')[:600]
    verdict['prompt_chars'] = len(prompt)
    return verdict
