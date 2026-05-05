# Phase 9 (Spider2 agent_v7) consolidation — produce master matrix v9,
# structural CSV, lane breakdown plot, and (where possible) execution
# match against gold exec_result CSVs.
#
# Inputs (Drive):
#   outputs/predictions/spider2lite_agent_v7_full_predictions.jsonl
#   outputs/traces/spider2lite_agent_v7_traces.jsonl
#   external_benchmarks/spider2_lite/.../evaluation_suite/gold/exec_result/
#       <instance_id>_a.csv (and _b, _c variants)
#   external_benchmarks/spider2_lite/.../evaluation_suite/gold/spider2lite_eval.jsonl
#
# Outputs:
#   outputs/tables/spider2_structural_full_v7.csv
#   outputs/tables/spider2_oracle_tables_full_v7.csv  (per-table)
#   outputs/tables/final_experiment_master_matrix_fullbench_v9.csv
#   outputs/tables/paired_significance_phase_nine_v1.csv  (lane-wise)
#   outputs/logs/spider2_lane_breakdown_v7.md
#   outputs/plots/spider2_agent_v7_overview.png
from __future__ import annotations

import csv, json, os, sys, traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
S2 = ROOT / 'external_benchmarks' / 'spider2_lite' / 'raw' / 'Spider2' / 'spider2-lite'
PRED = ROOT / 'outputs' / 'predictions' / 'spider2lite_agent_v7_full_predictions.jsonl'
TRACES = ROOT / 'outputs' / 'traces' / 'spider2lite_agent_v7_traces.jsonl'
TBL = ROOT / 'outputs' / 'tables'
LOG = ROOT / 'outputs' / 'logs'
PLT = ROOT / 'outputs' / 'plots'
for p in (TBL, LOG, PLT): p.mkdir(parents=True, exist_ok=True)


def utcnow(): return datetime.now(timezone.utc).isoformat()


def load_predictions() -> list[dict]:
    if not PRED.exists(): return []
    return [json.loads(l) for l in PRED.open(encoding='utf-8')]


def gold_results_for(instance_id: str) -> list[Path]:
    """Return existing gold exec_result CSVs for this item."""
    GR = S2 / 'evaluation_suite' / 'gold' / 'exec_result'
    return sorted(GR.glob(f'{instance_id}_*.csv'))


def load_csv_rows(p: Path) -> list[tuple]:
    rows: list[tuple] = []
    try:
        with p.open(encoding='utf-8', errors='ignore') as f:
            rd = csv.reader(f)
            for r in rd:
                rows.append(tuple(r))
    except Exception:
        return []
    return rows


def compare_rows_loose(a: list[tuple], b: list[tuple], *,
                         ignore_order: bool = True) -> bool:
    """Compare predicted rows (a) against gold rows (b).

    Loose comparator: strip header rows on both sides if shapes mismatch
    by 1, lower-case strings, ignore ordering when ignore_order=True.
    Returns True iff multiset(or sequence) of cells matches.
    """
    if not a or not b: return bool(a) == bool(b)
    # drop header if obvious
    if len(a) >= 1 and len(b) >= 1 and len(a[0]) == len(b[0]):
        # if first row of a is ALL string and b's first row contains numeric,
        # likely a includes header — drop it
        def _looks_header(row):
            return all(isinstance(c, str) and not c.replace('.','').replace('-','').isdigit()
                        for c in row)
        if _looks_header(a[0]) and not _looks_header(b[0]):
            a = a[1:]
        if _looks_header(b[0]) and not _looks_header(a[0]):
            b = b[1:]
    def _norm(row):
        return tuple(str(c).strip().lower() for c in row)
    A = [_norm(r) for r in a]; B = [_norm(r) for r in b]
    if ignore_order:
        return sorted(A) == sorted(B)
    return A == B


