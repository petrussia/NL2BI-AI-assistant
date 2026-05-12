"""Phase 25 — load planner (Qwen3-Coder-30B-A3B) + emitter (Coder-7B)
into the bridge kernel globals for downstream runners.

Idempotent. Re-run safely: skips if _V18_MODELS_READY=True.
"""
import os, sys, time
DRV = '/content/drive/MyDrive/diploma_plan_sql'
EVAL = DRV + '/repo/src/evaluation'
if EVAL not in sys.path: sys.path.insert(0, EVAL)

g = globals()
if g.get('_V18_MODELS_READY'):
    print('MODELS_ALREADY_READY')
else:
    # Make sure HF_TOKEN is in env (notebook cell 03 should have set it).
    # If not, try secrets/HF_TOKEN.json on Drive.
    if not os.environ.get('HF_TOKEN'):
        import json as _json
        from pathlib import Path as _Path
        p = _Path(DRV) / 'secrets' / 'HF_TOKEN.json'
        if p.is_file():
            try:
                t = _json.loads(p.read_text(encoding='utf-8')).get('HF_TOKEN')
                if t:
                    os.environ['HF_TOKEN'] = t
                    print(f'HF_TOKEN loaded from {p}')
            except Exception as e:
                print(f'HF_TOKEN load fail: {e}')

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
    print(f'VRAM after load: free={free/1024**3:.1f}/{total/1024**3:.1f} GB '
            f'alloc={torch.cuda.memory_allocated()/1024**3:.1f} GB')

print('PHASE25_LOAD_MODELS_DONE')
