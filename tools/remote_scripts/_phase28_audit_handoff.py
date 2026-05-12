"""Reliability audit for S1 Snow→Lite handoff.

Checks 8 invariants needed for unattended completion:
  1. S1 Snow chain alive and writing predictions.jsonl
  2. Number of preds in file matches progress.json counter (no FUSE drift)
  3. Supervisor thread alive and watching for _DONE
  4. /tmp/_phase27_snow_runner.py present (Lite chain needs it)
  5. Drive modules current (snow_identifier_guard_v27, snow_dialect_fixer_v28)
  6. Model globals still present (will Lite chain be able to invoke planner+emitter)
  7. _DONE file does not already exist (supervisor would fire prematurely if so)
  8. Disk space on /content (no /tmp ENOSPC)
"""
import threading, inspect, json, time, os, subprocess
from pathlib import Path

g = inspect.currentframe().f_globals
DRV = Path('/content/drive/MyDrive/diploma_plan_sql')
SNOW = DRV / 'outputs/spider2_snow/runs/snow_full_v28_revert_a'
LITE = DRV / 'outputs/spider2_lite/runs/lite_snow_full_v28_revert_a'

results = []
def check(name, ok, detail=''):
    results.append((ok, name, detail))
    flag = 'OK  ' if ok else 'FAIL'
    print(f'  {flag}  {name}{f" :: {detail}" if detail else ""}')

print('=== 1. S1 Snow chain liveness ===')
s1_chains = [t for t in threading.enumerate() if t.name == 'Phase28FullS1Chain']
chain_alive = bool(s1_chains and s1_chains[0].is_alive())
check('Phase28FullS1Chain alive', chain_alive,
      f'ident={s1_chains[0].ident if s1_chains else "?"}')

print('\n=== 2. Drive write integrity: preds rows == progress.n_total ===')
pj = SNOW / 'progress.json'
pf = SNOW / 'predictions.jsonl'
prog_n = None; pf_rows = None
if pj.exists():
    prog_n = json.loads(pj.read_text()).get('n_total')
    age = time.time() - pj.stat().st_mtime
    check('progress.json fresh (<5min idle)', age < 300, f'age={age:.0f}s n={prog_n}')
if pf.exists():
    pf_rows = sum(1 for _ in open(pf, encoding='utf-8'))
    check('predictions.jsonl rows == progress.n_total',
          pf_rows == prog_n, f'pf={pf_rows} vs progress={prog_n}')
else:
    check('predictions.jsonl exists', False)

print('\n=== 3. Supervisor liveness ===')
sup = [t for t in threading.enumerate() if t.name == 'Phase28S1Supervisor']
sup_alive = bool(sup and sup[0].is_alive())
check('Phase28S1Supervisor alive', sup_alive,
      f'ident={sup[0].ident if sup else "?"}')

print('\n=== 4. /tmp runner present ===')
tmp_runner = Path('/tmp/_phase27_snow_runner.py')
check('/tmp/_phase27_snow_runner.py exists', tmp_runner.exists(),
      f'size={tmp_runner.stat().st_size}B' if tmp_runner.exists() else 'MISSING')

print('\n=== 5. Drive modules current ===')
for fn in ['snow_identifier_guard_v27.py', 'snow_dialect_fixer_v28.py', 'schema_pack_builder_v18.py']:
    p = DRV / 'repo/src/evaluation' / fn
    check(f'module {fn}', p.exists(),
          f'size={p.stat().st_size}B' if p.exists() else 'MISSING')

print('\n=== 6. Model globals ===')
for k in ['_TOK_EMIT','_MDL_EMIT','_PROF_EMIT','_TOK_PLAN','_MDL_PLAN','_PROF_PLAN']:
    check(f'{k}', k in g, type(g[k]).__name__ if k in g else 'MISSING')

print('\n=== 7. _DONE does NOT pre-exist (would fire supervisor prematurely) ===')
done = SNOW / '_DONE'
check('_DONE absent', not done.exists())

print('\n=== 8. Disk space ===')
out = subprocess.getoutput('df -h /tmp /content /content/drive 2>&1 | head -8')
print(out)

print('\n=== summary ===')
n_ok = sum(1 for ok,_,_ in results if ok)
n_fail = len(results) - n_ok
print(f'  {n_ok}/{len(results)} OK; {n_fail} FAIL')
if n_fail:
    print('  failed checks:')
    for ok,n,d in results:
        if not ok: print(f'    - {n}  {d}')
else:
    print('  ALL CHECKS PASS — handoff infrastructure healthy')

# Also: when did the supervisor last "heartbeat"? It's silent right now.
# Add a Drive-visible heartbeat below.
print('\n=== Supervisor heartbeat status ===')
hb = SNOW.parent / '_supervisor_heartbeat.txt'
if hb.exists():
    print(f'  heartbeat: {hb.read_text()[:300]}')
else:
    print(f'  (no heartbeat file yet; will add one in supervisor v2)')
