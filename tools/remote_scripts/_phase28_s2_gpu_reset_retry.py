"""Clear all model state on S2 (incl. partial planner from failed load),
free GPU, then re-trigger model load from scratch."""
import sys, gc, inspect

g = inspect.currentframe().f_globals

print('=== before cleanup ===')
import torch
print(f'GPU alloc: {torch.cuda.memory_allocated(0)/1e9:.2f} GB')
print(f'GPU reserved: {torch.cuda.memory_reserved(0)/1e9:.2f} GB')

# Delete model refs aggressively
for name in ['tok_a','mdl_a','prof_a','tok_b','mdl_b','prof_b',
            '_TOK_EMIT','_MDL_EMIT','_PROF_EMIT',
            '_TOK_PLAN','_MDL_PLAN','_PROF_PLAN',
            '_V18_MODELS_READY','_MODEL_LOAD_STATUS','_MODEL_LOAD_TB']:
    if name in g:
        del g[name]
        print(f'  del {name}')

# Find any lingering PreTrainedModel via gc and explicitly del
import transformers
target = (transformers.PreTrainedModel,)
lingering = []
for obj in gc.get_objects():
    try:
        if isinstance(obj, target):
            lingering.append((type(obj).__name__, sum(p.numel() for p in obj.parameters())))
    except Exception:
        pass
print(f'lingering models after var-del: {lingering}')

gc.collect()
torch.cuda.empty_cache()
torch.cuda.synchronize()

print('=== after cleanup ===')
print(f'GPU alloc: {torch.cuda.memory_allocated(0)/1e9:.2f} GB')
print(f'GPU reserved: {torch.cuda.memory_reserved(0)/1e9:.2f} GB')

# Some allocations may be held by Python frames of dead threads — force one more pass
gc.collect()
import time; time.sleep(2)
torch.cuda.empty_cache()
print(f'final alloc: {torch.cuda.memory_allocated(0)/1e9:.2f} GB / reserved: {torch.cuda.memory_reserved(0)/1e9:.2f} GB')