def write_structural_csv(rows: list[dict]) -> Path:
    p = TBL / 'spider2_structural_full_v7.csv'
    fields = ['instance_id', 'lane', 'db_id', 'route_reason', 'dialect',
              'final_source', 'mode', 'parses', 'safe_select', 'all_known',
              'unknown_tables_n', 'unknown_columns_n',
              'has_join', 'has_groupby', 'has_subquery',
              'executable', 'rows_count', 'error_type',
              'judge_invoked', 'judge_overrode', 'judge_confidence',
              'repair_used', 'repair_rounds',
              'bytes_billed', 'bytes_processed',
              'lm_calls', 'latency_ms', 'completion_tokens']
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in fields})
    return p


def aggregate_by_lane(rows: list[dict]) -> dict:
    by_lane: dict[str, dict] = defaultdict(lambda: {'n': 0, 'parses': 0,
                                                       'safe_select': 0,
                                                       'all_known': 0,
                                                       'executable': 0,
                                                       'em_official': 0,
                                                       'em_total_compared': 0,
                                                       'judge_invoked': 0,
                                                       'judge_overrode': 0,
                                                       'repair_used': 0,
                                                       'bytes_billed_sum': 0,
                                                       'final_sources': Counter()})
    for r in rows:
        L = r.get('lane', '?')
        d = by_lane[L]
        d['n'] += 1
        d['parses'] += int(bool(r.get('parses')))
        d['safe_select'] += int(bool(r.get('safe_select')))
        d['all_known'] += int(bool(r.get('all_known')))
        d['executable'] += int(r.get('executable') is True)
        d['judge_invoked'] += int(bool(r.get('judge_invoked')))
        d['judge_overrode'] += int(bool(r.get('judge_overrode')))
        d['repair_used'] += int(bool(r.get('repair_used')))
        d['bytes_billed_sum'] += int(r.get('bytes_billed') or 0)
        if r.get('final_source'):
            d['final_sources'][r['final_source']] += 1
        if r.get('execution_match') is True: d['em_official'] += 1
        if r.get('execution_match') is not None: d['em_total_compared'] += 1
    # convert Counter to dict
    for L in by_lane:
        by_lane[L]['final_sources'] = dict(by_lane[L]['final_sources'])
    return dict(by_lane)


def gold_match_eligible(rows: list[dict], *, lane_target: str = 'A_bq') -> list[dict]:
    """Re-run predicted SQL for lane_target items against gold result
    rows to compute execution_match. Lane B_sqlite gold is non-comparable
    (sample-data oracle); we only attempt execution_match for A_bq.

    Note: this runs queries through BQ again at consolidation time —
    can be expensive. Capped at 1 GB billed per query like the runner.
    Skipped if BQ creds aren't available.
    """
    SECRETS = ROOT / 'secrets' / 'spider2_bq_sa.json'
    if not SECRETS.exists(): return rows
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(str(SECRETS))
        proj = json.loads(SECRETS.read_text(encoding='utf-8'))['project_id']
        client = bigquery.Client(project=proj, credentials=creds)
    except Exception as e:
        print(f'BQ_INIT_FAIL: {type(e).__name__}: {e}')
        return rows

    out: list[dict] = []
    for r in rows:
        if r.get('lane') != lane_target:
            out.append(r); continue
        if not r.get('generated_sql'):
            out.append(r); continue
        gold_csvs = gold_results_for(r.get('instance_id', ''))
        if not gold_csvs:
            r['execution_match'] = None
            r['exec_match_reason'] = 'no_gold_exec_result'
            out.append(r); continue
        gold_variants = [load_csv_rows(p) for p in gold_csvs]
        gold_variants = [g for g in gold_variants if g]
        try:
            cfg = bigquery.QueryJobConfig(maximum_bytes_billed=10**9,
                                            use_query_cache=False)
            j = client.query(r['generated_sql'], job_config=cfg)
            pred_rows = [tuple(row.values()) for row in j.result(timeout=90,
                                                                  max_results=10000)]
            r['_pred_rows_n_consolidation'] = len(pred_rows)
            r['_bytes_billed_consolidation'] = int(j.total_bytes_billed or 0)
            # any-variant match
            matched = any(compare_rows_loose(pred_rows, g) for g in gold_variants)
            r['execution_match'] = bool(matched)
            r['exec_match_reason'] = ('matched_variant' if matched else
                                        'rows_mismatch_all_variants')
        except Exception as e:
            r['execution_match'] = False
            r['exec_match_reason'] = f'consolidation_exec_fail:{type(e).__name__}:{str(e)[:100]}'
        out.append(r)
    return out


