"""spider2_agent_v7 — bounded agent loop for Spider2-Lite.

Lane-aware ReAct-style agent that produces a single SQL prediction per
item, with structured trace. Designed to be deterministic at every step
that is not the LLM call, so reruns are reproducible up to LLM sampling.

Design contract:
  - Up to 4 candidate families: C0 direct, C1 retrieval+evidence,
    C2 CTE-decomposition, C3 tool-explored draft.
  - Each candidate is verified by parse + safe + schema-validity +
    dry-run; lane A/B candidates also tried via real exec.
  - llm_judge_v7 (existing module) is reused for the final pick when
    multiple candidates disagree; falls back to verifier_ranker_v2 score.
  - Bounded repair (1 round) on the chosen candidate if its dry-run /
    exec failed and the lane has an executor.

Action JSON contract (used inside C3 exploration only):
  {"action": "<name>", "args": {...}, "reason_short": "<≤80 chars>"}
Action vocabulary (mapped to spider2_tools_v7):
  schema_search, metadata_doc_search, join_path_search,
  column_profile, sample_value_probe, dialect_check,
  draft_sql, submit_sql, give_up.

Entry point:
  run_spider2_agent_step(question, ir, *, lane, executor, gen,
                          dialect_target, max_steps, ...)
"""
from __future__ import annotations

import json
import re
import textwrap
from typing import Callable

from schema_ir_v2 import render_compact_schema
from schema_linker_bidirectional_v2 import link as schema_link
from dialect_utils_v2 import is_safe_select, transpile, normalize_sql
from sqlglot_checks_v2 import (
    ast_validity, schema_validity, structural_features as ast_struct_features,
)
from verifier_ranker_v2 import SOURCE_RISK
from llm_judge_v7 import judge_candidates
from baselines_b1_v5 import _extract_sql as _v5_extract_sql

import spider2_tools_v7 as tools


# Spider2-specific SQL extractor — preserves `WITH` prefix so multi-CTE
# answers don't get mangled. The frozen v5 extractor in
# baselines_b1_v5._extract_sql looks only for `SELECT` and silently
# strips a leading `WITH x AS (...),` clause, producing orphan `),`
# tokens that BQ rejects with "Expected end of input but got ')'".
_SQL_BLOCK_RE = re.compile(r'(?is)((?:with|select)\b.*)')

def _extract_sql(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r'^```(?:sql)?', '', text, flags=re.I).strip()
    text = re.sub(r'```$', '', text).strip()
    m = _SQL_BLOCK_RE.search(text)
    if m: text = m.group(1).strip()
    text = text.split('\n\n')[0].strip()
    if ';' in text: text = text.split(';', 1)[0].strip()
    return text.rstrip(';')


SOURCE_RISK_S2 = {
    'C0_anchor': 0,
    'C1_retrieval_evidence': 1,
    'C2_cte_decomp': 2,
    'C3_explore': 3,
}


# ===================== prompts =====================

