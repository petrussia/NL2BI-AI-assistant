import os, sys, subprocess, time, json
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
TASKS = """provider001 asana001 shopify001 asset001 flicks001 analytics_engineering001 xero_new001 chinook001 workday002 scd001 airport001 salesforce001 recharge001 maturity001 tpch002 nba001 quickbooks001""".split()
RUN_ID = "dbt_full_v26_final17"
LOG = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\outputs\spider2_dbt\dbt_full_v26_final17_runlog.txt")
env = os.environ.copy()
env["BRIDGE_URL_FILE"] = "tools/.bridge_url_dbt"
env["PYTHONUNBUFFERED"] = "1"
cmd = [sys.executable, "-u", str(REPO / "spider2_dbt_bridge" / "run_dbt_ablation.py"),
       "--tasks"] + TASKS + ["--variants", "v4", "--max-new", "1500", "--run-id", RUN_ID]
with LOG.open("w", encoding="utf-8") as f:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    f.write("[" + ts + "] DBT FINAL17 launching n=" + str(len(TASKS)) + "\n")
    f.flush()
    proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(REPO))
    ts2 = time.strftime("%Y-%m-%d %H:%M:%S")
    f.write("\n[" + ts2 + "] DBT exit code: " + str(proc.returncode) + "\n")
done = REPO / "outputs" / "runtime" / "dbt_full_v26_final17_done_local.json"
done.parent.mkdir(parents=True, exist_ok=True)
done.write_text(json.dumps({"run_id": RUN_ID, "exit_code": proc.returncode, "ts": time.time()}))
