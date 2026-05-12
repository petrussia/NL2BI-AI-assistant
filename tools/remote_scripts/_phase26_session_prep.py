"""Phase 26 — uniform per-session prep on bridge kernel.

Loads HF_TOKEN from <PROJECT_ROOT>/secrets/HF_TOKEN.json, sets Snow env
from <PROJECT_ROOT>/secrets/snowflake.json, loads planner+emitter
models, writes a Drive marker `<PROJECT_ROOT>/outputs/runtime/<session_tag>_READY`.

The session_tag is read from the SESSION_TAG global (set by 00_SESSION_CONFIG)
or defaults to '' (session 1).

Idempotent. Safe to re-run.
"""
import os, sys, json, time
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
EVAL = DRV / 'repo/src/evaluation'
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

g = globals()
session_tag = g.get('SESSION_TAG', '') or ''
print(f'PHASE26_PREP session_tag={session_tag!r}')

# 1) HF_TOKEN
if not os.environ.get('HF_TOKEN'):
    p = DRV / 'secrets' / 'HF_TOKEN.json'
    if p.is_file():
        try:
            t = json.loads(p.read_text(encoding='utf-8')).get('HF_TOKEN')
            if t:
                os.environ['HF_TOKEN'] = t
                print(f'HF_TOKEN loaded from {p}')
        except Exception as e:
            print(f'HF_TOKEN load fail: {type(e).__name__}: {e}')
print(f'HF_TOKEN_SET: {bool(os.environ.get("HF_TOKEN"))}')

# 2) Snow env
sf_path = DRV / 'secrets' / 'snowflake.json'
if sf_path.is_file():
    try:
        sf = json.loads(sf_path.read_text(encoding='utf-8'))
        for k_in, k_env in [('account','SNOWFLAKE_ACCOUNT'),('user','SNOWFLAKE_USER'),
                                 ('password','SNOWFLAKE_PASSWORD'),('role','SNOWFLAKE_ROLE'),
                                 ('warehouse','SNOWFLAKE_WAREHOUSE'),('database','SNOWFLAKE_DATABASE')]:
            v = sf.get(k_in)
            if v: os.environ[k_env] = str(v)
        print(f'Snow env set: {[k for k in ["SNOWFLAKE_USER","SNOWFLAKE_ACCOUNT","SNOWFLAKE_ROLE","SNOWFLAKE_WAREHOUSE"] if os.environ.get(k)]}')
    except Exception as e:
        print(f'Snow env load fail: {type(e).__name__}: {e}')

# 3) Models
if g.get('_V18_MODELS_READY'):
    print('MODELS_ALREADY_READY')
else:
    import importlib
    if 'model_registry_v17' in sys.modules:
        importlib.reload(sys.modules['model_registry_v17'])
    from model_registry_v17 import load_model_and_tokenizer
    EMIT_ALIAS = 'qwen2_5_coder_7b'
    PLAN_ALIAS = 'qwen3_coder_30b_bf16'
    t0 = time.time()
    print(f'LOAD_EMITTER {EMIT_ALIAS} ...', flush=True)
    tok_b, mdl_b, prof_b = load_model_and_tokenizer(EMIT_ALIAS)
    g['_TOK_EMIT'] = tok_b; g['_MDL_EMIT'] = mdl_b; g['_PROF_EMIT'] = prof_b
    print(f'EMITTER_LOADED in {time.time()-t0:.1f}s', flush=True)
    t1 = time.time()
    print(f'LOAD_PLANNER {PLAN_ALIAS} ...', flush=True)
    tok_a, mdl_a, prof_a = load_model_and_tokenizer(PLAN_ALIAS)
    g['_TOK_PLAN'] = tok_a; g['_MDL_PLAN'] = mdl_a; g['_PROF_PLAN'] = prof_a
    print(f'PLANNER_LOADED in {time.time()-t1:.1f}s', flush=True)
    g['_V18_MODELS_READY'] = True

import torch
free, total = torch.cuda.mem_get_info()
print(f'VRAM: free={free/1024**3:.1f}/{total/1024**3:.1f} GB '
        f'alloc={torch.cuda.memory_allocated()/1024**3:.1f} GB')

# 4) Ready marker (per-session)
runtime_dir = DRV / 'outputs/runtime'
runtime_dir.mkdir(parents=True, exist_ok=True)
ready_marker = runtime_dir / f'session{session_tag}_READY'
ready_marker.write_text(json.dumps({
    'session_tag': session_tag,
    'ts': time.time(),
    'pid': os.getpid(),
    'gpu_free_gb': round(free/1024**3, 2),
}))
print(f'READY_MARKER: {ready_marker}')
print('PHASE26_PREP_DONE')
