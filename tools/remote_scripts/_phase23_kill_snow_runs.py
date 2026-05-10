"""Phase 23 — kill the OOMing Snow BG threads by raising a sentinel
event-flag they will check before each task. Since we can't kill threads
in Python directly, we set a global cancellation flag.

But our existing _run_snow_diag doesn't check a flag. Workaround: we
overwrite the run dir's _STARTED with a _CANCELLED marker, and let the
threads keep running but their outputs land in dead dirs. We mark the
existing runs as cancelled diagnostically and create new ones later.

Cleaner: monkey-patch torch.no_grad to raise after our flag is set. But
that's fragile. The cleanest is to just NOT relaunch them and leave the
already-OOMed traces as evidence of GPU contention. The threads will
eventually finish iterating their task list (always failing) and write
_DONE markers.

We also write _PHASE23_CANCEL_SNOW=True so any new launch logic skips
those run_ids.
"""
import json
import time
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
SNOW_RUNS = DRV / 'outputs/spider2_snow/runs/snow_full_diagnostic_v23'
LITE_SNOW_RUNS = DRV / 'outputs/spider2_lite/runs/lite_full_diagnostic_v23_snow'

g = globals()
g['_PHASE23_SNOW_CANCEL'] = True

for d in [SNOW_RUNS, LITE_SNOW_RUNS]:
    if d.is_dir():
        cancel_p = d / '_CANCELLED_OOM'
        cancel_p.write_text(json.dumps({
            'reason': 'OOM under concurrent inference with BQ FULL; need to relaunch sequentially after BQ FULL completes',
            'ts': time.time(),
        }))
        print(f'CANCELLED_MARK: {d.name}')

print('PHASE23_SNOW_KILL_DONE')
