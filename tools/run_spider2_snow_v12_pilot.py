"""run_spider2_snow_v12_pilot.py — local launcher for Snow v12 pilot."""
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


def bridge_exec(code: str, timeout: int = 90) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--max-rows', type=int, default=100)
    ap.add_argument('--no-execute', action='store_true')
    args = ap.parse_args()

    run_id = args.run_id or f'snow_v12_pilot{args.limit}_{int(time.time())}'

    runner_path = REPO / 'repo' / 'src' / 'evaluation' / 'spider2_snow_v12_colab_runner.py'
    runner_src = runner_path.read_text(encoding='utf-8')
    namespace: dict = {}
    exec(compile(runner_src, str(runner_path), 'exec'), namespace)
    template = namespace['_self_contained_runner_template']()

    invocation = (
        f'\nresult = start_v12_bg(limit={args.limit!r},'
        f' run_id={run_id!r},'
        f' max_rows={args.max_rows!r},'
        f' no_execute={args.no_execute!r})\n'
        'import json as _json\n'
        'print("===STARTED===")\n'
        'print(_json.dumps(result))\n'
        'print("===STARTED_END===")\n'
    )

    print(f'Kicking off Snow v12 pilot in BG thread (limit={args.limit}, run_id={run_id})')
    t0 = time.time()
    try:
        r = bridge_exec(template + invocation, timeout=60)
    except Exception as exc:
        print(f'BRIDGE_EXC: {type(exc).__name__}: {exc}'); return 2

    out = (r.get('stdout') or '')
    started = None
    if '===STARTED===' in out and '===STARTED_END===' in out:
        try:
            started = json.loads(out.split('===STARTED===\n', 1)[1]
                                       .split('\n===STARTED_END===', 1)[0])
        except Exception:
            started = None
    if not started:
        print(f'NO_START_RESULT; tail:\n{out[-1000:]}')
        return 2
    print(f'  started: {started}')
    out_dir_drive = started['out_dir']

    poll_code = (
        f'import json as _json\n'
        f'_st = v12_status({run_id!r})\n'
        f'print("===STATUS===")\n'
        f'print(_json.dumps(_st))\n'
        f'print("===STATUS_END===")\n'
    )
    last_n = -1
    state = None
    print(f'\nPolling Drive every 30s ...')
    for poll_i in range(360):
        time.sleep(30)
        try:
            r2 = bridge_exec(template + poll_code, timeout=30)
        except Exception as exc:
            print(f'  poll_err: {type(exc).__name__}: {exc}; retry')
            continue
        out2 = r2.get('stdout') or ''
        if '===STATUS===' in out2 and '===STATUS_END===' in out2:
            try:
                state = json.loads(out2.split('===STATUS===\n', 1)[1]
                                          .split('\n===STATUS_END===', 1)[0])
            except Exception:
                state = None
        if not state:
            print(f'  poll {poll_i}: no state'); continue
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

    summary = state.get('summary')
    print(f'\nSUMMARY: {summary}')

    # Pull artifacts
    local_out_dir = REPO / 'outputs' / 'spider2_snow' / 'runs' / run_id
    local_out_dir.mkdir(parents=True, exist_ok=True)
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
        r3 = bridge_exec(pull_code, timeout=120)
        out3 = r3.get('stdout') or ''
        if '===FILES_START===' in out3 and '===FILES_END===' in out3:
            files_b64 = json.loads(out3.split('===FILES_START===\n', 1)[1]
                                          .split('\n===FILES_END===', 1)[0])
            for fname, b64 in files_b64.items():
                (local_out_dir / fname).write_bytes(base64.b64decode(b64))
            print(f'  pulled {len(files_b64)} file(s) to {local_out_dir.relative_to(REPO).as_posix()}')
            pred = local_out_dir / 'predictions.jsonl'
            if pred.exists():
                canon = REPO / 'outputs' / 'predictions' / f'spider2_snow_v12_{run_id}_predictions.jsonl'
                canon.parent.mkdir(parents=True, exist_ok=True)
                canon.write_bytes(pred.read_bytes())
                print(f'  canonical: {canon.relative_to(REPO).as_posix()}')
    except Exception as exc:
        print(f'pull_err: {type(exc).__name__}: {exc}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
