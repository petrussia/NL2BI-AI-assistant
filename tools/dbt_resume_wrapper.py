import os, sys, subprocess, time, json
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
TASKS = """divvy001 playbook002 apple_store001 jira001 zuora001 superstore001 marketo001 f1002 gitcoin001 shopify_holistic_reporting001 hive001 workday001 f1003 retail001 google_play002 sap001 airbnb001 app_reporting001 mrr002 twilio001 intercom001 tickit001 reddit001 recharge001 maturity001 tpch002 nba001 quickbooks001""".split()
RUN_ID = "dbt_full_v26_resume28"
LOG = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\outputs\spider2_dbt\dbt_full_v26_resume28_runlog.txt")
env = os.environ.copy()
env["BRIDGE_URL_FILE"] = "tools/.bridge_url_dbt"
cmd = [sys.executable, str(REPO / "spider2_dbt_bridge" / "run_dbt_ablation.py"),
       "--tasks"] + TASKS + ["--variants", "v4", "--max-new", "1500", "--run-id", RUN_ID]
with LOG.open("w", encoding="utf-8") as f:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    f.write("[" + ts + "] DBT RESUME launching n=" + str(len(TASKS)) + "\n")
    f.flush()
    proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(REPO))
    ts2 = time.strftime("%Y-%m-%d %H:%M:%S")
    f.write("\n[" + ts2 + "] DBT exit code: " + str(proc.returncode) + "\n")
done = REPO / "outputs" / "runtime" / "dbt_full_v26_resume_done_local.json"
done.parent.mkdir(parents=True, exist_ok=True)
done.write_text(json.dumps({"run_id": RUN_ID, "exit_code": proc.returncode, "ts": time.time()}))
