"""Find where the loaded models live. GPU has 76GB allocated so they exist."""
import sys, gc, torch, types
print('=== sys.modules with EMIT/PLAN/MDL/TOK ===')
for name, mod in list(sys.modules.items()):
    if mod is None: continue
    for attr in ['_TOK_EMIT', '_MDL_EMIT', '_TOK_PLAN', '_MDL_PLAN',
                 'tok_emit', 'mdl_emit', 'tokenizer_emit', 'model_emit',
                 'EMITTER', 'PLANNER']:
        if hasattr(mod, attr):
            v = getattr(mod, attr)
            print(f'  sys.modules[{name!r}].{attr} = {type(v).__name__}')

# Direct probe __main__
m = sys.modules.get('__main__')
print(f'\n__main__ id: {id(m.__dict__)}')
print(f'__main__ has _TOK_EMIT: {"_TOK_EMIT" in m.__dict__}')

# Check current frame globals
import inspect
frame = inspect.currentframe()
print(f'\ncurrent frame globals id: {id(frame.f_globals)}')
print(f'current frame globals same as __main__: {frame.f_globals is m.__dict__}')

# scan for AutoModelForCausalLM instances via gc
print('\n=== GC scan for transformer models ===')
import transformers
target_types = (transformers.PreTrainedModel, transformers.PreTrainedTokenizerBase)
seen = []
for obj in gc.get_objects():
    try:
        if isinstance(obj, target_types):
            cls = type(obj).__name__
            nparams = sum(p.numel() for p in obj.parameters()) if hasattr(obj, 'parameters') else 0
            seen.append((cls, nparams, id(obj)))
    except Exception:
        pass
seen.sort(key=lambda x: -x[1])
for cls, n, _ in seen[:6]:
    print(f'  {cls}: params={n:,}')

# Locate by referrers
if seen:
    print('\n=== referrers of top model ===')
    obj_id = seen[0][2]
    obj = next(o for o in gc.get_objects() if id(o) == obj_id)
    for r in gc.get_referrers(obj)[:5]:
        if isinstance(r, dict):
            # find which key holds it
            for k, v in r.items():
                if v is obj:
                    print(f'  dict key {k!r} | dict id={id(r)}')
                    break
        else:
            print(f'  type={type(r).__name__}')