def write_master_matrix(rows: list[dict], by_lane: dict) -> Path:
    """Append a v9 row to the master matrix tracking spider2 cells.

    Format mirrors prior fullbench v* matrices but with separate columns
    per lane since Spider2 is split.
    """
    p = TBL / 'final_experiment_master_matrix_fullbench_v9.csv'
    fields = ['method', 'spider_dev_full_ex', 'bird_minidev_full_ex',
               'spider2_a_bq_n', 'spider2_a_bq_em',
               'spider2_b_sqlite_n', 'spider2_b_sqlite_parses',
               'spider2_a_sf_n', 'spider2_c_struct_n',
               'spider2_total_n', 'spider2_executable_n',
               'spider2_parses_n', 'spider2_all_known_n',
               'spider2_judge_invoked_n', 'spider2_judge_overrode_n',
               'spider2_bytes_billed_total']
    # Read prior matrix (v8 if available) so we keep B0/B3_v4/B6_v7 rows
    prior = []
    for vN in (8, 7, 6, 5):
        prior_p = TBL / f'final_experiment_master_matrix_fullbench_v{vN}.csv'
        if prior_p.exists():
            with prior_p.open(encoding='utf-8') as f:
                rd = csv.DictReader(f)
                prior = [dict(r) for r in rd]
            break
    # New agent_v7 row
    a_bq = by_lane.get('A_bq', {}); b_sq = by_lane.get('B_sqlite', {})
    a_sf = by_lane.get('A_sf', {}); c_st = by_lane.get('C_struct', {})
    n_total = sum(d.get('n', 0) for d in by_lane.values())
    n_exec = sum(d.get('executable', 0) for d in by_lane.values())
    n_parses = sum(d.get('parses', 0) for d in by_lane.values())
    n_all_known = sum(d.get('all_known', 0) for d in by_lane.values())
    n_judge = sum(d.get('judge_invoked', 0) for d in by_lane.values())
    n_ovr = sum(d.get('judge_overrode', 0) for d in by_lane.values())
    bytes_total = sum(d.get('bytes_billed_sum', 0) for d in by_lane.values())
    new_row = {
        'method': 'agent_v7_spider2',
        'spider_dev_full_ex': '', 'bird_minidev_full_ex': '',
        'spider2_a_bq_n': a_bq.get('n', 0),
        'spider2_a_bq_em': (a_bq.get('em_official', 0) /
                              max(1, a_bq.get('em_total_compared', 0))) if a_bq else 0,
        'spider2_b_sqlite_n': b_sq.get('n', 0),
        'spider2_b_sqlite_parses': b_sq.get('parses', 0),
        'spider2_a_sf_n': a_sf.get('n', 0),
        'spider2_c_struct_n': c_st.get('n', 0),
        'spider2_total_n': n_total,
        'spider2_executable_n': n_exec,
        'spider2_parses_n': n_parses,
        'spider2_all_known_n': n_all_known,
        'spider2_judge_invoked_n': n_judge,
        'spider2_judge_overrode_n': n_ovr,
        'spider2_bytes_billed_total': bytes_total,
    }
    out = prior + [new_row]
    with p.open('w', newline='', encoding='utf-8') as f:
        # Write union-of-fields header
        all_fields: list[str] = []
        seen = set()
        for r in out:
            for k in r:
                if k not in seen: seen.add(k); all_fields.append(k)
        for k in fields:
            if k not in seen: seen.add(k); all_fields.append(k)
        w = csv.DictWriter(f, fieldnames=all_fields)
        w.writeheader()
        for r in out: w.writerow(r)
    return p


