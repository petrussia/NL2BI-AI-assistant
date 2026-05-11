"""List all keys in current globals, find tokenizers + models + profiles,
then alias them to runner-expected names (_TOK_EMIT, _MDL_EMIT, ...)."""
import sys, inspect, transformers

g = inspect.currentframe().f_globals
print(f'globals id: {id(g)}, key count: {len(g)}')

# Build inventory
keys_of_interest = []
for k, v in g.items():
    if k.startswith('__'): continue
    cls = type(v).__name__
    if any(s in cls.lower() for s in ('tokenizer', 'forcausallm', 'profile')) \
       or any(s in k.lower() for s in ('tok', 'mdl', 'model', 'prof', 'emit', 'plan')):
        keys_of_interest.append((k, cls))
keys_of_interest.sort()
print('\n=== keys of interest ===')
for k, cls in keys_of_interest:
    extra = ''
    v = g[k]
    if hasattr(v, 'parameters'):
        try:
            n = sum(p.numel() for p in v.parameters())
            extra = f' params={n:,}'
        except Exception:
            pass
    print(f'  {k}: {cls}{extra}')

# Common Phase-25/26 naming: mdl_a/tok_a = planner; mdl_b/tok_b = emitter
# OR: planner/emitter; OR: _MDL_PLAN/_MDL_EMIT
print('\n=== mapping attempt ===')
mapping = {}
for src_name, role in [('a', 'PLAN'), ('b', 'EMIT')]:
    mdl_key = f'mdl_{src_name}'
    tok_key = f'tok_{src_name}'
    prof_key = f'prof_{src_name}'
    if mdl_key in g:
        mapping[f'_MDL_{role}'] = mdl_key
    if tok_key in g:
        mapping[f'_TOK_{role}'] = tok_key
    if prof_key in g:
        mapping[f'_PROF_{role}'] = prof_key

# Discover profile defs if mapping incomplete
if '_PROF_PLAN' not in mapping or '_PROF_EMIT' not in mapping:
    for k, v in g.items():
        cls = type(v).__name__
        if 'profile' in cls.lower() or k.startswith('prof'):
            print(f'  candidate profile: {k}: {cls}')

print(f'mapping: {mapping}')

# Apply aliases in the shared globals dict — these are what the runner expects
for dst, src in mapping.items():
    g[dst] = g[src]
    print(f'  alias {dst} <- {src}')

# Verify
print('\n=== after aliasing ===')
for k in ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']:
    if k in g:
        print(f'  {k}: {type(g[k]).__name__}')
    else:
        print(f'  {k}: MISSING')
