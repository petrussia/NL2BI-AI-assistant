"""Launch DBT FULL final on remaining 17 tasks (detached) — S2 bridge free."""
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_ID = 'dbt_full_v26_final17'
RUNLOG = REPO / 'outputs' / 'spider2_dbt' / f'{RUN_ID}_runlog.txt'
RUNLOG.parent.mkdir(parents=True, exist_ok=True)

MISSING = [
    'provider001', 'asana001', 'shopify001', 'asset001', 'flicks001',
    'analytics_engineering001', 'xero_new001', 'chinook001', 'workday002',
    'scd001', 'airport001', 'salesforce001', 'recharge001', 'maturity001',
    'tpch002', 'nba001', 'quickbooks001'
]
print(f'launching DBT FULL FINAL17 on {len(MISSING)} tasks via S2 bridge')

wrapper = REPO / 'tools' / 'dbt_final17_wrapper.py'
src = (
    'import os, sys, subprocess, time, json\n'
    'from pathlib import Path\n'
    'REPO = Path(__file__).resolve().parents[1]\n'
    f'TASKS = """{ " ".join(MISSING) }""".split()\n'
    f'RUN_ID = "{RUN_ID}"\n'
    f'LOG = Path(r"{RUNLOG}")\n'
    'env = os.environ.copy()\n'
    'env["BRIDGE_URL_FILE"] = "tools/.bridge_url_dbt"\n'
    'env["PYTHONUNBUFFERED"] = "1"\n'
    'cmd = [sys.executable, "-u", str(REPO / "spider2_dbt_bridge" / "run_dbt_ablation.py"),\n'
    '       "--tasks"] + TASKS + ["--variants", "v4", "--max-new", "1500", "--run-id", RUN_ID]\n'
    'with LOG.open("w", encoding="utf-8") as f:\n'
    '    ts = time.strftime("%Y-%m-%d %H:%M:%S")\n'
    '    f.write("[" + ts + "] DBT FINAL17 launching n=" + str(len(TASKS)) + "\\n")\n'
    '    f.flush()\n'
    '    proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(REPO))\n'
    '    ts2 = time.strftime("%Y-%m-%d %H:%M:%S")\n'
    '    f.write("\\n[" + ts2 + "] DBT exit code: " + str(proc.returncode) + "\\n")\n'
    'done = REPO / "outputs" / "runtime" / "dbt_full_v26_final17_done_local.json"\n'
    'done.parent.mkdir(parents=True, exist_ok=True)\n'
    'done.write_text(json.dumps({"run_id": RUN_ID, "exit_code": proc.returncode, "ts": time.time()}))\n'
)
wrapper.write_text(src, encoding='utf-8')

DETACHED = 0x00000008; NEW_GROUP = 0x00000200; CREATE_NO_WINDOW = 0x08000000
flags = DETACHED | NEW_GROUP | CREATE_NO_WINDOW

proc = subprocess.Popen(
    [sys.executable, str(wrapper)],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
    creationflags=flags, close_fds=True,
)
print(f'detached pid={proc.pid}; runlog={RUNLOG}')
