"""run_spider2_v18_bq_pilot.py — local launcher for Phase 18 BQ pilot10.

End-to-end thin slice:
  1. Pulls Spider2-Lite-BQ canonical jsonl (filter to BQ tasks).
  2. Loads live BQ catalog jsonl produced by harvest_bq_live_catalog_v18.py.
  3. For each task:
     - schema_link the question against the live catalog
     - build compact pack
     - call Qwen3-Coder-30B-A3B-Instruct planner -> JSON plan
     - validate plan against pack
     - emit Family A (deterministic render) + Family B (Coder-7B direct)
     - select via validator-first policy with optional BQ dry_run
  4. Writes predictions.jsonl + traces.jsonl + readout.md + recall.csv to
     a Drive run-dir; canonical predictions copied locally.

The runner is launched as a BG thread on Colab via the bridge, mirroring
the v16/v17 pattern (start_*_bg + Drive marker + 30s poll). Designed to
work with `model_registry_v17.load_model_and_tokenizer` for both planner
and direct emitter — the launcher loads two models (planner + control)
on demand.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRIDGE_FILE = REPO / 'tools' / '.bridge_url'


def bridge_url() -> str:
    return BRIDGE_FILE.read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code: str, timeout: int = 90) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


# ---------- Self-contained runner template (sent verbatim to bridge) -----

RUNNER_TEMPLATE = r'''
import os, sys, json, time, traceback, threading
from pathlib import Path

DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
LITE_JSONL = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
BQ_CATALOG = DRV / "outputs/cache/spider2_bq_live_catalog_v18.jsonl"
RUNS_BASE  = DRV / "outputs/spider2_lite/runs"
EVAL_DIR   = DRV / "repo/src/evaluation"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))


def _load_models(planner_alias, emitter_alias):
    """Load planner + emitter HF models via model_registry_v17. The two
    models are kept in distinct global slots so we don't trample VRAM.
    Order matters on A100-80GB: load 7B first (small), then 30B."""
    g = globals()
    if g.get("_V18_MODELS_READY"):
        return
    import importlib
    if "model_registry_v17" in sys.modules:
        importlib.reload(sys.modules["model_registry_v17"])
    from model_registry_v17 import load_model_and_tokenizer
    print(f"LOAD_EMITTER {emitter_alias}", flush=True)
    tok_b, mdl_b, prof_b = load_model_and_tokenizer(emitter_alias)
    g["_TOK_EMIT"] = tok_b; g["_MDL_EMIT"] = mdl_b; g["_PROF_EMIT"] = prof_b
    print(f"LOAD_PLANNER {planner_alias}", flush=True)
    tok_a, mdl_a, prof_a = load_model_and_tokenizer(planner_alias)
    g["_TOK_PLAN"] = tok_a; g["_MDL_PLAN"] = mdl_a; g["_PROF_PLAN"] = prof_a
    g["_V18_MODELS_READY"] = True
    import torch
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        print(f"VRAM after both loaded: free={free/1024**3:.1f}/{total/1024**3:.1f} GB", flush=True)


def _gen(tok, mdl, prof, prompt, max_new):
    import torch
    nt = bool(getattr(prof, "non_thinking_mode", False))
    msgs = [{"role": "user", "content": prompt}]
    extra = {"enable_thinking": False} if nt else {}
    try:
        enc = tok.apply_chat_template(msgs, return_tensors="pt",
                                       add_generation_prompt=True,
                                       return_dict=True, **extra)
    except TypeError:
        enc = tok.apply_chat_template(msgs, return_tensors="pt",
                                       add_generation_prompt=True,
                                       return_dict=True)
    enc = {k: v.to(mdl.device) for k, v in enc.items()}
    with torch.no_grad():
        out = mdl.generate(**enc, max_new_tokens=max_new,
                              do_sample=False, temperature=0.0,
                              pad_token_id=tok.eos_token_id)
    gen = out[0][enc["input_ids"].shape[1]:]
    return tok.decode(gen, skip_special_tokens=True)


def _gen_planner(prompt, max_new=1100):
    g = globals()
    return _gen(g["_TOK_PLAN"], g["_MDL_PLAN"], g["_PROF_PLAN"], prompt, max_new)


def _gen_emitter(prompt, max_new=900):
    g = globals()
    return _gen(g["_TOK_EMIT"], g["_MDL_EMIT"], g["_PROF_EMIT"], prompt, max_new)


def _v18_plan(prompt, pack, max_attempts=2):
    """v18.1: validator-feedback retry. On the first failure, the
    planner is re-prompted with the exact validation reasons + the
    previous plan, and asked to correct only the offending identifiers."""
    import structured_plan_v18 as sp
    raw = ""
    last_err = None
    last_plan = None
    last_val = None
    cur_prompt = prompt
    retry_used = False
    for attempt in range(1, max_attempts + 1):
        raw = _gen_planner(cur_prompt)
        try:
            cand = sp.parse_plan(raw)
        except Exception as e:
            last_err = f"parse_err:{type(e).__name__}:{str(e)[:200]}"
            continue
        v = sp.validate_plan(cand, pack)
        last_plan = cand
        last_val = v
        if v.ok:
            return {"plan": cand, "validation": v, "raw": raw,
                      "attempts": attempt, "retry_used": retry_used}
        if attempt < max_attempts:
            cur_prompt = sp._retry_prompt(prompt, v.reasons, cand)
            retry_used = True
    return {"plan": last_plan, "validation": last_val, "raw": raw,
              "attempts": max_attempts, "last_parse_err": last_err,
              "retry_used": retry_used}


def start_v18_bq_bg(limit, run_id, max_rows=100, no_execute=False,
                       planner_alias="qwen3_coder_30b_bf16",
                       emitter_alias="qwen2_5_coder_7b"):
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    started_p = out_dir / "_STARTED"
    started_p.write_text(json.dumps({"run_id": run_id, "limit": limit,
                                       "planner_alias": planner_alias,
                                       "emitter_alias": emitter_alias,
                                       "ts": time.time()}))

    def _runner():
        try:
            _load_models(planner_alias, emitter_alias)
            import schema_linking_v18 as sl
            import schema_pack_builder_v18 as sb
            import structured_plan_v18 as sp
            import spider2_candidate_factory_v18 as cf
            import candidate_selector_v18 as cs

            # ---- Load tasks ----
            all_tasks = []
            with open(LITE_JSONL, encoding="utf-8") as fh:
                for ln in fh:
                    if ln.strip():
                        all_tasks.append(json.loads(ln))
            # Filter to BQ tasks (db_id starts with bq lookup; canonical filter:
            # the resource path is bigquery alias -> use it). Spider2-Lite uses
            # `db_id` that matches alias names under resource/databases/bigquery/
            BQ_BASE = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery"
            bq_aliases = set(os.listdir(BQ_BASE)) if BQ_BASE.is_dir() else set()
            bq_tasks = [t for t in all_tasks if t.get("db", "") in bq_aliases or t.get("db_id", "") in bq_aliases]
            tasks = bq_tasks[:limit]
            print(f"BQ tasks selected: {len(tasks)} of {len(bq_tasks)} BQ available",
                  flush=True)

            # ---- Load catalog ----
            catalog_cols = sl.load_catalog_jsonl(BQ_CATALOG, "bq")
            print(f"catalog columns indexed: {len(catalog_cols)}", flush=True)
            linker = sl.SchemaLinker(catalog_cols)

            # ---- Iterate ----
            preds_p = out_dir / "predictions.jsonl"
            traces_p = out_dir / "traces.jsonl"
            recall_p = out_dir / "schema_linking_recall.csv"
            metrics_p = out_dir / "metrics.csv"
            error_p = out_dir / "error_taxonomy.csv"
            preds_fh = open(preds_p, "w", encoding="utf-8")
            traces_fh = open(traces_p, "w", encoding="utf-8")
            recall_fh = open(recall_p, "w", encoding="utf-8")
            recall_fh.write("instance_id,alias,n_columns_indexed,n_tables_indexed,top_db,top_table,top_table_score,pack_token_budget\n")

            from collections import Counter
            err_counter = Counter()
            n_parse_ok = 0; n_schema_valid = 0; n_dry_ok = 0; n_plan_ok = 0
            n_total = 0; n_family_A_chosen = 0; n_family_B_chosen = 0

            for task in tasks:
                n_total += 1
                tid = task.get("instance_id") or task.get("id") or task.get("question_id") or f"t{n_total}"
                alias = task.get("db") or task.get("db_id") or ""
                question = task.get("question") or task.get("instruction") or ""
                ek = task.get("external_knowledge") or ""
                trace = {"instance_id": tid, "alias": alias, "question": question}
                try:
                    # --- Linker ---
                    link = linker.query(question, alias_filter=alias,
                                          top_columns=80, top_tables=20)
                    pack = sb.build_pack(link, lane="bq", alias=alias,
                                          max_tables=8, max_cols_per_table=22)
                    top_table = pack["tables"][0] if pack["tables"] else None
                    top_db = pack["databases"][0]["name"] if pack["databases"] else ""
                    recall_fh.write(",".join([
                        tid, alias,
                        str(link.n_columns_indexed), str(link.n_tables_indexed),
                        top_db,
                        f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else "",
                        str(top_table["score"]) if top_table else "0",
                        str(pack.get("token_budget_used", 0)),
                    ]) + "\n"); recall_fh.flush()
                    trace["pack_top_table"] = f'{top_table["db"]}.{top_table["schema"]}.{top_table["table"]}' if top_table else None
                    trace["pack_n_tables"] = len(pack["tables"])
                    trace["pack_n_columns"] = sum(len(t["columns"]) for t in pack["tables"])
                    trace["pack_token_budget"] = pack.get("token_budget_used", 0)

                    # --- Planner ---
                    plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
                    plan_res = _v18_plan(plan_prompt, pack)
                    plan = plan_res.get("plan")
                    val = plan_res.get("validation")
                    plan_valid = bool(val and getattr(val, "ok", False))
                    if plan_valid: n_plan_ok += 1
                    trace["plan_attempts"] = plan_res.get("attempts")
                    trace["plan_validation_ok"] = plan_valid
                    trace["plan_validation_reasons"] = list(getattr(val, "reasons", [])) if val else []
                    trace["plan_raw"] = plan_res.get("raw", "")[:1500]

                    # --- Candidate factory ---
                    cands = cf.emit_candidates(question, pack, plan, external_knowledge=ek,
                                                  lane="bq", _gen_fn=_gen_emitter)
                    trace["n_candidates"] = len(cands)

                    # --- Selector ---
                    sel = cs.select(cands, pack, do_dry_run=not no_execute)
                    chosen = sel.get("chosen") or {}
                    chosen_sql = chosen.get("sql", "")
                    if chosen.get("parse_ok"): n_parse_ok += 1
                    if chosen.get("schema_valid"): n_schema_valid += 1
                    if chosen.get("dry_run_ok"): n_dry_ok += 1
                    chosen_family = chosen.get("family", "?")
                    if chosen_family == "A": n_family_A_chosen += 1
                    if chosen_family == "B": n_family_B_chosen += 1
                    trace["evals"] = sel.get("evals")
                    trace["chosen_family"] = chosen_family

                    pred_rec = {"instance_id": tid, "sql": chosen_sql,
                                  "chosen_family": chosen_family}
                    preds_fh.write(json.dumps(pred_rec) + "\n"); preds_fh.flush()

                    err_class = chosen.get("error_class") or ("ok" if chosen.get("parse_ok") else "none")
                    err_counter[err_class] += 1
                except Exception as exc:
                    trace["error_type"] = type(exc).__name__
                    trace["error"] = str(exc)[:400]
                    trace["traceback"] = traceback.format_exc()[:1500]
                    pred_rec = {"instance_id": tid, "sql": "", "error": trace["error_type"]}
                    preds_fh.write(json.dumps(pred_rec) + "\n"); preds_fh.flush()
                    err_counter[trace["error_type"]] += 1
                traces_fh.write(json.dumps(trace, default=str) + "\n"); traces_fh.flush()

            preds_fh.close(); traces_fh.close(); recall_fh.close()

            with open(metrics_p, "w") as mfh:
                mfh.write("metric,value\n")
                mfh.write(f"n,{n_total}\n")
                mfh.write(f"plan_validation_ok,{n_plan_ok}\n")
                mfh.write(f"chosen_schema_valid,{n_schema_valid}\n")
                mfh.write(f"parse_ok,{n_parse_ok}\n")
                mfh.write(f"execute_ok,{n_dry_ok}\n")
                mfh.write(f"chosen_family_A,{n_family_A_chosen}\n")
                mfh.write(f"chosen_family_B,{n_family_B_chosen}\n")
            with open(error_p, "w") as efh:
                efh.write("error_class,count\n")
                for k, v in err_counter.most_common():
                    efh.write(f"{k},{v}\n")
            with open(out_dir / "readout.md", "w", encoding="utf-8") as rfh:
                rfh.write(f"# Spider2-Lite-BQ v18 — `{run_id}`\n\n")
                rfh.write("| metric | value | rate |\n|---|---:|---:|\n")
                def _r(n,d):
                    return "0.0%" if d==0 else f"{n/d*100:.1f}%"
                rfh.write(f"| n_total | {n_total} | — |\n")
                rfh.write(f"| plan_validation_ok | {n_plan_ok} | {_r(n_plan_ok,n_total)} |\n")
                rfh.write(f"| chosen_schema_valid | {n_schema_valid} | {_r(n_schema_valid,n_total)} |\n")
                rfh.write(f"| parse_ok | {n_parse_ok} | {_r(n_parse_ok,n_total)} |\n")
                rfh.write(f"| execute_ok (BQ dry_run) | {n_dry_ok} | {_r(n_dry_ok,n_total)} |\n")
                rfh.write(f"| chosen_family_A (deterministic) | {n_family_A_chosen} | {_r(n_family_A_chosen,n_total)} |\n")
                rfh.write(f"| chosen_family_B (Coder-7B direct) | {n_family_B_chosen} | {_r(n_family_B_chosen,n_total)} |\n")
                rfh.write("\n## Error taxonomy\n\n| error_class | count |\n|---|---:|\n")
                for k, v in err_counter.most_common():
                    rfh.write(f"| `{k}` | {v} |\n")
            with open(out_dir / "_DONE", "w") as df:
                df.write(json.dumps({
                    "n_total": n_total, "plan_ok": n_plan_ok,
                    "schema_valid": n_schema_valid, "parse_ok": n_parse_ok,
                    "execute_ok": n_dry_ok,
                    "family_A_chosen": n_family_A_chosen,
                    "family_B_chosen": n_family_B_chosen,
                    "ts": time.time()}))
        except Exception as exc:
            with open(out_dir / "_FAILED", "w") as ff:
                ff.write(json.dumps({"error_type": type(exc).__name__,
                                       "error": str(exc)[:400],
                                       "traceback": traceback.format_exc()[:2000],
                                       "ts": time.time()}))

    threading.Thread(target=_runner, daemon=True).start()
    return {"run_id": run_id, "out_dir": str(out_dir), "started": True}


def v18_bq_status(run_id):
    out_dir = RUNS_BASE / run_id
    if not out_dir.is_dir():
        return {"run_id": run_id, "exists": False}
    s = {"run_id": run_id, "exists": True,
         "started": (out_dir/"_STARTED").is_file(),
         "done":    (out_dir/"_DONE").is_file(),
         "failed":  (out_dir/"_FAILED").is_file()}
    pf = out_dir/"predictions.jsonl"
    s["n_predictions"] = sum(1 for _ in open(pf, encoding="utf-8")) if pf.is_file() else 0
    if (out_dir/"_DONE").is_file():
        s["summary"] = json.loads((out_dir/"_DONE").read_text())
    if (out_dir/"_FAILED").is_file():
        s["failure"] = json.loads((out_dir/"_FAILED").read_text())
    return s
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--run-id', default=None)
    ap.add_argument('--no-execute', action='store_true', default=False)
    ap.add_argument('--planner', default='qwen3_coder_30b_bf16')
    ap.add_argument('--emitter', default='qwen2_5_coder_7b')
    args = ap.parse_args()
    run_id = args.run_id or f'lite_bq_v18_pilot{args.limit}_{int(time.time())}'

    invocation = (f'\nresult = start_v18_bq_bg(limit={args.limit!r}, run_id={run_id!r}, '
                   f'no_execute={args.no_execute!r}, '
                   f'planner_alias={args.planner!r}, emitter_alias={args.emitter!r})\n'
                   "import json as _j\nprint('===STARTED===')\nprint(_j.dumps(result))\nprint('===STARTED_END===')\n")
    print(f'Kicking off v18 BQ pilot in BG  planner={args.planner}  emitter={args.emitter}  limit={args.limit}  run_id={run_id}')
    t0 = time.time()
    r = bridge_exec(RUNNER_TEMPLATE + invocation, timeout=60)
    out = r.get('stdout', '')
    if '===STARTED===' not in out:
        print('NO_START; tail:\n', out[-2000:]); return 2
    started = json.loads(out.split('===STARTED===\n', 1)[1].split('\n===STARTED_END===', 1)[0])
    print(f'  started: {started}')

    poll_code = (f'\n_st = v18_bq_status({run_id!r})\n'
                  "import json as _j\nprint('===STATUS===')\nprint(_j.dumps(_st))\nprint('===STATUS_END===')\n")
    last = -1
    state = None
    print('Polling Drive every 30s ...')
    for poll_i in range(360):
        time.sleep(30)
        try:
            r2 = bridge_exec(RUNNER_TEMPLATE + poll_code, timeout=30)
        except Exception as exc:
            print(f'  poll_err: {type(exc).__name__}'); continue
        out2 = r2.get('stdout', '')
        if '===STATUS===' not in out2: continue
        state = json.loads(out2.split('===STATUS===\n', 1)[1].split('\n===STATUS_END===', 1)[0])
        n = state.get('n_predictions', 0)
        if n != last or poll_i % 5 == 0:
            elapsed = int(time.time() - t0)
            print(f'  [{elapsed:5}s] preds={n} done={state.get("done")} failed={state.get("failed")}')
            last = n
        if state.get('done') or state.get('failed'): break
    wall = time.time() - t0
    if not state or not state.get('done'):
        print(f'\nNOT DONE after {wall:.1f}s; state: {state}')
        return 1

    # Pull artifacts
    out_dir_drive = state.get('out_dir') or f'/content/drive/MyDrive/diploma_plan_sql/outputs/spider2_lite/runs/{run_id}'
    local_runs_dir = REPO / 'outputs' / 'spider2_lite' / 'runs' / run_id
    local_runs_dir.mkdir(parents=True, exist_ok=True)
    pull_code = (
        "import os, base64, json\n"
        f"D = {out_dir_drive!r}\nfiles={{}}\n"
        "for f in sorted(os.listdir(D)):\n"
        "    p = os.path.join(D, f)\n"
        "    if os.path.isfile(p) and os.path.getsize(p) < 8_000_000:\n"
        "        with open(p, 'rb') as fh:\n"
        "            files[f] = base64.b64encode(fh.read()).decode()\n"
        "print('===FILES==='); print(json.dumps(files)); print('===FILES_END===')\n"
    )
    r3 = bridge_exec(pull_code, timeout=120)
    out3 = r3.get('stdout', '')
    if '===FILES===' in out3:
        b = json.loads(out3.split('===FILES===\n', 1)[1].split('\n===FILES_END===', 1)[0])
        for fn, data in b.items():
            (local_runs_dir / fn).write_bytes(base64.b64decode(data))
        print(f'pulled {len(b)} files to {local_runs_dir.relative_to(REPO).as_posix()}')
        pred = local_runs_dir / 'predictions.jsonl'
        if pred.is_file():
            canon = REPO / 'outputs' / 'predictions' / f'spider2_lite_bq_v18_{run_id}_predictions.jsonl'
            canon.parent.mkdir(parents=True, exist_ok=True)
            canon.write_bytes(pred.read_bytes())
            print(f'canonical: {canon.relative_to(REPO).as_posix()}')

    summary = state.get('summary')
    print(f'\nSUMMARY: {summary}')
    print(f'WALL:    {wall:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
