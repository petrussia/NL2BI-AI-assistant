"""run_dbt_ablation.py — V1 (baseline) vs V2 (better grounding) vs V4
(diff-form priority) ablation across N tasks. Each (task, variant) runs
in an isolated server workspace so variants don't contaminate each
other.

For each (task, variant):
  1. export task context (cached after first call per task)
  2. build prompt with the variant's builder
  3. inference via Colab bridge -> model_response_<variant>.txt
  4. apply to fresh server workspace per variant:
       outputs/colab_bridge/tasks/<task>__<variant>/workspace
  5. dbt deps + run + test
  6. official_eval
  7. collect metrics

Outputs:
  outputs/dbt_ablation/<run_id>/per_task.jsonl
  outputs/dbt_ablation/<run_id>/summary.csv
  outputs/dbt_ablation/<run_id>/readout.md
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'spider2_dbt_bridge'))
from ssh_utils import (
    load_config, ssh_run, scp_to_remote, scp_from_remote, ensure_remote_dir,
    local_task_path,
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_local(cmd: list[str], *, timeout: int = 300) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def _ensure_context(iid: str, cfg) -> bool:
    ctx = local_task_path(cfg, iid) / 'context' / 'context.json'
    if ctx.exists(): return True
    rc, _, err = _run_local([sys.executable,
                                str(REPO / 'spider2_dbt_bridge' / 'export_task_context.py'),
                                '--task-id', iid], timeout=600)
    return rc == 0


def _build_prompt(iid: str, variant: str) -> bool:
    rc, _, err = _run_local([sys.executable,
                                str(REPO / 'spider2_dbt_bridge' / 'build_model_prompt_v2.py'),
                                '--task-id', iid, '--variant', variant],
                                timeout=60)
    return rc == 0


def _inference(iid: str, variant: str, max_new: int = 1500) -> bool:
    rc, _, err = _run_local([sys.executable,
                                str(REPO / 'tools' / 'remote_scripts' / '_run_dbt_inference.py'),
                                iid, str(max_new), variant], timeout=600)
    return rc == 0


def _prepare_floor_workspace(cfg, iid: str) -> tuple[str, dict]:
    """v0_floor: just `cp -R` the upstream example into a per-task workspace.
    No prompt, no inference, no apply. Returns (workspace_path, manifest).
    """
    iid_var = f'{iid}__v0_floor'
    var_remote = f'{cfg.remote_workspace_root.rstrip("/")}/{iid_var}'
    var_workspace = f'{var_remote}/workspace'
    ensure_remote_dir(cfg, var_workspace)

    src_dir = f'{cfg.remote_spider2_dbt}/examples/{iid}'
    init_cmd = (
        f'rm -rf {shlex.quote(var_workspace)} && '
        f'mkdir -p {shlex.quote(var_workspace)} && '
        f'cp -RTu {shlex.quote(src_dir)} {shlex.quote(var_workspace)} && '
        f'rm -rf {shlex.quote(var_workspace)}/dbt_packages '
        f'        {shlex.quote(var_workspace)}/target '
        f'        {shlex.quote(var_workspace)}/logs'
    )
    r = ssh_run(cfg, init_cmd, timeout=120)
    if r.returncode != 0:
        return (var_workspace,
                {'error': f'workspace_init_failed: {r.stderr[:200]}'})
    return (var_workspace, {'kind': 'none', 'pushed': [],
                              'fenced_blocks': 0, 'response_chars': 0})


def _per_variant_apply(cfg, iid: str, variant: str) -> tuple[str, dict]:
    """Apply model_response_<variant>.txt to a per-variant workspace
    on the server. Returns (variant_workspace_remote, manifest_dict).
    """
    response_path = local_task_path(cfg, iid) / f'model_response_{variant}.txt'
    if not response_path.exists():
        return ('', {'error': f'no response file: {response_path}'})

    iid_var = f'{iid}__{variant}'
    var_remote = f'{cfg.remote_workspace_root.rstrip("/")}/{iid_var}'
    var_workspace = f'{var_remote}/workspace'
    var_incoming = f'{var_remote}/incoming'
    ensure_remote_dir(cfg, var_workspace)
    ensure_remote_dir(cfg, var_incoming)

    # Reset workspace as cp -R of upstream example
    src_dir = f'{cfg.remote_spider2_dbt}/examples/{iid}'
    init_cmd = (
        f'rm -rf {shlex.quote(var_workspace)} && '
        f'mkdir -p {shlex.quote(var_workspace)} && '
        f'cp -RTu {shlex.quote(src_dir)} {shlex.quote(var_workspace)} && '
        f'rm -rf {shlex.quote(var_workspace)}/dbt_packages '
        f'        {shlex.quote(var_workspace)}/target '
        f'        {shlex.quote(var_workspace)}/logs'
    )
    r = ssh_run(cfg, init_cmd, timeout=120)
    if r.returncode != 0:
        return (var_workspace,
                {'error': f'workspace_init_failed: {r.stderr[:200]}'})

    # Parse + apply (re-use apply_model_output logic via subprocess)
    # We need to swap predictions path; easiest: call apply with a wrapper
    # that overrides the response. We'll call a small inline parse here.
    text = response_path.read_text(encoding='utf-8')
    import re
    fence_re = re.compile(
        r'```(?P<lang>[A-Za-z]+)?\s*(?P<attrs>[^\n]*)?\n(?P<body>.*?)```',
        re.DOTALL)
    blocks = []
    for m in fence_re.finditer(text):
        attrs_kv = {}
        for kv in re.findall(r'(\w+)=([^\s]+)', (m.group('attrs') or '').strip()):
            attrs_kv[kv[0]] = kv[1]
        blocks.append({'lang': (m.group('lang') or '').lower(),
                         'body': m.group('body'),
                         'attrs': attrs_kv})

    sql_block = next((b for b in blocks
                        if b['lang'] in ('sql', '') and b['attrs'].get('path')), None)
    diff_block = next((b for b in blocks if b['lang'] == 'diff'), None)
    kind = 'none'; pushed = []
    if sql_block:
        path = sql_block['attrs']['path']
        if path.startswith('/') or '..' in Path(path).parts:
            return (var_workspace, {'error': f'unsafe_path:{path!r}'})
        local_tmp = local_task_path(cfg, iid) / f'_apply_{variant}.sql'
        local_tmp.write_text(sql_block['body'], encoding='utf-8')
        remote_path = f'{var_workspace}/{path}'
        ensure_remote_dir(cfg, f'{var_workspace}/{Path(path).parent.as_posix()}'
                                if '/' in path else var_workspace)
        cp = scp_to_remote(cfg, local_tmp, remote_path)
        if cp.returncode == 0:
            pushed.append(path); kind = 'sql_file'
    elif diff_block:
        local_tmp = local_task_path(cfg, iid) / f'_apply_{variant}.diff'
        local_tmp.write_text(diff_block['body'], encoding='utf-8')
        remote_diff = f'{var_workspace}/patch.diff'
        cp = scp_to_remote(cfg, local_tmp, remote_diff)
        if cp.returncode == 0:
            apply_cmd = (f'cd {shlex.quote(var_workspace)} && '
                          f'(git apply --whitespace=nowarn -p1 patch.diff || '
                          f'patch -p1 < patch.diff) 2>&1')
            r = ssh_run(cfg, apply_cmd, timeout=30)
            kind = 'diff'; pushed.append('patch.diff')
            return (var_workspace, {'kind': kind, 'pushed': pushed,
                                      'diff_apply_rc': r.returncode,
                                      'diff_apply_out': (r.stdout + r.stderr)[:300]})
    if kind == 'none':
        # Fallback: write whole response as models/output.sql
        local_tmp = local_task_path(cfg, iid) / f'_apply_{variant}.sql'
        local_tmp.write_text(text.strip(), encoding='utf-8')
        cp = scp_to_remote(cfg, local_tmp, f'{var_workspace}/models/output.sql')
        if cp.returncode == 0: pushed.append('models/output.sql'); kind = 'fallback_sql'

    return (var_workspace, {'kind': kind, 'pushed': pushed,
                              'fenced_blocks': len(blocks),
                              'response_chars': len(text)})


def _per_variant_eval(cfg, iid: str, variant: str, var_workspace: str) -> dict:
    iid_var = f'{iid}__{variant}'
    activate = 'source /home/denis/dbt/.venv/bin/activate'
    logs = f'{cfg.remote_workspace_root.rstrip("/")}/{iid_var}/logs'
    ensure_remote_dir(cfg, logs)
    cmd = (
        f'{activate} && cd {shlex.quote(var_workspace)} && '
        f'export DBT_PROFILES_DIR=$PWD && '
        f'(timeout 120 dbt deps  > {shlex.quote(logs)}/dbt_deps.log 2>&1; '
        f' echo DEPS=$?) && '
        f'(timeout 240 dbt run  > {shlex.quote(logs)}/dbt_run.log 2>&1; '
        f' echo RUN=$?) && '
        f'(timeout 240 dbt test > {shlex.quote(logs)}/dbt_test.log 2>&1; '
        f' echo TEST=$?)'
    )
    r = ssh_run(cfg, f'bash -lc {shlex.quote(cmd)}', timeout=720)
    rcs = {'dbt_deps_rc': None, 'dbt_run_rc': None, 'dbt_test_rc': None}
    for ln in r.stdout.splitlines():
        if ln.startswith('DEPS='): rcs['dbt_deps_rc'] = int(ln.split('=')[1])
        elif ln.startswith('RUN='): rcs['dbt_run_rc'] = int(ln.split('=')[1])
        elif ln.startswith('TEST='): rcs['dbt_test_rc'] = int(ln.split('=')[1])

    # Run dbt PASS/ERROR counts from log
    grep_pass_rc = ssh_run(cfg,
        f"grep -h 'PASS=\\|ERROR=' {shlex.quote(logs)}/dbt_test.log 2>/dev/null | tail -1",
        timeout=10)
    pass_n = err_n = 0
    for tok in grep_pass_rc.stdout.split():
        if tok.startswith('PASS='):
            try: pass_n = int(tok.split('=')[1])
            except Exception: pass
        elif tok.startswith('ERROR='):
            try: err_n = int(tok.split('=')[1])
            except Exception: pass

    # Official eval
    official = ssh_run(cfg,
        f'{activate} && /home/denis/dbt/.venv/bin/python '
        f'/home/denis/dbt/colab_bridge/server_official_eval.py '
        f'--task-id {shlex.quote(iid)} '
        f'--workspace {shlex.quote(var_workspace)}', timeout=600)
    score = None
    out_text = official.stdout or ''
    # Find LAST top-level JSON object — server prints `{ ... }` block
    try:
        last_open = out_text.rfind('\n{')
        last_close = out_text.rfind('\n}')
        if last_open >= 0 and last_close > last_open:
            data = json.loads(out_text[last_open:last_close+2])
            score = data.get('official_score')
    except Exception:
        pass
    if score is None:
        # fallback: regex `0.0 0 1`
        import re
        m = re.search(r'(\d+\.\d+)\s+(\d+)\s+(\d+)', out_text)
        if m:
            try: score = {'rate': float(m.group(1)),
                              'matched': int(m.group(2)),
                              'total': int(m.group(3))}
            except Exception: score = None

    return {
        **rcs, 'pass_n': pass_n, 'err_n': err_n,
        'official_score': score,
        'official_rc': official.returncode,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--tasks', nargs='+', required=True,
                     help='task ids to run, e.g. asana001 playbook001 retail001')
    ap.add_argument('--variants', nargs='+', default=['v1', 'v2', 'v4'],
                     choices=['v0_floor', 'v1', 'v2', 'v4'])
    ap.add_argument('--max-new', type=int, default=1500)
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--config', default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)

    run_id = args.run_id or f'ablation_{int(time.time())}'
    out_dir = REPO / 'outputs' / 'dbt_ablation' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'RUN_ID={run_id}  OUT={out_dir}')

    per_task = []
    for iid in args.tasks:
        print(f'\n========== TASK {iid} ==========')
        # v0_floor doesn't need context/prompt/inference; skip ensure_context
        # for variants that are pure floor.
        non_floor_variants = [v for v in args.variants if v != 'v0_floor']
        if non_floor_variants and not _ensure_context(iid, cfg):
            print(f'  SKIP {iid}: context failed'); continue

        for variant in args.variants:
            print(f'  --- {iid} | {variant} ---')
            t0 = time.time()

            if variant == 'v0_floor':
                # Pure floor: no inference, no prompt, no apply (just cp -R).
                ws, manifest = _prepare_floor_workspace(cfg, iid)
                if not ws or 'error' in manifest:
                    per_task.append({
                        'instance_id': iid, 'variant': variant,
                        'status': 'workspace_prep_failed',
                        'apply_kind': 'none', 'pushed_files': [],
                        'inference_used': False, 'prompt_used': False,
                        'fenced_blocks': 0, 'response_chars': 0,
                        'mode': 'submission_like_floor_no_gold_prompt',
                        **manifest,
                        'wall_time_s': round(time.time()-t0, 1)})
                    continue
                ev = _per_variant_eval(cfg, iid, variant, ws)
                row = {'instance_id': iid, 'variant': variant,
                        'status': 'done',
                        'apply_kind': 'none', 'pushed_files': [],
                        'inference_used': False, 'prompt_used': False,
                        'fenced_blocks': 0, 'response_chars': 0,
                        'mode': 'submission_like_floor_no_gold_prompt',
                        **ev,
                        'wall_time_s': round(time.time()-t0, 1)}
                per_task.append(row)
                print(f'    floor eval: dbt_run={ev.get("dbt_run_rc")} '
                      f'pass={ev.get("pass_n")}/err={ev.get("err_n")} '
                      f'score={ev.get("official_score")}')
                continue

            # Normal LLM-driven variant path
            ok_p = _build_prompt(iid, variant); print(f'    prompt: {ok_p}')
            ok_i = _inference(iid, variant, args.max_new) if ok_p else False
            print(f'    inference: {ok_i}')
            if not (ok_p and ok_i):
                per_task.append({'instance_id': iid, 'variant': variant,
                                  'status': 'inference_failed',
                                  'inference_used': bool(ok_i),
                                  'prompt_used': bool(ok_p),
                                  'wall_time_s': round(time.time()-t0,1)})
                continue
            ws, manifest = _per_variant_apply(cfg, iid, variant)
            print(f'    apply: kind={manifest.get("kind")} pushed={manifest.get("pushed")}')
            if not ws or 'error' in manifest:
                per_task.append({'instance_id': iid, 'variant': variant,
                                  'status': 'apply_failed', **manifest,
                                  'inference_used': True, 'prompt_used': True,
                                  'wall_time_s': round(time.time()-t0,1)})
                continue
            ev = _per_variant_eval(cfg, iid, variant, ws)
            row = {'instance_id': iid, 'variant': variant,
                    'status': 'done',
                    'apply_kind': manifest.get('kind'),
                    'pushed_files': manifest.get('pushed'),
                    'inference_used': True, 'prompt_used': True,
                    'fenced_blocks': manifest.get('fenced_blocks', 0),
                    'response_chars': manifest.get('response_chars', 0),
                    **ev,
                    'wall_time_s': round(time.time()-t0,1)}
            per_task.append(row)
            print(f'    eval: dbt_run={ev.get("dbt_run_rc")} '
                  f'pass={ev.get("pass_n")}/err={ev.get("err_n")} '
                  f'score={ev.get("official_score")}')

    # Save
    (out_dir / 'per_task.jsonl').write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in per_task) + '\n',
        encoding='utf-8')

    # Summary CSV
    import csv
    with (out_dir / 'summary.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['instance_id', 'variant', 'apply_kind',
                      'dbt_deps_rc', 'dbt_run_rc', 'dbt_test_rc',
                      'pass_n', 'err_n', 'score_rate', 'score_matched',
                      'score_total', 'wall_time_s'])
        for r in per_task:
            sc = r.get('official_score') or {}
            w.writerow([r.get('instance_id'), r.get('variant'),
                          r.get('apply_kind'),
                          r.get('dbt_deps_rc'), r.get('dbt_run_rc'),
                          r.get('dbt_test_rc'),
                          r.get('pass_n'), r.get('err_n'),
                          sc.get('rate'), sc.get('matched'),
                          sc.get('total'),
                          r.get('wall_time_s')])

    # Readout
    by_variant: dict = {v: {'n': 0, 'compile_ok': 0, 'score_match': 0,
                              'pass_total': 0, 'err_total': 0,
                              'wall_s_sum': 0.0}
                          for v in args.variants}
    for r in per_task:
        v = r.get('variant'); d = by_variant.get(v) or by_variant.setdefault(v, {})
        d['n'] = d.get('n', 0) + 1
        if r.get('dbt_run_rc') == 0: d['compile_ok'] = d.get('compile_ok', 0) + 1
        sc = r.get('official_score') or {}
        if (sc.get('matched') or 0) > 0: d['score_match'] = d.get('score_match', 0) + 1
        d['pass_total'] = d.get('pass_total', 0) + (r.get('pass_n') or 0)
        d['err_total'] = d.get('err_total', 0) + (r.get('err_n') or 0)
        d['wall_s_sum'] = d.get('wall_s_sum', 0.0) + (r.get('wall_time_s') or 0)

    md = ['# DBT ablation — V1 vs V2 vs V4', '',
            f'_Run: {run_id}, generated {utcnow()}_', '',
            '## Per-variant aggregates', '',
            '| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |',
            '|---|---:|---:|---:|---:|---:|---:|']
    for v in args.variants:
        d = by_variant.get(v) or {}
        n = d.get('n', 0)
        md.append(f'| {v} | {n} | {d.get("compile_ok",0)}/{n} | '
                  f'{d.get("score_match",0)}/{n} | '
                  f'{d.get("pass_total",0)} | {d.get("err_total",0)} | '
                  f'{d.get("wall_s_sum", 0)/max(1,n):.1f} |')
    md += ['',
            '## Per-task',
            '',
            '| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |',
            '|---|---|---:|---|---|---|---:|']
    for r in per_task:
        sc = r.get('official_score') or {}
        sc_str = (f'{sc.get("matched","-")}/{sc.get("total","-")} '
                    f'(rate={sc.get("rate","-")})')
        md.append(f'| {r.get("instance_id")} | {r.get("variant")} | '
                  f'{r.get("dbt_run_rc")} | {r.get("pass_n",0)}/{r.get("err_n",0)} | '
                  f'{sc_str} | {r.get("apply_kind","-")} | {r.get("wall_time_s","-")} |')
    (out_dir / 'readout.md').write_text('\n'.join(md), encoding='utf-8')
    print(f'\nWROTE {out_dir / "per_task.jsonl"}')
    print(f'WROTE {out_dir / "summary.csv"}')
    print(f'WROTE {out_dir / "readout.md"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
