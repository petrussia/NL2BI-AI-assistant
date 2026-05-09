"""spider2_agent_v8 — BigQuery-only multi-candidate agent for Spider2-Lite.

Pipeline per item:
  1. Load BQ schema index (already cached per-db in the runner).
  2. Build retrieval bundle (tables + columns + docs + join hints).
  3. Generate up to 3 candidates (C0_direct, C1_retrieval_docs, C2_cte_decomp).
  4. Verify each via BQ dry_run (free).
  5. If no candidate passes dry_run, attempt bounded repair on the
     highest-scoring failed candidate (max_repair_rounds).
  6. Select the winner via heuristic + optional judge.
  7. Execute the chosen SQL via real BQ exec (bytes-billed capped).
  8. Return a structured result dict + per-candidate audit.

This is A_bq lane only. SF/SQLite lanes are NOT touched here.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from spider2_bq_schema_index_v8 import BqSchemaIndex, render_subset
from spider2_bq_retrieval_v8 import (
    RetrievalBundle, retrieve_for_question,
)
from spider2_bq_candidate_generator_v8 import make_candidates
from spider2_bq_verifier_v8 import verify_candidate, execute_chosen
from spider2_bq_selector_v8 import select_candidate, _candidate_score
from spider2_bq_repair_v8 import attempt_repair


def run_bq_agent_step(question: str, idx: BqSchemaIndex, *,
                        gen: Callable, bq_executor: Callable,
                        doc_paths: list[Path] | None = None,
                        judge_gen: Callable | None = None,
                        max_repair_rounds: int = 2,
                        max_candidate_bytes_soft: int = 5 * 10**9,
                        include_direct: bool = True,
                        include_retrieval: bool = True,
                        include_cte: bool = True,
                        max_new_sql: int = 800,
                        max_new_cte: int = 1100,
                        execute_chosen_query: bool = True,
                        max_rows_exec: int = 1000) -> dict:
    """One pass over a single Spider2 BQ item. Returns full audit."""
    t0 = time.time()
    bundle: RetrievalBundle = retrieve_for_question(
        idx, question, doc_paths=doc_paths,
        k_tables=6, k_columns=14, k_docs=3,
    )

    # --- candidate generation ---
    cands = make_candidates(question, idx, bundle, gen=gen,
                             include_direct=include_direct,
                             include_retrieval=include_retrieval,
                             include_cte=include_cte,
                             max_new_sql=max_new_sql,
                             max_new_cte=max_new_cte)
    for c in cands:
        verify_candidate(c, idx, bq_executor,
                          max_bytes_soft=max_candidate_bytes_soft)

    # --- if no parses=True, repair the highest-scoring one ---
    repair_record = None
    parses_any = any((c.get('verifier') or {}).get('parses') for c in cands)
    if not parses_any and cands and bq_executor is not None:
        # Pick candidate with shortest error or most table_refs as repair seed
        seed = max(cands, key=lambda c: (c.get('verifier') or {}).get('table_refs_n', 0))
        sv = seed.get('verifier') or {}
        # Build small schema text from selected_keys for repair prompt
        schema_text = render_subset(idx, bundle.selected_keys, max_cols=20,
                                      include_samples=False)
        repair_record = attempt_repair(
            question, schema_text,
            seed.get('sql', ''),
            sv.get('error_message', '') or sv.get('error_type', ''),
            gen=gen, bq_executor=bq_executor,
            max_rounds=max_repair_rounds,
        )
        if repair_record['success']:
            new_cand = {'source': 'C3_repaired', 'sql': repair_record['sql'],
                         'audit': {'repair_rounds': repair_record['rounds'],
                                    'seed_source': seed['source']}}
            verify_candidate(new_cand, idx, bq_executor,
                              max_bytes_soft=max_candidate_bytes_soft)
            cands.append(new_cand)

    # --- selector ---
    schema_summary = render_subset(idx, bundle.selected_keys, max_cols=15,
                                     include_samples=False)
    chosen, sel_audit = select_candidate(
        cands, question,
        judge_gen=judge_gen,
        judge_close_margin=0.4,
        schema_summary=schema_summary,
    )

    # --- final BQ exec on the chosen ---
    if chosen is None:
        return _empty_result(question, bundle, cands, repair_record,
                              sel_audit, t0)

    if execute_chosen_query and bq_executor is not None and (chosen.get('verifier') or {}).get('parses'):
        execute_chosen(chosen, bq_executor, max_rows=max_rows_exec)

    return _build_result(question, bundle, cands, chosen,
                          repair_record, sel_audit, t0)


def _build_result(question, bundle, cands, chosen, repair_record,
                    sel_audit, t0) -> dict:
    v = chosen.get('verifier') or {}
    return {
        'sql': chosen.get('sql', ''),
        'final_source': chosen.get('source', ''),
        'parses': v.get('parses'),
        'executable': v.get('executable'),
        'rows_count': v.get('rows_count', 0),
        'rows_sample': (v.get('rows') or [])[:5],
        'all_known': v.get('all_known'),
        'table_refs': v.get('table_refs', []),
        'table_refs_n': v.get('table_refs_n', 0),
        'unknown_tables': v.get('unknown_tables', []),
        'has_join': v.get('has_join'),
        'has_groupby': v.get('has_groupby'),
        'has_subquery': v.get('has_subquery'),
        'has_window': v.get('has_window'),
        'has_unnest': v.get('has_unnest'),
        'has_with': v.get('has_with'),
        'bytes_billed': v.get('bytes_billed', 0),
        'bytes_processed': v.get('bytes_processed', 0),
        'error_type': v.get('error_type', ''),
        'error_message': (v.get('error_message') or '')[:300],
        'phase': v.get('phase', ''),
        'repair_used': repair_record is not None,
        'repair_success': bool(repair_record and repair_record.get('success')),
        'repair_rounds': repair_record['rounds'] if repair_record else 0,
        'repair_trace': repair_record['trace'] if repair_record else [],
        'judge_invoked': sel_audit.get('judge_invoked', False),
        'judge_overrode': sel_audit.get('judge_overrode', False),
        'judge_chose': sel_audit.get('judge_chose', ''),
        'judge_confidence': sel_audit.get('judge_confidence', 0.0),
        'judge_reason': sel_audit.get('judge_reason', ''),
        'candidate_count': len(cands),
        'candidates_summary': [{
            'source': c['source'],
            'parses': (c.get('verifier') or {}).get('parses'),
            'table_refs_n': (c.get('verifier') or {}).get('table_refs_n', 0),
            'unknown_tables_n': len((c.get('verifier') or {}).get('unknown_tables') or []),
            'sql_chars': len(c.get('sql', '') or ''),
            'error_type': (c.get('verifier') or {}).get('error_type', ''),
            'bytes_processed': (c.get('verifier') or {}).get('bytes_processed', 0),
            'score': round(_candidate_score(c, question), 3),
        } for c in cands],
        'retrieval': {
            'selected_keys': bundle.selected_keys,
            'doc_titles': [d.title for d in bundle.docs],
            'doc_sources': sorted({d.source for d in bundle.docs}),
            'fallback_used': bundle.fallback_used,
            'tables_n': len(bundle.tables),
            'columns_n': len(bundle.columns),
            'joins_n': len(bundle.joins),
        },
        'wall_time_s': round(time.time() - t0, 2),
    }


def _empty_result(question, bundle, cands, repair_record, sel_audit, t0) -> dict:
    return {
        'sql': '', 'final_source': '', 'parses': False, 'executable': False,
        'all_known': None, 'table_refs': [], 'table_refs_n': 0,
        'has_join': False, 'has_groupby': False, 'has_subquery': False,
        'bytes_billed': 0, 'bytes_processed': 0,
        'error_type': 'no_candidate', 'error_message': '',
        'repair_used': repair_record is not None,
        'repair_success': bool(repair_record and repair_record.get('success')),
        'judge_invoked': sel_audit.get('judge_invoked', False),
        'judge_overrode': False,
        'candidate_count': len(cands),
        'candidates_summary': [],
        'retrieval': {'selected_keys': bundle.selected_keys,
                       'fallback_used': bundle.fallback_used},
        'wall_time_s': round(time.time() - t0, 2),
    }