def _b0_prompt(schema_text: str, question: str, *, dialect: str,
                evidence_text: str = '') -> str:
    dialect_label = {'bigquery': 'BigQuery Standard SQL',
                      'snowflake': 'Snowflake SQL',
                      'sqlite': 'SQLite SQL'}.get(dialect, f'{dialect} SQL')
    ev_block = (f'\nDOMAIN KNOWLEDGE (use only if relevant):\n{evidence_text[:800]}\n'
                 if evidence_text.strip() else '')
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate ONE valid {dialect_label}
    query for the question. Use only tables/columns from the schema.
    Return SQL only — no markdown, no explanation, no DECLARE statements
    unless absolutely required.

    SCHEMA:
    {schema_text}
    {ev_block}
    Question: {question}
    SQL:
    """).strip()


def _cte_prompt(schema_text: str, question: str, *, dialect: str,
                 evidence_text: str = '') -> str:
    dialect_label = {'bigquery': 'BigQuery', 'snowflake': 'Snowflake',
                      'sqlite': 'SQLite'}.get(dialect, dialect)
    ev_block = (f'\nDOMAIN KNOWLEDGE:\n{evidence_text[:600]}\n'
                 if evidence_text.strip() else '')
    return textwrap.dedent(f"""
    Write ONE {dialect_label} query that answers the question. Decompose
    the logic into named CTEs (`WITH step1 AS (...), step2 AS (...)
    SELECT ...`). Each CTE should compute one logical step. Final SELECT
    consumes the CTEs. Return SQL only.

    SCHEMA:
    {schema_text}
    {ev_block}
    Question: {question}
    SQL:
    """).strip()


_ACTION_INSTRUCTIONS = """
You are exploring a database to answer a SQL question. At each step you
emit ONE action as JSON. Valid actions:

  {"action":"schema_search","args":{"terms":["..."]},"reason_short":"..."}
  {"action":"metadata_doc_search","args":{"terms":["..."]},"reason_short":"..."}
  {"action":"join_path_search","args":{"from":"t1","to":"t2"},"reason_short":"..."}
  {"action":"column_profile","args":{"table":"t","column":"c"},"reason_short":"..."}
  {"action":"sample_value_probe","args":{"table":"t","column":"c"},"reason_short":"..."}
  {"action":"draft_sql","args":{"sql":"SELECT ..."},"reason_short":"..."}
  {"action":"submit_sql","args":{"sql":"SELECT ..."},"reason_short":"..."}
  {"action":"give_up","args":{},"reason_short":"..."}

