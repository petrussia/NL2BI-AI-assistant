"""run_spider2_sequential_v24 — Phase 24 single-benchmark orchestrator.

Strict rules:
  1. Acquire `outputs/runtime/gpu_inference.lock` BEFORE any inference work.
  2. ONE benchmark per invocation; ONE BG thread inside that benchmark.
  3. Refuse FULL launch if pilot50 metrics file does not show
     `chosen_schema_valid >= 0.60` AND `execute_ok >= 0.50`.
  4. Snow / DBT NOT supported in Phase 24 (use Phase 25+ once Snow auth
     is fixed and DBT v2 governed agent is built).

Local launcher pattern (mirrors `run_spider2_v18_bq_pilot.py`):
  - Sends a self-contained runner template to the bridge via `/exec`.
  - The template runs as a single Python thread on the bridge kernel.
  - On bridge it acquires the same Drive lock (the lock lives on Drive,
    not local FS, so a local launcher and a bridge runner share state).

Usage:
  python tools/run_spider2_sequential_v24.py --benchmark lite_bq --pilot50
  python tools/run_spider2_sequential_v24.py --benchmark lite_bq --full
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRIDGE_FILE = REPO / 'tools' / '.bridge_url'

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def bridge_url() -> str:
    return BRIDGE_FILE.read_text(encoding='utf-8').strip().rstrip('/')


def bridge_exec(code: str, timeout: int = 90) -> dict:
    payload = json.dumps({'code': code}).encode('utf-8')
    req = urllib.request.Request(bridge_url() + '/exec', data=payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


# ---------- Self-contained bridge-side runner template -----------------

RUNNER_TEMPLATE = r'''
import os, sys, json, time, traceback, gc, threading
from pathlib import Path

DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
LITE_JSONL = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
BQ_CATALOG = DRV / "outputs/cache/spider2_bq_live_catalog_v18.jsonl"
RUNS_BASE  = DRV / "outputs/spider2_lite/runs"
EVAL_DIR   = DRV / "repo/src/evaluation"
LOCK_DIR   = DRV / "outputs/runtime"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))


def _serialize_lock():
    """Single threading.Lock around all model.generate calls inside this run.
    Prevents BG-thread races even if a future refactor introduces helpers
    that schedule async work."""
    g = globals()
    if g.get('_PHASE24_GEN_LOCK') is None:
        g['_PHASE24_GEN_LOCK'] = threading.Lock()
    return g['_PHASE24_GEN_LOCK']


def _gen(tok, mdl, prof, prompt, max_new):
    """Serialized generate; restores _gen even if v23 stubs replaced it."""
    LOCK = _serialize_lock()
    with LOCK:
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
    import structured_plan_v18 as sp
    raw = ""
    last_plan = None
    last_val = None
    cur_prompt = prompt
    retry_used = False
    for attempt in range(1, max_attempts + 1):
        raw = _gen_planner(cur_prompt)
        try:
            cand = sp.parse_plan(raw)
        except Exception:
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
              "attempts": max_attempts, "retry_used": retry_used}


def _aquire_lock(run_id):
    """Acquire Drive lock OR return error."""
    from gpu_lock_v24 import GPULock
    lock_path = LOCK_DIR / 'gpu_inference.lock'
    lock = GPULock(lock_path)
    res = lock.acquire(run_id)
    return lock, res


def _check_pilot50_gate(metrics_path):
    """Read pilot50 metrics CSV; return (gate_passed, sv_rate, exec_rate)."""
    if not metrics_path.is_file():
        return False, None, None
    sv = exec_ok = None
    n = None
    for line in metrics_path.read_text(encoding="utf-8").splitlines():
        if "," not in line: continue
        k, v = line.split(",", 1)
        try: vi = int(v)
        except Exception: continue
        if k == "n": n = vi
        elif k == "chosen_schema_valid": sv = vi
        elif k == "execute_ok": exec_ok = vi
    if not n: return False, None, None
    sv_r = sv / n if sv is not None else 0.0
    ex_r = exec_ok / n if exec_ok is not None else 0.0
    return (sv_r >= 0.60 and ex_r >= 0.50), sv_r, ex_r


def start_v24_lite_bq_bg(run_id, *, mode="pilot50", limit=None):
    """Phase 24 sequential Lite-BQ runner. mode in {"pilot50", "full"}."""
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Acquire lock
    lock, lock_res = _aquire_lock(run_id)
    if not lock_res.get("acquired"):
        return {"started": False, "lock_failure": lock_res}

    started_p = out_dir / "_STARTED"
    started_p.write_text(json.dumps({"run_id": run_id, "mode": mode,
                                       "phase": 24, "ts": time.time()}))

    def _runner():
        try:
            import schema_linking_v18 as sl
            import schema_pack_builder_v18 as sb
            import structured_plan_v18 as sp
            import spider2_candidate_factory_v18 as cf
            import candidate_selector_v18 as cs
            import bigquery_engine_compat_v24 as bqcompat

            # Refresh CUDA cache before start
            import torch
            gc.collect(); torch.cuda.empty_cache()

            all_tasks = []
            with open(LITE_JSONL, encoding="utf-8") as fh:
                for ln in fh:
                    if ln.strip(): all_tasks.append(json.loads(ln))
            BQ_BASE = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery"
            bq_aliases = set(os.listdir(BQ_BASE)) if BQ_BASE.is_dir() else set()
            bq_tasks = [t for t in all_tasks
                          if t.get("db", "") in bq_aliases or t.get("db_id", "") in bq_aliases]
            tasks = bq_tasks if limit is None else bq_tasks[:limit]
            print(f"v24 BQ tasks selected: {len(tasks)} of {len(bq_tasks)}", flush=True)

            catalog_cols = sl.load_catalog_jsonl(BQ_CATALOG, "bq")
            print(f"v24 catalog cols: {len(catalog_cols)}", flush=True)
            linker = sl.SchemaLinker(catalog_cols)

            preds_p = out_dir / "predictions.jsonl"
            traces_p = out_dir / "traces.jsonl"
            recall_p = out_dir / "schema_linking_recall.csv"
            metrics_p = out_dir / "metrics.csv"
            error_p = out_dir / "error_taxonomy.csv"
            rewrite_stats_p = out_dir / "engine_rewrite_stats.csv"
            family_breakdown_p = out_dir / "family_breakdown.csv"
            progress_p = out_dir / "progress.json"
            preds_fh = open(preds_p, "w", encoding="utf-8")
            traces_fh = open(traces_p, "w", encoding="utf-8")
            recall_fh = open(recall_p, "w", encoding="utf-8")
            recall_fh.write("instance_id,alias,n_columns_indexed,n_tables_indexed,top_db,top_table,top_table_score,pack_token_budget\n")

            from collections import Counter
            err_counter = Counter()
            family_counter = Counter()
            rewrite_counter = Counter()  # tracks rewrite types fired
            rewrite_helpful_counter = Counter()  # tracks when rewrite turned dry_run F→T
            n_parse_ok = 0; n_schema_valid = 0; n_dry_ok = 0; n_plan_ok = 0
            n_total = 0
            t_start = time.time()

            for ti, task in enumerate(tasks):
                n_total += 1
                tid = task.get("instance_id") or task.get("id") or f"t{n_total}"
                alias = task.get("db") or task.get("db_id") or ""
                question = task.get("question") or task.get("instruction") or ""
                ek = task.get("external_knowledge") or ""
                trace = {"instance_id": tid, "alias": alias, "question": question}
                t_task = time.time()
                try:
                    link = linker.query(question, alias_filter=alias,
                                          top_columns=80, top_tables=20)
                    pack = sb.build_pack(link, lane="bq", alias=alias,
                                          max_tables=8, max_cols_per_table=22,
                                          all_catalog_cols=catalog_cols)
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

                    plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
                    plan_res = _v18_plan(plan_prompt, pack)
                    plan = plan_res.get("plan")
                    val = plan_res.get("validation")
                    plan_valid = bool(val and getattr(val, "ok", False))
                    if plan_valid: n_plan_ok += 1
                    trace["plan_validation_ok"] = plan_valid

                    cands = cf.emit_candidates(question, pack, plan, external_knowledge=ek,
                                                  lane="bq", _gen_fn=_gen_emitter)
                    trace["n_candidates_initial"] = len(cands)

                    # Phase 24 STAGE A4: emit a parallel "rewritten" variant for
                    # each candidate whose SQL changes after engine-compat rewrite.
                    # Append AFTER originals so selector tie-break prefers original.
                    augmented = list(cands)
                    rewrites_emitted = []
                    for c in cands:
                        sql = c.get("sql") or ""
                        if not sql: continue
                        rew, log = bqcompat.rewrite_for_bq(sql)
                        if rew != sql:
                            augmented.append({
                                "family": f'{c.get("family", "?")}_v24',
                                "sql_raw": rew, "sql": rew,
                                "meta": {**(c.get("meta") or {}),
                                            "rewrite_of": c.get("family"),
                                            "rewrites_applied": log}})
                            rewrites_emitted.extend(log)
                            for entry in log:
                                rewrite_counter[entry.split(":")[0]] += 1
                    trace["n_candidates_total"] = len(augmented)
                    trace["rewrites_emitted"] = rewrites_emitted

                    sel = cs.select(augmented, pack, do_dry_run=True)
                    chosen = sel.get("chosen") or {}
                    chosen_sql = chosen.get("sql", "")
                    if chosen.get("parse_ok"): n_parse_ok += 1
                    if chosen.get("schema_valid"): n_schema_valid += 1
                    if chosen.get("dry_run_ok"): n_dry_ok += 1
                    chosen_family = chosen.get("family", "?")
                    family_counter[chosen_family] += 1
                    trace["evals"] = sel.get("evals")
                    trace["chosen_family"] = chosen_family

                    # Track rewrite-helpfulness: did the rewritten variant win
                    # dry_run when the corresponding original failed?
                    if chosen_family.endswith("_v24") and chosen.get("dry_run_ok"):
                        # find the original same-family-letter candidate's eval
                        orig_letter = chosen_family.replace("_v24", "")
                        evals = sel.get("evals") or []
                        orig_dry = next((e.get("dry_run_ok") for e in evals
                                            if e.get("family") == orig_letter), None)
                        if orig_dry is False:
                            rewrite_helpful_counter[chosen_family] += 1

                    pred_rec = {"instance_id": tid, "sql": chosen_sql,
                                  "chosen_family": chosen_family, "lane": "bq",
                                  "schema_valid": chosen.get("schema_valid"),
                                  "parse_ok": chosen.get("parse_ok"),
                                  "dry_run_ok": chosen.get("dry_run_ok"),
                                  "rewrites_emitted": rewrites_emitted}
                    preds_fh.write(json.dumps(pred_rec) + "\n"); preds_fh.flush()

                    err_class = chosen.get("error_class") or ("ok" if (chosen.get("parse_ok") and chosen.get("dry_run_ok")) else "none")
                    err_counter[err_class] += 1
                except Exception as exc:
                    trace["error_type"] = type(exc).__name__
                    trace["error"] = str(exc)[:400]
                    trace["traceback"] = traceback.format_exc()[:1500]
                    pred_rec = {"instance_id": tid, "sql": "", "lane": "bq",
                                  "error": trace["error_type"]}
                    preds_fh.write(json.dumps(pred_rec) + "\n"); preds_fh.flush()
                    err_counter[trace["error_type"]] += 1

                trace["task_wall_sec"] = round(time.time() - t_task, 2)
                traces_fh.write(json.dumps(trace, default=str) + "\n"); traces_fh.flush()

                if (n_total % 5) == 0:
                    gc.collect(); torch.cuda.empty_cache()

                with open(progress_p, "w") as pfh:
                    pfh.write(json.dumps({
                        "n_total": n_total, "n_target": len(tasks),
                        "plan_ok": n_plan_ok, "schema_valid": n_schema_valid,
                        "parse_ok": n_parse_ok, "execute_ok": n_dry_ok,
                        "family_counts": dict(family_counter),
                        "rewrite_counts": dict(rewrite_counter),
                        "rewrite_helpful": dict(rewrite_helpful_counter),
                        "err_top": err_counter.most_common(8),
                        "wall_sec": round(time.time() - t_start, 1),
                        "last_task": tid,
                    }, default=str))

            preds_fh.close(); traces_fh.close(); recall_fh.close()

            with open(metrics_p, "w") as mfh:
                mfh.write("metric,value\n")
                mfh.write(f"n,{n_total}\n")
                mfh.write(f"plan_validation_ok,{n_plan_ok}\n")
                mfh.write(f"chosen_schema_valid,{n_schema_valid}\n")
                mfh.write(f"parse_ok,{n_parse_ok}\n")
                mfh.write(f"execute_ok,{n_dry_ok}\n")
                for fam, c in family_counter.most_common():
                    mfh.write(f"chosen_family_{fam},{c}\n")
            with open(error_p, "w") as efh:
                efh.write("error_class,count\n")
                for k, v in err_counter.most_common():
                    efh.write(f"{k},{v}\n")
            with open(rewrite_stats_p, "w") as rfh:
                rfh.write("rewrite_kind,emitted_count,helpful_count\n")
                for k, v in rewrite_counter.most_common():
                    helpful = rewrite_helpful_counter.get("A_v24", 0) if k != "noop" else 0
                    rfh.write(f"{k},{v},{helpful}\n")
            with open(family_breakdown_p, "w") as fbfh:
                fbfh.write("family,chosen_count\n")
                for fam, c in family_counter.most_common():
                    fbfh.write(f"{fam},{c}\n")

            def _r(n,d): return "0.0%" if d==0 else f"{n/d*100:.1f}%"
            with open(out_dir / "readout.md", "w", encoding="utf-8") as rfh:
                rfh.write(f"# Spider2-Lite-BQ v24 — `{run_id}` (Phase 24 sequential)\n\n")
                rfh.write("| metric | value | rate |\n|---|---:|---:|\n")
                rfh.write(f"| n_total | {n_total} | — |\n")
                rfh.write(f"| plan_validation_ok | {n_plan_ok} | {_r(n_plan_ok,n_total)} |\n")
                rfh.write(f"| chosen_schema_valid | {n_schema_valid} | {_r(n_schema_valid,n_total)} |\n")
                rfh.write(f"| parse_ok | {n_parse_ok} | {_r(n_parse_ok,n_total)} |\n")
                rfh.write(f"| execute_ok (BQ dry_run) | {n_dry_ok} | {_r(n_dry_ok,n_total)} |\n")
                rfh.write("\n## Family choice\n\n| family | count | rate |\n|---|---:|---:|\n")
                for fam, c in family_counter.most_common():
                    rfh.write(f"| `{fam}` | {c} | {_r(c, n_total)} |\n")
                rfh.write("\n## Engine rewrite emit + helpful counts\n\n| kind | emitted | helpful (won dry_run) |\n|---|---:|---:|\n")
                for k, v in rewrite_counter.most_common():
                    rfh.write(f"| `{k}` | {v} | — |\n")
                rfh.write(f"\nTotal rewrite-helpful (any kind): {sum(rewrite_helpful_counter.values())}\n")
                rfh.write("\n## Error taxonomy\n\n| error_class | count |\n|---|---:|\n")
                for k, v in err_counter.most_common():
                    rfh.write(f"| `{k}` | {v} |\n")

            with open(out_dir / "_DONE", "w") as df:
                df.write(json.dumps({
                    "n_total": n_total, "plan_ok": n_plan_ok,
                    "schema_valid": n_schema_valid, "parse_ok": n_parse_ok,
                    "execute_ok": n_dry_ok,
                    "family_counts": dict(family_counter),
                    "rewrite_helpful": dict(rewrite_helpful_counter),
                    "wall_sec": round(time.time() - t_start, 1),
                    "ts": time.time()}))
        except Exception as exc:
            with open(out_dir / "_FAILED", "w") as ff:
                ff.write(json.dumps({"error_type": type(exc).__name__,
                                      "error": str(exc)[:400],
                                      "traceback": traceback.format_exc()[:2000],
                                      "ts": time.time()}))
        finally:
            # Always release lock + free GPU
            try:
                from gpu_lock_v24 import GPULock, free_gpu_cache
                lock_path = LOCK_DIR / 'gpu_inference.lock'
                GPULock(lock_path).release()
                free_gpu_cache()
            except Exception:
                pass

    threading.Thread(target=_runner, daemon=True).start()
    return {"run_id": run_id, "out_dir": str(out_dir), "started": True}


def v24_status(run_id):
    out_dir = RUNS_BASE / run_id
    if not out_dir.is_dir():
        return {"run_id": run_id, "exists": False}
    s = {"run_id": run_id, "exists": True,
         "started": (out_dir/"_STARTED").is_file(),
         "done": (out_dir/"_DONE").is_file(),
         "failed": (out_dir/"_FAILED").is_file()}
    pf = out_dir/"predictions.jsonl"
    s["n_predictions"] = sum(1 for _ in open(pf, encoding="utf-8")) if pf.is_file() else 0
    if (out_dir/"progress.json").is_file():
        try: s["progress"] = json.loads((out_dir/"progress.json").read_text())
        except Exception: pass
    if (out_dir/"_DONE").is_file():
        s["summary"] = json.loads((out_dir/"_DONE").read_text())
    if (out_dir/"_FAILED").is_file():
        s["failure"] = json.loads((out_dir/"_FAILED").read_text())
    return s


globals()['_PHASE24_START_LITE_BQ'] = start_v24_lite_bq_bg
globals()['_PHASE24_STATUS_V24'] = v24_status
globals()['_PHASE24_PILOT50_GATE'] = _check_pilot50_gate
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--benchmark', choices=['lite_bq'], required=True)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument('--pilot50', action='store_true')
    grp.add_argument('--full', action='store_true')
    ap.add_argument('--run-id', default=None)
    args = ap.parse_args()

    if args.benchmark != 'lite_bq':
        print('Phase 24 supports only --benchmark lite_bq. '
                'Snow / DBT deferred per session policy.')
        return 2

    if args.full:
        run_id = args.run_id or 'lite_bq_full_v24'
        mode = 'full'; limit = None
    else:
        run_id = args.run_id or 'lite_bq_v24_pilot50'
        mode = 'pilot50'; limit = 50

    print(f'Phase 24 sequential launcher → run_id={run_id} mode={mode} limit={limit}')

    # FULL gate check before kicking off
    if args.full:
        gate_check_code = (
            RUNNER_TEMPLATE +
            "\n_p = RUNS_BASE / 'lite_bq_v24_pilot50' / 'metrics.csv'\n"
            "_g, _sv, _ex = _check_pilot50_gate(_p)\n"
            "import json as _j\nprint('===GATE===')\n"
            "print(_j.dumps({'passed': _g, 'sv_rate': _sv, 'exec_rate': _ex,\n"
            "                  'metrics_path_exists': _p.is_file()}))\nprint('===GATE_END===')\n")
        r = bridge_exec(gate_check_code, timeout=60)
        out = r.get('stdout', '')
        if '===GATE===' not in out:
            print(f'GATE check failed: no marker; tail:\n{out[-1000:]}'); return 1
        gate = json.loads(out.split('===GATE===\n', 1)[1].split('\n===GATE_END===', 1)[0])
        print(f'  gate: {gate}')
        if not gate.get('passed'):
            print(f'  REFUSE FULL launch — gate not cleared '
                  f'(sv={gate.get("sv_rate")}, exec={gate.get("exec_rate")}).')
            return 3

    # Launch
    invocation = (
        f'\nresult = start_v24_lite_bq_bg(run_id={run_id!r}, '
        f'mode={mode!r}, limit={limit!r})\n'
        "import json as _j\nprint('===STARTED===')\n"
        "print(_j.dumps(result))\nprint('===STARTED_END===')\n")
    r = bridge_exec(RUNNER_TEMPLATE + invocation, timeout=60)
    out = r.get('stdout', '')
    if '===STARTED===' not in out:
        print(f'NO_START; tail:\n{out[-2000:]}'); return 2
    started = json.loads(out.split('===STARTED===\n', 1)[1].split('\n===STARTED_END===', 1)[0])
    print(f'  started: {started}')
    if not started.get('started'):
        print(f'  Lock acquisition failed: {started.get("lock_failure")}')
        return 4

    poll_code = (
        RUNNER_TEMPLATE +
        f'\n_st = v24_status({run_id!r})\n'
        "import json as _j\nprint('===STATUS===')\nprint(_j.dumps(_st))\n"
        "print('===STATUS_END===')\n")

    last = -1
    state = None
    print('Polling Drive every 30s (max 480 polls = 4h)...')
    t0 = time.time()
    for poll_i in range(480):
        time.sleep(30)
        try:
            r2 = bridge_exec(poll_code, timeout=30)
        except Exception as exc:
            print(f'  poll_err: {type(exc).__name__}'); continue
        out2 = r2.get('stdout', '')
        if '===STATUS===' not in out2: continue
        state = json.loads(out2.split('===STATUS===\n', 1)[1].split('\n===STATUS_END===', 1)[0])
        n = state.get('n_predictions', 0)
        if n != last or poll_i % 5 == 0:
            elapsed = int(time.time() - t0)
            print(f'  [{elapsed:5}s] preds={n} done={state.get("done")} '
                  f'failed={state.get("failed")}')
            last = n
        if state.get('done') or state.get('failed'): break
    wall = time.time() - t0
    if not state or not state.get('done'):
        print(f'\nNOT DONE after {wall:.1f}s; state: {state}'); return 1

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

    summary = state.get('summary')
    print(f'\nSUMMARY: {summary}')
    print(f'WALL:    {wall:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
