"""Heartbeat probe for both FULL runs. Read run dirs from Drive (shared) and
report one line per kernel."""
import json, time
from pathlib import Path

DRV = Path('/content/drive/MyDrive/diploma_plan_sql')

def status(out_dir, label, n_target):
    p = out_dir / 'progress.json'
    err_file = out_dir / '_RUNNER_ERROR'
    done = (out_dir / '_DONE').exists()
    if not p.exists():
        return f'[{label}] no progress yet (dir exists: {out_dir.exists()})'
    d = json.loads(p.read_text())
    age = time.time() - p.stat().st_mtime
    parts = [
        f'[{label}]',
        f'n={d.get("n_total","?")}/{n_target}',
        f'sv={d.get("schema_valid",0)}',
        f'exec={d.get("execute_ok",0)}',
        f'wrp={d.get("wrapped_n",0)}',
        f'fb={d.get("guard_regex_fallback",0)}',
        f'wall={d.get("wall_sec",0)/60:.0f}min',
        f'last={d.get("last_task","?")}',
        f'idle={age:.0f}s',
    ]
    if done: parts.append('DONE')
    if err_file.exists(): parts.append('ERROR_FILE')
    return ' '.join(parts)

s1 = status(DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a', 'S1-Snow547', 547)
s2 = status(DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a', 'S2-Lite207', 207)
print(s1)
print(s2)

# Thread liveness via threading (executed inside the kernel)
import threading
alive_s1 = any(t.name == 'Phase28FullS1Chain' and t.is_alive() for t in threading.enumerate())
alive_s2 = any(t.name == 'Phase28FullS2Chain' and t.is_alive() for t in threading.enumerate())
# Only one of these will be true depending on which kernel runs this script
print(f'this kernel: S1chain={alive_s1} S2chain={alive_s2}')