Hard rules:
- Output a SINGLE JSON object. No markdown, no prose, no commentary.
- The "sql" arg, when present, must be a single complete query.
- Stop exploring as soon as you have enough info; emit submit_sql.
""".strip()


def _explore_step_prompt(question: str, schema_text: str, evidence_text: str,
                          history: list[dict], dialect: str) -> str:
    obs_blocks = []
    for h in history[-4:]:
        a = h.get('action', '?'); res = json.dumps(h.get('result'),
                                                     ensure_ascii=False)[:300]
        obs_blocks.append(f'[{a}] -> {res}')
    obs_text = '\n'.join(obs_blocks) if obs_blocks else '(no prior steps)'
    return textwrap.dedent(f"""
    {_ACTION_INSTRUCTIONS}

    DIALECT: {dialect}

    QUESTION:
    {question}

    SCHEMA (compact):
    {schema_text[:1600]}

    DOMAIN KNOWLEDGE:
    {(evidence_text or '')[:600]}

    PRIOR_STEPS:
    {obs_text}

    NEXT_ACTION (JSON only):
    """).strip()


_JSON_RE = re.compile(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', re.DOTALL)


def _parse_action(raw: str) -> dict | None:
    text = (raw or '').strip()
    text = re.sub(r'^```(?:json)?', '', text, flags=re.I).strip()
    text = re.sub(r'```$', '', text).strip()
    try:
        obj = json.loads(text)
    except Exception:
        obj = None
    if obj is None:
        for m in _JSON_RE.finditer(text):
            try:
                obj = json.loads(m.group(0)); break
            except Exception:
                continue
    if not isinstance(obj, dict): return None
    if 'action' not in obj: return None
    if not isinstance(obj.get('args', {}), dict): obj['args'] = {}
    return obj


# ===================== candidate generation =====================

def _verify_candidate(sql: str, ir, *, executor, dialect: str,
                       dry_only: bool) -> dict:
    """Parse + safe + schema-validity + dry-run (+ optional exec).

    Important: sqlglot's BigQuery parser does NOT support several common
    BQ idioms (wildcard `_TABLE_SUFFIX`, dotted backticked refs in some
    forms). For lanes with a real executor we therefore treat the
    executor's dry_run as the authoritative parse signal. sqlglot's
    verdict is recorded for reference but does not gate the candidate.
    """
    ast = ast_validity(sql, dialect)
    sql_clean = (sql or '').strip()
    sv = schema_validity(sql_clean, ir, dialect) if ast['parses'] else {
        'all_known': False, 'unknown_tables': [], 'unknown_columns': []}
    sf = ast_struct_features(sql_clean, dialect) if ast['parses'] else {}
    safe, why = is_safe_select(sql_clean, dialect)

    if not sql_clean:
        return {'parses': False, 'safe_select': False, 'all_known': False,
                'executable': None, 'rows_count': 0,
                'phase': 'empty', 'error_type': 'empty_sql',
                'error_message': '', 'unknown_tables': [],
                'unknown_columns': [], 'bytes_billed': 0,
                'bytes_processed': 0,
                'parses_sqlglot': False}

    # No executor (A_sf / C_struct fallback): trust sqlglot
    if executor is None or getattr(executor, 'mode', None) == 'noop':
        if not ast['parses']:
            return {'parses': False, 'safe_select': False, 'all_known': False,
                    'executable': None, 'rows_count': 0,
                    'phase': 'parse', 'error_type': 'parse_error',
                    'error_message': '', 'unknown_tables': [],
                    'unknown_columns': [], 'bytes_billed': 0,
                    'bytes_processed': 0, 'parses_sqlglot': False}
        return {'parses': True, 'safe_select': safe, 'safe_reason': why,
                'all_known': sv['all_known'],
                'unknown_tables': sv['unknown_tables'],
                'unknown_columns': sv['unknown_columns'],
                'executable': None, 'rows_count': 0,
                'phase': 'parse_only', 'error_type': '',
                'error_message': '',
                'has_join': bool(sf.get('join_count', 0)),
                'has_groupby': bool(sf.get('has_group_by')),
                'has_window': bool(sf.get('has_window')),
                'has_subquery': bool(sf.get('has_subquery')),
                'bytes_billed': 0, 'bytes_processed': 0,
                'parses_sqlglot': True}

    # Executor available: dry_run is the authoritative parse signal
    out = tools.sql_dry_run_or_execute(sql_clean, executor, dialect=dialect,
                                         dry_only=dry_only, max_rows=200)
    parses_exec = bool(out['ok']) or out.get('phase') == 'execute'
    # If the dry_run failed in the safety guard rather than the executor,
    # surface that as parse failure
    if out.get('phase') == 'safety':
        parses_exec = False
    return {'parses': parses_exec or ast['parses'],
            'parses_sqlglot': ast['parses'],
            'parses_executor': parses_exec,
            'safe_select': safe, 'safe_reason': why,
            'all_known': sv['all_known'],
            'unknown_tables': sv['unknown_tables'],
            'unknown_columns': sv['unknown_columns'],
            'executable': out['ok'],
            'rows_count': len(out.get('rows') or []),
            'phase': out.get('phase', ''),
            'error_type': out.get('error_type', ''),
            'error_message': out.get('error_message', ''),
            'has_join': bool(sf.get('join_count', 0)),
            'has_groupby': bool(sf.get('has_group_by')),
            'has_window': bool(sf.get('has_window')),
            'has_subquery': bool(sf.get('has_subquery')),
            'bytes_billed': int(out.get('bytes_billed') or 0),
            'bytes_processed': int(out.get('bytes_processed') or 0)}


def _candidate(source: str, sql: str, ir, *, executor, dialect: str,
                dry_only: bool, audit: dict | None = None) -> dict:
    sql = (sql or '').strip().rstrip(';')
    v = _verify_candidate(sql, ir, executor=executor, dialect=dialect,
                            dry_only=dry_only)
    return {'source': source, 'sql': sql, 'verifier': v,
             'audit': audit or {}}


def _candidate_score(c: dict) -> float:
    """Composite score for verifier_ranker_v2-style ordering."""
    v = c['verifier']
    score = 0.0
    if v.get('parses'): score += 1.0
    if v.get('safe_select'): score += 0.5
    if v.get('all_known'): score += 1.5
    score -= 0.5 * len(v.get('unknown_tables') or [])
    score -= 0.2 * len(v.get('unknown_columns') or [])
    if v.get('executable') is True: score += 2.0
    elif v.get('executable') is False: score -= 1.0
    # very small structural complexity bonus (some questions need joins)
    if v.get('has_join'): score += 0.05
    if v.get('has_subquery'): score += 0.05
    # source risk: anchor cheapest, explore most expensive
    score -= 0.05 * SOURCE_RISK_S2.get(c['source'], 0)
    return score


# ===================== main entry =====================

def run_spider2_agent_step(question: str, ir, *,
                              lane: str,
                              executor=None,
                              gen: Callable,
                              dialect_target: str = 'sqlite',
                              evidence_text: str = '',
                              full_schema_max_tables: int = 12,
                              max_explore_steps: int = 4,
                              max_repair_rounds: int = 1,
                              include_retrieval: bool = True,
                              include_cte: bool = True,
                              include_explore: bool = True,
                              judge_gen: Callable | None = None,
                              judge_policy: dict | None = None) -> dict:
    """Run one Spider2-Lite item. Returns a result dict + per-step trace."""
    if lane == 'A_sf':
        return {
            'sql': '', 'lane': lane, 'mode': 'blocked_snowflake',
            'final_source': '', 'candidates': [],
            'trace': [], 'judge_invoked': False, 'judge_overrode': False,
            'judge_confidence': 0.0, 'reason': 'blocked_no_sf_creds',
            'bytes_billed_total': 0, 'bytes_processed_total': 0,
        }

    dry_only = (lane == 'C_struct' or executor is None
                 or getattr(executor, 'mode', None) == 'noop')

    # Schema link / reduce
    try:
        link_res = schema_link(question, ir, k_tables=full_schema_max_tables,
                                expand_extra=4)
        sel_tables = link_res.selected_tables
    except Exception:
        link_res = None; sel_tables = None
    full_schema_text = render_compact_schema(ir, include_comments=True)
    if sel_tables and len(ir.tables) > full_schema_max_tables:
        reduced_text = render_compact_schema(ir, include_comments=True,
                                              subset_tables=sel_tables)
    else:
        reduced_text = full_schema_text
    # Hard prompt cap — Spider2 enterprise schemas can render to 100K+ chars
    # which makes inference unusably slow. Truncate the rendered text to
    # ~4000 chars; the LLM sees fewer tables but answers fast.
    MAX_PROMPT_SCHEMA_CHARS = 4000
    if len(reduced_text) > MAX_PROMPT_SCHEMA_CHARS:
        reduced_text = (reduced_text[:MAX_PROMPT_SCHEMA_CHARS]
                          + '\n-- ...(schema truncated for prompt budget)')
    schema_text_for_prompt = (reduced_text if len(full_schema_text) > 4000
                                 else full_schema_text)
    if len(schema_text_for_prompt) > MAX_PROMPT_SCHEMA_CHARS:
        schema_text_for_prompt = (schema_text_for_prompt[:MAX_PROMPT_SCHEMA_CHARS]
                                     + '\n-- ...(truncated)')

    candidates: list[dict] = []
    trace: list[dict] = []
    bytes_billed_total = 0; bytes_processed_total = 0

    # ---------- C0: direct anchor ----------
    p0 = _b0_prompt(schema_text_for_prompt, question,
                     dialect=dialect_target, evidence_text=evidence_text)
    s0_raw = gen(p0, max_new=800)
    s0 = _extract_sql(s0_raw)
    cand0 = _candidate('C0_anchor', s0, ir, executor=executor,
                        dialect=dialect_target, dry_only=dry_only,
                        audit={'prompt_chars': len(p0)})
    candidates.append(cand0)
    bytes_billed_total += cand0['verifier'].get('bytes_billed', 0)
    bytes_processed_total += cand0['verifier'].get('bytes_processed', 0)

    # ---------- C1: retrieval+evidence (optional) ----------
    if include_retrieval:
        p1 = _b0_prompt(reduced_text, question, dialect=dialect_target,
                         evidence_text=evidence_text)
        s1_raw = gen(p1, max_new=800)
        s1 = _extract_sql(s1_raw)
        cand1 = _candidate('C1_retrieval_evidence', s1, ir, executor=executor,
                            dialect=dialect_target, dry_only=dry_only,
                            audit={'selected_tables': sel_tables or [],
                                    'reduction_ratio': getattr(link_res,
                                                                'reduction_ratio',
                                                                1.0)})
        candidates.append(cand1)
        bytes_billed_total += cand1['verifier'].get('bytes_billed', 0)
        bytes_processed_total += cand1['verifier'].get('bytes_processed', 0)

    # ---------- C2: CTE decomposition ----------
    if include_cte:
        p2 = _cte_prompt(reduced_text, question, dialect=dialect_target,
                         evidence_text=evidence_text)
        s2_raw = gen(p2, max_new=900)
        s2 = _extract_sql(s2_raw)
        cand2 = _candidate('C2_cte_decomp', s2, ir, executor=executor,
                            dialect=dialect_target, dry_only=dry_only)
        candidates.append(cand2)
        bytes_billed_total += cand2['verifier'].get('bytes_billed', 0)
        bytes_processed_total += cand2['verifier'].get('bytes_processed', 0)

    # ---------- C3: bounded explore loop ----------
    explore_sql = ''
    if include_explore and max_explore_steps > 0:
        history: list[dict] = []
        for step_i in range(max_explore_steps):
            ep = _explore_step_prompt(question, schema_text_for_prompt,
                                       evidence_text, history,
                                       dialect_target)
            try:
                a_raw = gen(ep, max_new=200)
            except Exception as exc:
                trace.append({'step': step_i, 'phase': 'gen_exc',
                              'error': type(exc).__name__})
                break
            act = _parse_action(a_raw)
            if act is None:
                trace.append({'step': step_i, 'phase': 'parse_fail',
                              'raw': a_raw[:200]}); break
            name = (act.get('action') or '').lower()
            args = act.get('args') or {}
            reason = (act.get('reason_short') or '')[:120]
            obs: object = None
            if name == 'schema_search':
                obs = tools.schema_search(ir, ' '.join(args.get('terms', []))
                                           or question)
            elif name == 'metadata_doc_search':
                obs = tools.metadata_doc_search(ir, args.get('terms') or [])
            elif name == 'join_path_search':
                obs = tools.join_path_search(ir, str(args.get('from', '')),
                                              str(args.get('to', '')))
            elif name == 'column_profile':
                obs = tools.column_profile(executor,
                                            str(args.get('table', '')),
                                            str(args.get('column', '')))
            elif name == 'sample_value_probe':
                obs = tools.column_profile(executor,
                                            str(args.get('table', '')),
                                            str(args.get('column', '')))
            elif name in ('draft_sql', 'submit_sql'):
                explore_sql = (args.get('sql') or '').strip()
                trace.append({'step': step_i, 'action': name, 'args': args,
                              'reason': reason})
                if name == 'submit_sql': break
                continue
            elif name == 'give_up':
                trace.append({'step': step_i, 'action': name,
                              'reason': reason}); break
            else:
                trace.append({'step': step_i, 'action': name,
                              'reason': f'unknown_action:{name}'}); break
            entry = {'step': step_i, 'action': name, 'args': args,
                     'reason': reason, 'result': obs}
            trace.append(entry); history.append(entry)
        if explore_sql:
            cand3 = _candidate('C3_explore', _extract_sql(explore_sql),
                                 ir, executor=executor,
                                 dialect=dialect_target, dry_only=dry_only,
                                 audit={'steps_used': len(trace)})
            candidates.append(cand3)
            bytes_billed_total += cand3['verifier'].get('bytes_billed', 0)
            bytes_processed_total += cand3['verifier'].get('bytes_processed', 0)

    # ---------- rank ----------
    candidates.sort(key=lambda c: -_candidate_score(c))
    top = candidates[0]
    top2 = candidates[1] if len(candidates) > 1 else None
    margin = _candidate_score(top) - (_candidate_score(top2) if top2 else 0.0)

    # ---------- judge (optional) ----------
    judge_invoked = False; judge_overrode = False
    judge_chose = None; judge_conf = 0.0; judge_reason = ''
    pol = {'judge_close_margin': 0.5, 'judge_override_min_conf': 0.65,
            'allow_anchor_override': True}
    if judge_policy: pol.update(judge_policy)
    if (judge_gen is not None and len(candidates) >= 2
            and margin < pol['judge_close_margin']):
        judge_invoked = True
        cand_meta = []
        for i, c in enumerate(candidates[:4]):
            v = c['verifier']
            cand_meta.append({
                'id': str(i), 'source': c['source'], 'sql': c['sql'],
                'meta': {'executable': v.get('executable'),
                          'rows_count': v.get('rows_count', 0),
                          'error_type': v.get('error_type', ''),
                          'parses': v.get('parses')},
            })
        verdict = judge_candidates(question, ir, cand_meta, gen=judge_gen,
                                     evidence_text=evidence_text,
                                     schema_summary=schema_text_for_prompt[:1200])
        judge_conf = verdict.get('confidence', 0.0)
        judge_reason = verdict.get('reason', '')
        bid = verdict.get('best_candidate_id')
        if bid is not None:
            try:
                jchose = candidates[int(bid)]
                judge_chose = jchose['source']
                if (judge_conf >= pol['judge_override_min_conf']
                        and jchose['source'] != top['source']):
                    if pol['allow_anchor_override'] or top['source'] != 'C0_anchor':
                        top = jchose
                        judge_overrode = True
            except (ValueError, IndexError):
                pass

    # ---------- bounded repair on chosen ----------
    repair_used = False; repair_rounds = 0; final_error = ''
    chosen_sql = top['sql']
    v = top['verifier']
    if (executor is not None and not dry_only
            and v.get('executable') is False and max_repair_rounds > 0):
        rep = tools.bounded_repair(chosen_sql, v.get('error_message') or '',
                                     gen=gen, executor=executor,
                                     dialect=dialect_target,
                                     max_rounds=max_repair_rounds)
        repair_used = True
        repair_rounds = rep['rounds']
        if rep['safe']:
            chosen_sql = rep['sql']
            v = _verify_candidate(chosen_sql, ir, executor=executor,
                                    dialect=dialect_target, dry_only=False)
            top = {**top, 'sql': chosen_sql, 'verifier': v,
                    'audit': {**top.get('audit', {}), 'repaired': True}}
        else:
            final_error = rep.get('final_error', '')

    return {
        'sql': chosen_sql,
        'lane': lane,
        'mode': v.get('phase') or ('parse_only' if dry_only else 'execute'),
        'dialect_target': dialect_target,
        'final_source': top['source'],
        'candidates': [{'source': c['source'],
                          'sql': c['sql'][:600],
                          'parses': c['verifier'].get('parses'),
                          'safe_select': c['verifier'].get('safe_select'),
                          'all_known': c['verifier'].get('all_known'),
                          'executable': c['verifier'].get('executable'),
                          'unknown_tables_n': len(c['verifier'].get('unknown_tables') or []),
                          'unknown_columns_n': len(c['verifier'].get('unknown_columns') or []),
                          'rows_count': c['verifier'].get('rows_count', 0),
                          'error_type': c['verifier'].get('error_type', ''),
                          'bytes_billed': c['verifier'].get('bytes_billed', 0),
                          'score': round(_candidate_score(c), 3)}
                         for c in candidates],
        'top_score': round(_candidate_score(top), 3),
        'top2_margin': round(margin, 3),
        'judge_invoked': judge_invoked,
        'judge_overrode': judge_overrode,
        'judge_chose_source': judge_chose or '',
        'judge_confidence': judge_conf,
        'judge_reason': judge_reason,
        'verifier': v,
        'repair_used': repair_used,
        'repair_rounds': repair_rounds,
        'final_error': final_error,
        'trace': trace,
        'bytes_billed_total': bytes_billed_total,
        'bytes_processed_total': bytes_processed_total,
    }
