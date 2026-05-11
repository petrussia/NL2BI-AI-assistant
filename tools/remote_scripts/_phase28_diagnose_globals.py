"""Diagnose why model globals are missing in S1 __main__."""
import sys, threading, gc, torch
g = sys.modules['__main__'].__dict__

print('=== threads ===')
for t in threading.enumerate():
    print(f'  {t.name}: alive={t.is_alive()}')

print('\n=== __main__ keys (filtered) ===')
keys = sorted([k for k in g.keys() if k.startswith('_TOK') or k.startswith('_MDL') or k.startswith('_PROF')
               or 'planner' in k.lower() or 'emit' in k.lower() or 'model' in k.lower()])[:40]
for k in keys:
    v = g[k]
    print(f'  {k}: {type(v).__name__}')

print('\n=== GPU memory ===')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        print(f'  cuda:{i}: {torch.cuda.memory_allocated(i)/1e9:.2f} GB allocated, '
              f'{torch.cuda.memory_reserved(i)/1e9:.2f} GB reserved')

# Try common alternative names
print('\n=== broader scan ===')
candidates = ['emitter', 'planner', 'tok_emit', 'mdl_emit', 'TOK_EMIT', 'MDL_EMIT',
              '_EMIT_TOK', '_PLAN_TOK', 'tokenizer_emit', 'model_emit']
for c in candidates:
    if c in g:
        print(f'  FOUND: {c} ({type(g[c]).__name__})')
