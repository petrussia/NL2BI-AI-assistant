"""Launch DBT remaining 28 tasks (divvy001 + tasks 42-68) detached.

Tasks 1-40 already done in dbt_full_v26 (model_response_v4 written, eval done).
Task 41 (divvy001) crashed on SSH timeout — retry with bumped timeout.
Tasks 42-68 = 27 not run.

Total = 1 + 27 = 28 tasks.

Run-id: dbt_full_v26_resume28. After done, marks Drive flag for chain.
"""
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_ID = 'dbt_full_v26_resume28'
RUNLOG = REPO / 'outputs' / 'spider2_dbt' / f'{RUN_ID}_runlog.txt'
RUNLOG.parent.mkdir(parents=True, exist_ok=True)

# Read all 68
with open(REPO / '_all_68.txt', encoding='utf-8') as f:
    all_tasks = f.read().strip().split()

# Tasks 41-68 (1-indexed positions 41..68 → list indices 40..67)
remaining = all_tasks[40:]
print(f'remaining tasks ({len(remaining)}): {remaining[:5]}...{remaining[-3:]}')

wrapper = REPO / 'tools' / 'dbt_resume_wrapper.py'
src = (
    'import os, sys, subprocess, time, json\n'
    'from pathlib import Path\n'
    'REPO = Path(__file__).resolve().parents[1]\n'
    f'TASKS = """{ " ".join(remaining) }""".split()\n'
    f'RUN_ID = "{RUN_ID}"\n'
    f'LOG = Path(r"{RUNLOG}")\n'
    'env = os.environ.copy()\n'
    'env["BRIDGE_URL_FILE"] = "tools/.bridge_url_dbt"\n'
    'cmd = [sys.executable, str(REPO / "spider2_dbt_bridge" / "run_dbt_ablation.py"),\n'
    '       "--tasks"] + TASKS + ["--variants", "v4", "--max-new", "1500", "--run-id", RUN_ID]\n'
    'with LOG.open("w", encoding="utf-8") as f:\n'
    '    ts = time.strftime("%Y-%m-%d %H:%M:%S")\n'
    '    f.write("[" + ts + "] DBT RESUME launching n=" + str(len(TASKS)) + "\\n")\n'
    '    f.flush()\n'
    '    proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(REPO))\n'
    '    ts2 = time.strftime("%Y-%m-%d %H:%M:%S")\n'
    '    f.write("\\n[" + ts2 + "] DBT exit code: " + str(proc.returncode) + "\\n")\n'
    'done = REPO / "outputs" / "runtime" / "dbt_full_v26_resume_done_local.json"\n'
    'done.parent.mkdir(parents=True, exist_ok=True)\n'
    'done.write_text(json.dumps({"run_id": RUN_ID, "exit_code": proc.returncode, "ts": time.time()}))\n'
)
wrapper.write_text(src, encoding='utf-8')

DETACHED = 0x00000008
NEW_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
flags = DETACHED | NEW_GROUP | CREATE_NO_WINDOW

proc = subprocess.Popen(
    [sys.executable, str(wrapper)],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
    creationflags=flags, close_fds=True,
)
print(f'detached pid={proc.pid}; runlog={RUNLOG}')