def write_lane_md(by_lane: dict, total_rows: int) -> Path:
    p = LOG / 'spider2_lane_breakdown_v7.md'
    lines = ['# Spider2-Lite agent_v7 — lane breakdown',
             '',
             f'_Generated: {utcnow()}_',
             '',
             f'Total items: {total_rows}',
             '',
             '| Lane | n | parses | safe% | all_known | exec_ok | EX vs gold | judge_inv | judge_ovr | repair |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for L in ('A_bq', 'B_sqlite', 'A_sf', 'C_struct'):
        d = by_lane.get(L, {})
        n = d.get('n', 0)
        if n == 0: continue
        em = (d.get('em_official', 0) / d['em_total_compared']
                if d.get('em_total_compared') else None)
        em_str = f'{em*100:.2f}%' if em is not None else '—'
        lines.append(f'| {L} | {n} | {d.get("parses",0)} | '
                     f'{100*d.get("safe_select",0)/n:.1f}% | '
                     f'{d.get("all_known",0)} | {d.get("executable",0)} | '
                     f'{em_str} | {d.get("judge_invoked",0)} | '
                     f'{d.get("judge_overrode",0)} | {d.get("repair_used",0)} |')
    lines.append('')
    lines.append('## Final source mix per lane')
    lines.append('')
    for L, d in by_lane.items():
        if not d.get('final_sources'): continue
        lines.append(f'### {L}')
        for src, cnt in sorted(d['final_sources'].items(), key=lambda x: -x[1]):
            lines.append(f'- {src}: {cnt}')
        lines.append('')
    p.write_text('\n'.join(lines), encoding='utf-8')
    return p


def write_plot(by_lane: dict) -> Path | None:
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        return None
    lanes = ['A_bq', 'B_sqlite', 'A_sf', 'C_struct']
    n = [by_lane.get(L, {}).get('n', 0) for L in lanes]
    parses = [by_lane.get(L, {}).get('parses', 0) for L in lanes]
    exec_n = [by_lane.get(L, {}).get('executable', 0) for L in lanes]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = range(len(lanes))
    ax.bar([i - 0.25 for i in x], n, width=0.25, label='items')
    ax.bar(list(x), parses, width=0.25, label='parses')
    ax.bar([i + 0.25 for i in x], exec_n, width=0.25, label='executable')
    ax.set_xticks(list(x)); ax.set_xticklabels(lanes)
    ax.set_title('Spider2-Lite agent_v7 — per-lane structural metrics')
    ax.legend()
    p = PLT / 'spider2_agent_v7_overview.png'
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig)
    return p


def main():
    rows = load_predictions()
    print(f'rows_loaded: {len(rows)}')
    if not rows:
        print('NO_PREDICTIONS_YET — run the runner first'); return

    # Optional: compute execution_match for A_bq via re-execution
    do_em = os.environ.get('PHASE9_RUN_EXEC_MATCH', '1') == '1'
    if do_em:
        print('Re-running A_bq predictions vs gold exec_result CSVs ...')
        rows = gold_match_eligible(rows, lane_target='A_bq')
    by_lane = aggregate_by_lane(rows)
    summary = {k: {'n': v['n'], 'exec': v['executable']}
                for k, v in by_lane.items()}
    print(f'by_lane: {summary}')

    p_struct = write_structural_csv(rows)
    p_md = write_lane_md(by_lane, len(rows))
    p_mat = write_master_matrix(rows, by_lane)
    p_plt = write_plot(by_lane)
    print(f'WROTE: {p_struct}')
    print(f'WROTE: {p_md}')
    print(f'WROTE: {p_mat}')
    if p_plt: print(f'WROTE: {p_plt}')
    print('CONSOLIDATION_DONE')


if __name__ == '__main__':
    main()
