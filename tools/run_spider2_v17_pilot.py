"""run_spider2_v17_pilot.py — model-swap launcher reusing v16 runners.

Why a single new tool: v16 BQ+Snow runners (lite_bq_v16_colab_runner.py,
spider2_snow_v16_colab_runner.py) hardcode `Qwen/Qwen2.5-Coder-7B-Instruct`
in their `_ensure_model()`. v17 doesn't change validator / mapper /
nested-rewrite / repair logic at all — it only swaps the generator via
`model_registry_v17`.

Usage:
  python tools/run_spider2_v17_pilot.py --lane bq   --model qwen3_coder_30b_bf16 --limit 10
  python tools/run_spider2_v17_pilot.py --lane snow --model mistral_small_32_24b_bnb4 --limit 10

Aliases: see `repo/src/evaluation/model_registry_v17.py`.

The launcher patches the v16 template at runtime: it replaces the
`_ensure_model` body so that the model is loaded via
`model_registry_v17.load_model_and_tokenizer(alias)`. Everything else
in v16 (catalog, validator, constrained repair, BQ nested rewrite,
async batch pattern, write-probe) is preserved.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
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


def _patch_model_loader(template: str, alias: str) -> str:
    """Replace v16 _ensure_model with a v17 registry-based loader.
    The replacement imports model_registry_v17 from Drive (must be
    uploaded once before first run via the upload helper).
    """
    new_ensure = (
        'def _ensure_model():\n'
        '    g = globals()\n'
        '    if g.get("_GEN_READY"): return\n'
        f'    _MODEL_ALIAS = {alias!r}\n'
        '    print(f"LOADING_MODEL alias={_MODEL_ALIAS}", flush=True)\n'
        '    import sys\n'
        '    REG_DIR = "/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation"\n'
        '    if REG_DIR not in sys.path: sys.path.insert(0, REG_DIR)\n'
        '    from model_registry_v17 import load_model_and_tokenizer\n'
        '    tok, mdl, prof = load_model_and_tokenizer(_MODEL_ALIAS)\n'
        '    g["_TOK"] = tok; g["_MDL"] = mdl; g["_GEN_READY"] = True\n'
        '    g["_MODEL_ALIAS"] = _MODEL_ALIAS\n'
        '    g["_MODEL_PROFILE"] = {\n'
        '        "alias": prof.alias, "hf_id": prof.hf_id,\n'
        '        "non_thinking_mode": prof.non_thinking_mode,\n'
        '        "max_new_tokens_default": prof.max_new_tokens_default,\n'
        '    }\n'
        '    print(f"MODEL_READY {prof.hf_id}", flush=True)\n'
    )

    # Also rewrite _gen() to honor non_thinking_mode via chat_generate
    new_gen = (
        'def _gen(prompt, max_new=800):\n'
        '    g = globals(); import torch\n'
        '    nt = bool(g.get("_MODEL_PROFILE", {}).get("non_thinking_mode", False))\n'
        '    msgs = [{"role": "user", "content": prompt}]\n'
        '    extra = {"enable_thinking": False} if nt else {}\n'
        '    try:\n'
        '        enc = g["_TOK"].apply_chat_template(\n'
        '            msgs, return_tensors="pt", add_generation_prompt=True,\n'
        '            return_dict=True, **extra)\n'
        '    except TypeError:\n'
        '        enc = g["_TOK"].apply_chat_template(\n'
        '            msgs, return_tensors="pt", add_generation_prompt=True,\n'
        '            return_dict=True)\n'
        '    enc = {k: v.to(g["_MDL"].device) for k, v in enc.items()}\n'
        '    with torch.no_grad():\n'
        '        out = g["_MDL"].generate(**enc, max_new_tokens=max_new,\n'
        '                                    do_sample=False, temperature=0.0,\n'
        '                                    pad_token_id=g["_TOK"].eos_token_id)\n'
        '    gen = out[0][enc["input_ids"].shape[1]:]\n'
        '    return g["_TOK"].decode(gen, skip_special_tokens=True)\n'
    )

    # Replace the existing _ensure_model and _gen function bodies
    # The v16 _ensure_model starts at "def _ensure_model():" and ends at the
    # next top-level "def " in the template string. Same for _gen.
    def _replace_block(src: str, fn_name: str, new_block: str) -> str:
        pat = re.compile(rf'def {fn_name}\([^)]*\):\n(?:    .+\n)+',
                          re.MULTILINE)
        m = pat.search(src)
        if not m:
            raise RuntimeError(f'function {fn_name} not found in template')
        # match greedy until next top-level def/class or unindented line
        # The simple regex matches indented body lines only; that's enough
        return src[:m.start()] + new_block + src[m.end():]

    out = _replace_block(template, '_ensure_model', new_ensure)
    out = _replace_block(out, '_gen', new_gen)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--lane', choices=['bq', 'snow'], required=True)
    ap.add_argument('--model', required=True,
                     help='alias from repo/src/evaluation/model_registry_v17.py')
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--max-rows', type=int, default=100)
    ap.add_argument('--cap-bytes-billed', type=int, default=1*1024**3)
    ap.add_argument('--no-execute', action='store_true')
    args = ap.parse_args()

    run_id = args.run_id or f'{args.lane}_v17_{args.model}_pilot{args.limit}_{int(time.time())}'

    # Pick v16 runner template
    if args.lane == 'bq':
        runner_path = REPO / 'repo' / 'src' / 'evaluation' / 'spider2_lite_bq_v16_colab_runner.py'
        bg_fn = 'start_v16_bq_bg'
        status_fn = 'v16_bq_status'
        bg_call_kwargs = (f'limit={args.limit!r}, run_id={run_id!r}, '
                            f'max_rows={args.max_rows!r}, '
                            f'cap_bytes_billed={args.cap_bytes_billed!r}, '
                            f'no_execute={args.no_execute!r}')
        local_runs_dir = REPO / 'outputs' / 'spider2_lite' / 'runs' / run_id
        canon_prefix = 'spider2_lite_bq_v17'
    else:  # snow
        runner_path = REPO / 'repo' / 'src' / 'evaluation' / 'spider2_snow_v16_colab_runner.py'
        bg_fn = 'start_v16_snow_bg'
        status_fn = 'v16_snow_status'
        bg_call_kwargs = (f'limit={args.limit!r}, run_id={run_id!r}, '
                            f'max_rows={args.max_rows!r}, '
                            f'no_execute={args.no_execute!r}')
        local_runs_dir = REPO / 'outputs' / 'spider2_snow' / 'runs' / run_id
        canon_prefix = 'spider2_snow_v17'

    runner_src = runner_path.read_text(encoding='utf-8')
    namespace: dict = {}
    exec(compile(runner_src, str(runner_path), 'exec'), namespace)
    template = namespace['_self_contained_runner_template']()

    # Inject v17 model loader
    template = _patch_model_loader(template, args.model)

    invocation = (
        f'\nresult = {bg_fn}({bg_call_kwargs})\n'
        'import json as _j\nprint("===STARTED===")\nprint(_j.dumps(result))\nprint("===STARTED_END===")\n'
    )

    print(f'Kicking off {args.lane} v17 pilot in BG  model={args.model}  '
          f'limit={args.limit}  run_id={run_id}')
    t0 = time.time()
    try:
        r = bridge_exec(template + invocation, timeout=60)
    except Exception as exc:
        print(f'BRIDGE_EXC: {type(exc).__name__}: {exc}'); return 2

    out = r.get('stdout') or ''
    started = None
    if '===STARTED===' in out and '===STARTED_END===' in out:
        try:
            started = json.loads(out.split('===STARTED===\n', 1)[1]
                                       .split('\n===STARTED_END===', 1)[0])
        except Exception: started = None
    if not started:
        print(f'NO_START; tail:\n{out[-2000:]}'); return 2
    print(f'  started: {started}')
    out_dir_drive = started['out_dir']

    poll_code = (f'import json as _j\n_st = {status_fn}({run_id!r})\n'
                  f'print("===STATUS===")\nprint(_j.dumps(_st))\nprint("===STATUS_END===")\n')
    last_n = -1
    state = None
    print('\nPolling Drive every 30s ...')
    for poll_i in range(360):
        time.sleep(30)
        try:
            r2 = bridge_exec(template + poll_code, timeout=30)
        except Exception as exc:
            print(f'  poll_err: {type(exc).__name__}'); continue
        out2 = r2.get('stdout') or ''
        if '===STATUS===' in out2 and '===STATUS_END===' in out2:
            try:
                state = json.loads(out2.split('===STATUS===\n', 1)[1]
                                          .split('\n===STATUS_END===', 1)[0])
            except Exception: state = None
        if not state: continue
        n = state.get('n_predictions', 0)
        if n != last_n or poll_i % 5 == 0:
            elapsed = int(time.time() - t0)
            print(f'  [{elapsed:5}s] preds={n} done={state.get("done")} '
                  f'failed={state.get("failed")}')
            last_n = n
        if state.get('done') or state.get('failed'): break
    wall = time.time() - t0

    if not state or not state.get('done'):
        print(f'\nNOT DONE after {wall:.1f}s; state: {state}')
        if state and state.get('failed'):
            print(f'  failure: {state.get("failure")}')
        return 1

    summary = state.get('summary')
    print(f'\nSUMMARY: {summary}')
    print(f'WALL: {wall:.1f}s')

    # Pull artifacts
    local_runs_dir.mkdir(parents=True, exist_ok=True)
    pull_code = ('import os, base64, json\n'
                 f'D = {out_dir_drive!r}\nfiles={{}}\n'
                 'for f in sorted(os.listdir(D)):\n'
                 '    p = os.path.join(D, f)\n'
                 '    if os.path.isfile(p):\n'
                 '        with open(p, "rb") as fh:\n'
                 '            files[f] = base64.b64encode(fh.read()).decode()\n'
                 'print("===FILES_START===")\nprint(json.dumps(files))\nprint("===FILES_END===")\n')
    try:
        r3 = bridge_exec(pull_code, timeout=120)
        out3 = r3.get('stdout') or ''
        if '===FILES_START===' in out3 and '===FILES_END===' in out3:
            files_b64 = json.loads(out3.split('===FILES_START===\n', 1)[1]
                                          .split('\n===FILES_END===', 1)[0])
            for fname, b64 in files_b64.items():
                (local_runs_dir / fname).write_bytes(base64.b64decode(b64))
            print(f'  pulled {len(files_b64)} files to {local_runs_dir.relative_to(REPO).as_posix()}')
            pred = local_runs_dir / 'predictions.jsonl'
            if pred.exists():
                canon = REPO / 'outputs' / 'predictions' / f'{canon_prefix}_{run_id}_predictions.jsonl'
                canon.parent.mkdir(parents=True, exist_ok=True)
                canon.write_bytes(pred.read_bytes())
                print(f'  canonical: {canon.relative_to(REPO).as_posix()}')
    except Exception as exc:
        print(f'pull_err: {type(exc).__name__}: {exc}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
