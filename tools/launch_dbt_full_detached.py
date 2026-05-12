"""Launch DBT FULL 68 v4 as a fully detached subprocess on Windows.
Survives parent shell exit. Logs to outputs/spider2_dbt/dbt_full_v26_runlog.txt.

After all 68 tasks done, writes a marker file the bridge daemon reads:
  <PROJECT_ROOT>/outputs/runtime/phase26_session2/DBT_DONE_v26
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TASKS_FILE = REPO / '_all_68.txt'
RUN_ID = 'dbt_full_v26'
RUNLOG = REPO / 'outputs' / 'spider2_dbt' / f'{RUN_ID}_runlog.txt'
RUNLOG.parent.mkdir(parents=True, exist_ok=True)

if not TASKS_FILE.is_file():
    print(f'tasks file not found: {TASKS_FILE}', file=sys.stderr)
    sys.exit(1)

tasks = TASKS_FILE.read_text(encoding='utf-8').strip().split()
print(f'launching DBT FULL with {len(tasks)} tasks; runlog={RUNLOG}')

# Wrapper that writes DBT_DONE marker after ablation finishes
wrapper = REPO / 'tools' / 'dbt_full_wrapper.py'
tasks_join = ' '.join(tasks)
wrapper_src = (
    'import os, sys, subprocess, time, json\n'
    'from pathlib import Path\n'
    'REPO = Path(__file__).resolve().parents[1]\n'
    f'TASKS = """{tasks_join}""".split()\n'
    f'RUN_ID = "{RUN_ID}"\n'
    f'LOG = Path(r"{RUNLOG}")\n'
    'env = os.environ.copy()\n'
    'env["BRIDGE_URL_FILE"] = "tools/.bridge_url_dbt"\n'
    'cmd = [sys.executable, str(REPO / "spider2_dbt_bridge" / "run_dbt_ablation.py"),\n'
    '       "--tasks"] + TASKS + ["--variants", "v4", "--max-new", "1500", "--run-id", RUN_ID]\n'
    'with LOG.open("w", encoding="utf-8") as f:\n'
    '    ts = time.strftime("%Y-%m-%d %H:%M:%S")\n'
    '    f.write("[" + ts + "] DBT FULL launching n=" + str(len(TASKS)) + "\\n")\n'
    '    f.flush()\n'
    '    proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(REPO))\n'
    '    ts2 = time.strftime("%Y-%m-%d %H:%M:%S")\n'
    '    f.write("\\n[" + ts2 + "] DBT exit code: " + str(proc.returncode) + "\\n")\n'
    'done = REPO / "outputs" / "runtime" / "dbt_full_v26_done_local.json"\n'
    'done.parent.mkdir(parents=True, exist_ok=True)\n'
    'done.write_text(json.dumps({"run_id": RUN_ID, "exit_code": proc.returncode, "ts": time.time()}))\n'
)
wrapper.write_text(wrapper_src, encoding='utf-8')

# Launch with Windows DETACHED_PROCESS (creationflags 0x00000008) so it
# survives parent. Use CREATE_NEW_PROCESS_GROUP (0x00000200) so console
# signals don't propagate.
DETACHED = 0x00000008
NEW_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
flags = DETACHED | NEW_GROUP | CREATE_NO_WINDOW

proc = subprocess.Popen(
    [sys.executable, str(wrapper)],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL,
    creationflags=flags,
    close_fds=True,
)
print(f'detached pid={proc.pid}; runlog will appear at {RUNLOG}')
print('Run "tail" on runlog to watch progress.')
