"""Phase 28 S2 bringup — launch _phase25_load_models in a background thread
so /exec returns immediately. Poll _V18_MODELS_READY to detect completion."""
import os, sys, threading, time, traceback, inspect
g = inspect.currentframe().f_globals

DRV = '/content/drive/MyDrive/diploma_plan_sql'
EVAL = DRV + '/repo/src/evaluation'
if EVAL not in sys.path: sys.path.insert(0, EVAL)

if g.get('_V18_MODELS_READY'):
    print('MODELS_ALREADY_READY')
else:
    # Stash status so we can poll
    g['_MODEL_LOAD_STATUS'] = 'launching'

    def _load():
        try:
            g['_MODEL_LOAD_STATUS'] = 'in_progress'
            # Make sure HF_TOKEN is in env (notebook cell 03 should have set it).
            if not os.environ.get('HF_TOKEN'):
                import json as _json
                from pathlib import Path as _Path
                p = _Path(DRV) / 'secrets' / 'HF_TOKEN.json'
                if p.is_file():
                    try:
                        t = _json.loads(p.read_text(encoding='utf-8')).get('HF_TOKEN')
                        if t:
                            os.environ['HF_TOKEN'] = t
                            print(f'HF_TOKEN loaded from {p}', flush=True)
                    except Exception as e:
                        print(f'HF_TOKEN load fail: {e}', flush=True)

            import importlib
            if 'model_registry_v17' in sys.modules:
                importlib.reload(sys.modules['model_registry_v17'])
            from model_registry_v17 import load_model_and_tokenizer

            EMIT_ALIAS = 'qwen2_5_coder_7b'
            PLAN_ALIAS = 'qwen3_coder_30b_bf16'

            # Skip emitter reload if already present (avoids GPU memory waste)
            if 'mdl_b' in g and 'tok_b' in g:
                print('EMITTER already loaded (mdl_b/tok_b present); skipping', flush=True)
                # Make sure runner aliases are set
                g['_TOK_EMIT'] = g['tok_b']; g['_MDL_EMIT'] = g['mdl_b']
                g['_PROF_EMIT'] = g.get('prof_b')
            else:
                t0 = time.time()
                print(f'LOAD_EMITTER {EMIT_ALIAS} ...', flush=True)
                tok_b, mdl_b, prof_b = load_model_and_tokenizer(EMIT_ALIAS)
                g['_TOK_EMIT'] = tok_b; g['_MDL_EMIT'] = mdl_b; g['_PROF_EMIT'] = prof_b
                g['tok_b'] = tok_b; g['mdl_b'] = mdl_b; g['prof_b'] = prof_b
                print(f'EMITTER_LOADED in {time.time()-t0:.1f}s', flush=True)
            g['_MODEL_LOAD_STATUS'] = 'emitter_done'

            t1 = time.time()
            print(f'LOAD_PLANNER {PLAN_ALIAS} ...', flush=True)
            tok_a, mdl_a, prof_a = load_model_and_tokenizer(PLAN_ALIAS)
            g['_TOK_PLAN'] = tok_a; g['_MDL_PLAN'] = mdl_a; g['_PROF_PLAN'] = prof_a
            g['tok_a'] = tok_a; g['mdl_a'] = mdl_a; g['prof_a'] = prof_a
            print(f'PLANNER_LOADED in {time.time()-t1:.1f}s', flush=True)

            g['_V18_MODELS_READY'] = True
            g['_MODEL_LOAD_STATUS'] = 'done'

            import torch
            free, total = torch.cuda.mem_get_info()
            print(f'VRAM after load: free={free/1024**3:.1f}/{total/1024**3:.1f} GB '
                  f'alloc={torch.cuda.memory_allocated()/1024**3:.1f} GB', flush=True)
        except Exception as e:
            g['_MODEL_LOAD_STATUS'] = f'error: {type(e).__name__}: {e}'
            g['_MODEL_LOAD_TB'] = traceback.format_exc()
            print(f'LOAD_FAILED: {e}', flush=True)

    t = threading.Thread(target=_load, name='Phase28S2ModelLoad', daemon=True)
    t.start()
    print(f'Phase28S2ModelLoad thread started: ident={t.ident}')
    print(f'_MODEL_LOAD_STATUS now: {g["_MODEL_LOAD_STATUS"]}')
    print('(load runs in background; poll _MODEL_LOAD_STATUS and _V18_MODELS_READY)')
