"""Phase 24 STAGE 2 — runtime cleanup.

Replace v23 runner gen/plan helpers with fast-fail stubs so any still-alive
BG threads exit their loops quickly. Mark all v23 run dirs as cancelled.
Free CUDA cache. DO NOT restart kernel.
"""
import json, time, gc, threading
from pathlib import Path

g = globals()


def _stub(*a, **k):
    raise RuntimeError('PHASE24_V23_THREAD_ABORTED')


# Phase 23 BG runners installed these names in shared globals — overwrite all.
TO_STUB = [
    '_v18_plan', '_v18_plan_local',
    '_gen', '_gen_planner', '_gen_planner_local',
    '_gen_emitter', '_gen_emitter_local',
]
for name in TO_STUB:
    if g.get(name) is not None:
        g[name] = _stub
        print(f'STUBBED {name}')

# Mark all v23 run dirs as cancelled if they aren't done.
DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
v23_dirs = [
    DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_bq',
    DRV / 'outputs/spider2_snow/runs/snow_full_diagnostic_v23',
    DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_snow',
]
for d in v23_dirs:
    if d.is_dir() and not (d / '_DONE').is_file():
        cm = d / '_CANCELLED_OOM'
        if not cm.is_file():
            cm.write_text(json.dumps({'reason': 'phase24_force_cancel', 'ts': time.time()}))
            print(f'MARK_CANCELLED: {d.name}')

# Free CUDA cache, run gc
import torch
gc.collect()
torch.cuda.empty_cache()
gc.collect()
torch.cuda.empty_cache()
free, total = torch.cuda.mem_get_info()
print(f'GPU after cleanup: free={free/1024**3:.2f}/{total/1024**3:.2f} GB')

# List threads
ts = [t for t in threading.enumerate() if '_runner' in t.name]
print(f'Alive _runner threads: {len(ts)} ({[t.name for t in ts]})')

print('PHASE24_CLEANUP_DONE')
