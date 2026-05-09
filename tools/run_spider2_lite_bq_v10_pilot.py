"""run_spider2_lite_bq_v10_pilot.py — local launcher for the Colab-side BQ pilot.

Sends the v10 Colab-side runner as ONE /exec call. The Colab kernel does
all per-task work inline (no Cloudflare-tunnel wave). Local side just
fires the call and pulls back artifacts.

Usage:
    python tools/run_spider2_lite_bq_v10_pilot.py --limit 10
    python tools/run_spider2_lite_bq_v10_pilot.py --limit 30 --run-id lite_bq_v10_pilot30
    python tools/run_spider2_lite_bq_v10_pilot.py --limit 0 --run-id lite_bq_v10_FULL_205   # FULL
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'repo' / 'src' / 'evaluation'))

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def bridge_url() -> str:
    return (REPO / 'tools' / '.bridge_url').read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code: str, timeout: int = 1800) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=10, help='0 = FULL (all bq* tasks)')
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--max-repair-rounds', type=int, default=1)
    ap.add_argument('--max-rows', type=int, default=100,
                     help='LIMIT the result set we materialize from BQ.')
    ap.add_argument('--cap-bytes-billed', type=int, default=1 * 1024 ** 3,
                     help='Per-query bytes-billed cap (default 1 GiB).')
    ap.add_argument('--timeout', type=int, default=1800,
                     help='HTTP timeout for the single /exec call (s).')
    args = ap.parse_args()

    run_id = args.run_id or f'lite_bq_v10_pilot{args.limit}_{int(time.time())}'

    # Compose the Colab-side script: runner template + run_pilot(...) call
    runner_path = REPO / 'repo' / 'src' / 'evaluation' / 'spider2_lite_bq_v10_colab_runner.py'
    runner_src = runner_path.read_text(encoding='utf-8')
    # The runner module exposes _self_contained_runner_template(); we need
    # to extract the inner string.
    # Simpler: import + invoke locally to obtain the template.
    namespace: dict = {}
    exec(compile(runner_src, str(runner_path), 'exec'), namespace)
    template = namespace['_self_contained_runner_template']()

    # Cloudflare quick-tunnel has ~100s edge timeout. Long synchronous
    # /exec calls fail with HTTP 524. Use start_pilot_bg + polling.
    invocation = (
        f'\nresult = start_pilot_bg(limit={args.limit!r},'
        f' run_id={run_id!r},'
        f' max_repair_rounds={args.max_repair_rounds!r},'
        f' max_rows={args.max_rows!r},'
        f' cap_bytes_billed={args.cap_bytes_billed!r})\n'
        'import json as _json\n'
        'print("===PILOT_RESULT===")\n'
        'print(_json.dumps(result))\n'
        'print("===PILOT_END===")\n'
    )
    full_code = template + invocation

    print(f'Kicking off Colab-side pilot in BG thread (limit={args.limit}, run_id={run_id})')
    t0 = time.time()
    try:
        r = bridge_exec(full_code, timeout=60)
    except Exception as exc:
        print(f'BRIDGE_EXC starting pilot: {type(exc).__name__}: {exc}')
        return 2

    out = (r.get('stdout') or '')
    summary = None
    if '===PILOT_RESULT===' in out and '===PILOT_END===' in out:
        try:
            summary = json.loads(out.split('===PILOT_RESULT===\n', 1)[1]
                                       .split('\n===PILOT_END===', 1)[0])
        except Exception:
            summary = None
    if not summary:
        print(f'NO_START_RESULT; tail:\n{out[-1000:]}')
        return 2
    print(f'  started: {summary}')

    # Poll loop
    print(f'\nPolling Drive for progress every 30s ...')
    poll_code = (
        f'import json as _json\n'
        f'_st = pilot_status({run_id!r})\n'
        f'print("===STATUS===")\n'
        f'print(_json.dumps(_st))\n'
        f'print("===STATUS_END===")\n'
    )
    last_n = -1
    poll_interval = 30
    expected_n = args.limit if args.limit > 0 else 999  # FULL upper bound is ~205 for BQ lane
    max_polls = 240  # 240 * 30s = 2 hours
    state = None
    for poll_i in range(max_polls):
        time.sleep(poll_interval)
        try:
            r2 = bridge_exec(template + poll_code, timeout=30)
        except Exception as exc:
            print(f'  poll_err: {type(exc).__name__}: {exc}; will retry')
            continue
        out2 = r2.get('stdout') or ''
        if '===STATUS===' in out2 and '===STATUS_END===' in out2:
            try:
                state = json.loads(out2.split('===STATUS===\n', 1)[1]
                                          .split('\n===STATUS_END===', 1)[0])
            except Exception:
                state = None
        if not state:
            print(f'  poll {poll_i}: no state parsed')
            continue
        n = state.get('n_predictions', 0)
        if n != last_n or poll_i % 5 == 0:
            elapsed = int(time.time() - t0)
            print(f'  [{elapsed:5}s] preds={n} done={state.get("done")} '
                  f'failed={state.get("failed")}')
            last_n = n
        if state.get('done') or state.get('failed'):
            break
    wall = time.time() - t0

    if not state or not state.get('done'):
        print(f'\nNOT DONE after {wall:.1f}s; last state: {state}')
        if state and state.get('failed'):
            print(f'  failure: {state.get("failure")}')
        return 1

    summary = state.get('summary') or summary
    print(f'\n--- Final summary (Drive _DONE marker) ---')
    if summary:
        print(f'SUMMARY: {summary}')
        # Pull artifacts from Drive to local outputs/
        out_dir_drive = summary['out_dir']
        local_out_dir = REPO / 'outputs' / 'spider2_lite' / 'runs' / summary['run_id']
        local_out_dir.mkdir(parents=True, exist_ok=True)
        print(f'\nPulling artifacts from {out_dir_drive} -> {local_out_dir} ...')
        # Inline pull via /exec
        pull_code = (
            'import os, base64, json\n'
            f'D = {out_dir_drive!r}\n'
            'files = {}\n'
            'for f in sorted(os.listdir(D)):\n'
            '    p = os.path.join(D, f)\n'
            '    if os.path.isfile(p):\n'
            '        with open(p, "rb") as fh:\n'
            '            files[f] = base64.b64encode(fh.read()).decode()\n'
            'print("===FILES_START===")\n'
            'print(json.dumps(files))\n'
            'print("===FILES_END===")\n'
        )
        try:
            r2 = bridge_exec(pull_code, timeout=120)
            out2 = r2.get('stdout') or ''
            if '===FILES_START===' in out2 and '===FILES_END===' in out2:
                files_b64 = json.loads(out2.split('===FILES_START===\n', 1)[1]
                                              .split('\n===FILES_END===', 1)[0])
                for fname, b64 in files_b64.items():
                    (local_out_dir / fname).write_bytes(base64.b64decode(b64))
                print(f'  pulled {len(files_b64)} file(s) to {local_out_dir.relative_to(REPO).as_posix()}')
                # Also mirror predictions to canonical
                pred = local_out_dir / 'predictions.jsonl'
                if pred.exists():
                    canon = REPO / 'outputs' / 'predictions' / f'spider2_lite_bq_v10_{summary["run_id"]}_predictions.jsonl'
                    canon.parent.mkdir(parents=True, exist_ok=True)
                    canon.write_bytes(pred.read_bytes())
                    print(f'  canonical predictions: {canon.relative_to(REPO).as_posix()}')
        except Exception as exc:
            print(f'pull_artifact_err: {type(exc).__name__}: {exc}')
    else:
        print('NO_SUMMARY_PARSED')

    return 0 if summary else 1


if __name__ == '__main__':
    sys.exit(main())
