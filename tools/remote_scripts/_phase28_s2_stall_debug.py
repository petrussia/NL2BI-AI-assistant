"""Debug S2 stall: check Phase28FullS2Chain liveness, GPU, recent traces."""
import threading, time, json
from pathlib import Path

print('=== S2 threads (Phase chains + workers) ===')
for t in threading.enumerate():
    if 'Phase' in t.name or '_runner' in t.name:
        print(f'  {t.name}: alive={t.is_alive()} daemon={t.daemon} ident={t.ident}')

# Anything else of interest
print('\n=== all non-bridge alive daemons ===')
keep = ('MainThread', 'IOPub', 'Heartbeat', 'Control', 'bridge-flask',
        'process_request_thread', '_read_incoming', 'Thread-2', 'Thread-3')
for t in threading.enumerate():
    if any(k in t.name for k in keep): continue
    if not t.is_alive(): continue
    print(f'  {t.name}: ident={t.ident}')

print('\n=== GPU ===')
try:
    import torch
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            free, total = torch.cuda.mem_get_info(i)
            alloc = torch.cuda.memory_allocated(i)
            print(f'  cuda:{i}: alloc={alloc/1e9:.1f}GB free={free/1e9:.1f}GB / total={total/1e9:.1f}GB')
except Exception as e:
    print(f'  GPU probe err: {e}')

print('\n=== S2 run dir state ===')
RUN = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/lite_snow_full_v28_revert_a')
for p in sorted(RUN.iterdir(), key=lambda x: -x.stat().st_mtime)[:8]:
    age = (time.time() - p.stat().st_mtime) / 60
    print(f'  {p.name:30s} {p.stat().st_size:>9d}B  age={age:.1f}min')

# Tail traces.jsonl to see what's there
print('\n=== last 3 traces in S2 traces.jsonl ===')
tf = RUN / 'traces.jsonl'
if tf.exists():
    lines = tf.read_text(encoding='utf-8').splitlines()[-3:]
    for ln in lines:
        try:
            t = json.loads(ln)
            print(f"  iid={t.get('instance_id')} task_db={t.get('task_db')} "
                  f"sv={t.get('schema_valid')} parse={t.get('parse_ok')} "
                  f"explain_ok={t.get('explain_ok')} "
                  f"explain_class={t.get('explain_class','?')} "
                  f"err={t.get('error_type','-')}")
        except Exception as e:
            print(f'  parse err: {e}')

# Check if _RUNNER_ERROR exists
err_f = RUN / '_RUNNER_ERROR'
if err_f.exists():
    print(f'\n=== _RUNNER_ERROR ({err_f.stat().st_size}B) ===')
    print(err_f.read_text()[:1500])
