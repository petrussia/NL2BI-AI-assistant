"""analyze_v18_pilot.py — post-hoc analysis of a v18 pilot run.

Reads metrics + readout from a v18 run dir and emits the master matrices
the brief asks for in STEP 10:
  - outputs/tables/spider2_full_master_matrix_v18.csv (single row per run)
  - outputs/tables/spider2_full_master_matrix_v18.md
  - outputs/tables/spider2_full_lane_breakdown_v18.csv
  - outputs/tables/spider2_full_error_taxonomy_v18.csv
  - outputs/tables/spider2_model_role_comparison_v18.csv (A vs B per task)
  - outputs/tables/spider2_full_cost_runtime_v18.csv (placeholder if no
    cost data captured in traces yet)

Idempotent. Reads:
  outputs/spider2_lite/runs/<run_id>/{metrics,readout,traces,error_taxonomy,schema_linking_recall}.csv|md|jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def write_master_matrix(run_dir: Path, lane: str, run_id: str, model_planner: str,
                          model_emitter: str) -> None:
    metrics_p = run_dir / 'metrics.csv'
    rows = []
    if metrics_p.is_file():
        with metrics_p.open() as fh:
            for ln in fh:
                if ',' not in ln: continue
                k, v = ln.strip().split(',', 1)
                rows.append((k, v))
    metrics = dict(rows)

    out_csv = REPO / 'outputs' / 'tables' / 'spider2_full_master_matrix_v18.csv'
    out_md = REPO / 'outputs' / 'tables' / 'spider2_full_master_matrix_v18.md'
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['run_id', 'lane', 'planner', 'emitter',
                     'n', 'plan_validation_ok', 'chosen_schema_valid',
                     'parse_ok', 'execute_ok',
                     'chosen_family_A', 'chosen_family_B'])
        w.writerow([run_id, lane, model_planner, model_emitter,
                     metrics.get('n', '0'),
                     metrics.get('plan_validation_ok', '0'),
                     metrics.get('chosen_schema_valid', '0'),
                     metrics.get('parse_ok', '0'),
                     metrics.get('execute_ok', '0'),
                     metrics.get('chosen_family_A', '0'),
                     metrics.get('chosen_family_B', '0')])

    with out_md.open('w', encoding='utf-8') as fh:
        fh.write('# Spider2 v18 master matrix\n\n')
        fh.write('| run_id | lane | planner | emitter | n | plan_ok | sv | parse | exec | A | B |\n')
        fh.write('|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n')
        fh.write(f'| {run_id} | {lane} | {model_planner} | {model_emitter} | '
                  f'{metrics.get("n","0")} | {metrics.get("plan_validation_ok","0")} | '
                  f'{metrics.get("chosen_schema_valid","0")} | '
                  f'{metrics.get("parse_ok","0")} | {metrics.get("execute_ok","0")} | '
                  f'{metrics.get("chosen_family_A","0")} | {metrics.get("chosen_family_B","0")} |\n')


def write_role_comparison(run_dir: Path, run_id: str) -> None:
    traces_p = run_dir / 'traces.jsonl'
    out_csv = REPO / 'outputs' / 'tables' / 'spider2_model_role_comparison_v18.csv'
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['run_id', 'instance_id',
                     'family_A_parse_ok', 'family_A_schema_valid', 'family_A_dry_run_ok',
                     'family_B_parse_ok', 'family_B_schema_valid', 'family_B_dry_run_ok',
                     'plan_valid', 'chosen_family'])
        if not traces_p.is_file():
            return
        with traces_p.open(encoding='utf-8') as ifh:
            for ln in ifh:
                t = json.loads(ln)
                evals = t.get('evals') or []
                a = next((e for e in evals if e.get('family') == 'A'), {})
                b = next((e for e in evals if e.get('family') == 'B'), {})
                w.writerow([run_id, t.get('instance_id', ''),
                             int(bool(a.get('parse_ok'))), int(bool(a.get('schema_valid'))),
                             int(bool(a.get('dry_run_ok'))),
                             int(bool(b.get('parse_ok'))), int(bool(b.get('schema_valid'))),
                             int(bool(b.get('dry_run_ok'))),
                             int(bool(t.get('plan_validation_ok'))),
                             t.get('chosen_family', '?')])


def write_lane_breakdown_and_taxonomy(run_dir: Path, run_id: str, lane: str) -> None:
    out_lane = REPO / 'outputs' / 'tables' / 'spider2_full_lane_breakdown_v18.csv'
    out_lane.parent.mkdir(parents=True, exist_ok=True)
    metrics_p = run_dir / 'metrics.csv'
    rows = {}
    if metrics_p.is_file():
        with metrics_p.open() as fh:
            for ln in fh:
                if ',' not in ln: continue
                k, v = ln.strip().split(',', 1)
                rows[k] = v
    with out_lane.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['lane', 'run_id', 'n', 'sv', 'parse', 'exec'])
        w.writerow([lane, run_id,
                     rows.get('n', '0'),
                     rows.get('chosen_schema_valid', '0'),
                     rows.get('parse_ok', '0'),
                     rows.get('execute_ok', '0')])

    err_in = run_dir / 'error_taxonomy.csv'
    out_err = REPO / 'outputs' / 'tables' / 'spider2_full_error_taxonomy_v18.csv'
    if err_in.is_file():
        with err_in.open() as ifh, out_err.open('w', newline='', encoding='utf-8') as ofh:
            w = csv.writer(ofh)
            w.writerow(['lane', 'run_id', 'error_class', 'count'])
            r = csv.reader(ifh)
            header = next(r)
            for row in r:
                w.writerow([lane, run_id] + row)


def write_cost_runtime(run_dir: Path, run_id: str, lane: str) -> None:
    """Best-effort cost+runtime — for v18.0 we only have the run's wall
    timestamp; bytes_billed needs to be captured per-task to be useful.
    Emit a placeholder that captures the run_id and the start/end
    markers."""
    out_cost = REPO / 'outputs' / 'tables' / 'spider2_full_cost_runtime_v18.csv'
    out_cost.parent.mkdir(parents=True, exist_ok=True)
    started = run_dir / '_STARTED'
    done = run_dir / '_DONE'
    started_ts = json.loads(started.read_text())['ts'] if started.is_file() else 0.0
    done_ts = json.loads(done.read_text())['ts'] if done.is_file() else 0.0
    wall = (done_ts - started_ts) if done_ts and started_ts else 0.0
    with out_cost.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['run_id', 'lane', 'wall_seconds', 'cost_usd_estimate'])
        w.writerow([run_id, lane, f'{wall:.1f}', '0 (dry_run only)'])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--lane', default='bq')
    ap.add_argument('--planner', default='qwen3_coder_30b_bf16')
    ap.add_argument('--emitter', default='qwen2_5_coder_7b')
    a = ap.parse_args()
    run_dir = REPO / 'outputs' / a.lane.replace('snow', 'spider2_snow').replace('bq', 'spider2_lite') / 'runs' / a.run_id
    if not run_dir.is_dir():
        # try direct path
        run_dir = REPO / 'outputs' / 'spider2_lite' / 'runs' / a.run_id
    if not run_dir.is_dir():
        print(f'run dir not found: {run_dir}'); return 2

    write_master_matrix(run_dir, a.lane, a.run_id, a.planner, a.emitter)
    write_role_comparison(run_dir, a.run_id)
    write_lane_breakdown_and_taxonomy(run_dir, a.run_id, a.lane)
    write_cost_runtime(run_dir, a.run_id, a.lane)
    print('analysis tables written under outputs/tables/')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
