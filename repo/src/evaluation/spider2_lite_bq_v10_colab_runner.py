"""spider2_lite_bq_v10_colab_runner — Colab-side batch runner for BQ lane.

Designed to be sent through `/exec` ONCE per pilot, not per-task. Inside
the Colab kernel it:
  1. Lazily loads Coder-7B (or reuses if already in globals).
  2. Lazily builds the BQ Client.
  3. Iterates the requested slice of `bq*` Spider2-Lite tasks.
  4. For each: builds the schema index from the local Drive copy, runs
     three candidates (C0_direct + C1_retrieval + C2_cte) via in-process
     LLM, normalizes BQ-isms, dry_runs each candidate, picks the best
     parsing one, executes it (capped bytes), and appends one JSONL row
     to a Drive predictions file.
  5. Bounded repair on failed dry_run.
  6. Logs bytes_processed, bytes_billed, retry_count, error_class.

This sidesteps the per-task Cloudflare HTTP wave: one /exec call covers
N tasks, all I/O lives inside the Colab process.

Usage from local launcher:
    code_str = open("repo/src/evaluation/spider2_lite_bq_v10_colab_runner.py").read()
    code_str += f"\\nrun_pilot(limit={limit}, run_id={run_id!r}, max_repair_rounds=1)\\n"
    bridge_exec(code_str, timeout=1800)
"""
from __future__ import annotations


def _self_contained_runner_template() -> str:
    """Returns the Colab-side runner as a single Python string. Caller
    injects it into /exec along with a `run_pilot(...)` call."""
    return r'''
# ---------- Colab-side BQ pilot runner (v10) ----------
import os, sys, json, re, time, traceback
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
LITE_JSONL = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
BQ_RES_BASE = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery"
SA_PATH = str(DRV / "secrets/spider2_bq_sa.json")
RUNS_BASE = DRV / "outputs/spider2_lite/runs"

# --- BQ-isms postprocessor (BQ-friendly form) ---
def _bq_normalize(sql: str) -> dict:
    if not sql: return {"sql": "", "applied_fixes": []}
    cur = sql
    applied = []
    # DATE("YYYYMMDD") -> DATE 'YYYY-MM-DD'
    out, n = re.subn(r'\bDATE\s*\(\s*["\'](\d{4})(\d{2})(\d{2})["\']\s*\)',
                       lambda m: f"DATE '{m.group(1)}-{m.group(2)}-{m.group(3)}'", cur)
    if n: applied.append("date_yyyymmdd_to_typed"); cur = out
    out, n = re.subn(r'\bDATE\s*\(\s*["\'](\d{4})-(\d{2})-(\d{2})["\']\s*\)',
                       lambda m: f"DATE '{m.group(1)}-{m.group(2)}-{m.group(3)}'", cur)
    if n: applied.append("date_dashed_to_typed"); cur = out
    # TRY_CAST -> SAFE_CAST (Snowflake-ism in BQ context)
    out, n = re.subn(r'\bTRY_CAST\b', "SAFE_CAST", cur)
    if n: applied.append("try_cast_to_safe_cast"); cur = out
    # DATEDIFF(PART, a, b) -> DATE_DIFF(b, a, PART)
    out, n = re.subn(r'\bDATEDIFF\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\s*\)',
                       lambda m: f"DATE_DIFF({m.group(3).strip()}, {m.group(2).strip()}, {m.group(1).upper()})",
                       cur)
    if n: applied.append("datediff_to_date_diff"); cur = out
    return {"sql": cur, "applied_fixes": applied}


# --- SQL extractor (preserves WITH) ---
def _extract_sql_v10(raw: str) -> str:
    if not raw: return ""
    txt = raw
    # Look for ```sql ... ``` fence
    m = re.search(r"```sql\s*\n([\s\S]*?)```", txt, re.IGNORECASE)
    if m: return m.group(1).strip()
    # Look for any code fence
    m = re.search(r"```\s*\n([\s\S]*?)```", txt)
    if m:
        cand = m.group(1).strip()
        if any(kw in cand.upper() for kw in ("SELECT", "WITH")):
            return cand
    # Heuristic: take from first SELECT/WITH
    upper = txt.upper()
    for tag in ("WITH ", "SELECT "):
        i = upper.find(tag)
        if i >= 0:
            return txt[i:].strip()
    return txt.strip()


# --- Schema index from local JSONs ---
def _build_bq_schema_index(db: str, max_tables: int = 80) -> list:
    """Returns list of {fq_name, table, dataset, project, description, columns}."""
    db_dir = BQ_RES_BASE / db
    out = []
    if not db_dir.is_dir():
        return out
    for ds_dir in sorted(db_dir.iterdir()):
        if not ds_dir.is_dir(): continue
        dataset = ds_dir.name
        for jf in sorted(ds_dir.glob("*.json")):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict): continue
            tname = (d.get("table_name") or jf.stem).strip()
            cols = d.get("column_names") or []
            types = d.get("column_types") or []
            descs = d.get("column_descriptions") or [""] * len(cols)
            samples = d.get("sample_rows") or []
            if not tname or not cols: continue
            col_metas = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else "STRING") or "STRING"
                cd = (descs[i] if isinstance(descs, list) and i < len(descs) else "")
                sample_vals = []
                for r in samples[:5]:
                    if isinstance(r, dict) and cn in r:
                        v = r[cn]
                        if v is None: continue
                        s = str(v)[:60]
                        if s and s not in sample_vals: sample_vals.append(s)
                col_metas.append({"name": str(cn), "type": str(dt),
                                    "description": str(cd)[:160],
                                    "samples": sample_vals})
            # BQ identifier: use db.dataset.table; fallback to project from
            # table_fullname like `project.dataset.table`
            fq_full = d.get("table_fullname", "")
            project = ""
            if "." in fq_full:
                parts = fq_full.split(".")
                if len(parts) >= 3:
                    project = parts[0]
            out.append({
                "fq_name": f"{project}.{dataset}.{tname}" if project else f"{db}.{dataset}.{tname}",
                "table": tname, "dataset": dataset, "project": project,
                "description": str(d.get("description") or "")[:200],
                "columns": col_metas,
            })
            if len(out) >= max_tables: return out
    return out


def _retrieve_keys(idx: list, question: str, k: int = 6) -> list:
    if not idx: return []
    q = re.findall(r"[A-Za-z][A-Za-z0-9_]+", question.lower())
    qset = {t for t in q if len(t) > 2}
    if not qset:
        return [t["fq_name"] for t in idx[:k]]
    scored = []
    for t in idx:
        toks = set([t["table"].lower()])
        for c in t["columns"]:
            toks.add(c["name"].lower())
            toks.update(re.findall(r"[A-Za-z][A-Za-z0-9_]+", (c.get("description") or "").lower()))
        toks = {x for x in toks if len(x) > 2}
        overlap = len(qset & toks) / max(1, len(qset | toks))
        if overlap > 0:
            scored.append((overlap, t["fq_name"]))
    scored.sort(reverse=True)
    keys = [n for _, n in scored[:k]]
    if not keys: keys = [t["fq_name"] for t in idx[:k]]
    return keys


def _render_subset(idx: list, keys: list, max_cols: int = 22) -> str:
    by_fq = {t["fq_name"]: t for t in idx}
    out = ["-- BigQuery schema. Use canonical `project.dataset.table` form."]
    for k in keys:
        t = by_fq.get(k)
        if not t: continue
        out.append(f"`{t['fq_name']}`")
        if t.get("description"):
            out.append(f"  -- {t['description'][:160]}")
        for c in t["columns"][:max_cols]:
            line = f"  {c['name']} {c['type']}"
            if c.get("description"): line += f"  -- {c['description'][:90]}"
            if c.get("samples"): line += f"  /* eg. {', '.join(c['samples'][:2])} */"
            out.append(line)
        if len(t["columns"]) > max_cols:
            out.append(f"  -- ...{len(t['columns']) - max_cols} more columns")
        out.append("")
    return "\n".join(out)


_BQ_RULES = """You generate BigQuery Standard SQL. Strict rules:

1. Identifiers: backtick fully-qualified `project.dataset.table`. Do NOT use Snowflake DB.SCHEMA.TABLE form.
2. Use ONLY tables and columns from the SCHEMA. Do NOT invent identifiers.
3. Date/time: DATE_DIFF(end, start, DAY); DATE_TRUNC(d, DAY); typed-date literal `DATE 'YYYY-MM-DD'`.
4. Cast: SAFE_CAST(x AS T) for safe coercion (Snowflake's TRY_CAST is forbidden).
5. Repeated fields: UNNEST(arr) AS f, then access f.field. No LATERAL FLATTEN.
6. Wildcard tables OK: FROM `project.dataset.events_*` WHERE _TABLE_SUFFIX BETWEEN '...' AND '...'.
7. Single statement; no semicolons inside; no markdown fence required.
8. Use REGEXP_CONTAINS (NOT REGEXP_LIKE).
"""


def _direct_prompt(question, schema_text):
    return f"{_BQ_RULES}\n\nSCHEMA:\n{schema_text}\n\nQuestion: {question}\nSQL:"

def _retrieval_prompt(question, schema_text):
    return (f"{_BQ_RULES}\n\nUse ONLY the tables/columns below. Do not invent identifiers.\n\n"
            f"SCHEMA:\n{schema_text}\n\nQuestion: {question}\nSQL:")

def _cte_prompt(question, schema_text):
    return (f"{_BQ_RULES}\n\nDecompose into named CTEs.\n\n"
            f"SCHEMA:\n{schema_text}\n\nQuestion: {question}\nSQL:")

def _repair_prompt(question, schema_text, broken_sql, error):
    return (
        "Your previous BigQuery SQL was rejected. Output ONLY the corrected SQL.\n\n"
        f"BIGQUERY RULES:\n{_BQ_RULES}\n\n"
        f"SCHEMA:\n{schema_text}\n\n"
        f"QUESTION: {question}\n\nORIGINAL_SQL:\n{broken_sql}\n\n"
        f"BIGQUERY_ERROR:\n{(error or '')[:600]}\n\nFIXED_SQL:"
    )


def _ensure_model():
    g = globals()
    if g.get("_GEN_READY"):
        return
    print("LOADING_MODEL Qwen/Qwen2.5-Coder-7B-Instruct ...", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct", trust_remote_code=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-Coder-7B-Instruct", torch_dtype=torch.bfloat16,
        device_map="auto", trust_remote_code=True)
    mdl.eval()
    g["_TOK"] = tok; g["_MDL"] = mdl; g["_GEN_READY"] = True
    print("MODEL_READY", flush=True)


def _gen(prompt: str, max_new: int = 800) -> str:
    g = globals()
    import torch
    enc = g["_TOK"].apply_chat_template(
        [{"role": "user", "content": prompt}], return_tensors="pt",
        add_generation_prompt=True, return_dict=True)
    enc = {k: v.to(g["_MDL"].device) for k, v in enc.items()}
    with torch.no_grad():
        out = g["_MDL"].generate(**enc, max_new_tokens=max_new,
                                    do_sample=False,
                                    pad_token_id=g["_TOK"].eos_token_id)
    gen = out[0][enc["input_ids"].shape[1]:]
    return g["_TOK"].decode(gen, skip_special_tokens=True)


def _ensure_bq():
    g = globals()
    if g.get("_BQ_CLIENT") is not None: return
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_PATH
    from google.cloud import bigquery
    g["bigquery"] = bigquery
    g["_BQ_CLIENT"] = bigquery.Client()
    print(f"BQ_CLIENT_PROJECT={g['_BQ_CLIENT'].project}", flush=True)


def _bq_dry_run(sql: str) -> dict:
    g = globals()
    bq = g["bigquery"]
    try:
        cfg = bq.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = g["_BQ_CLIENT"].query(sql, job_config=cfg)
        _ = job.total_bytes_processed
        return {"ok": True, "bytes_processed": job.total_bytes_processed,
                  "query_id": job.job_id}
    except Exception as exc:
        msg = str(exc)
        et = "syntax" if "Syntax error" in msg else (
              "object_not_found" if ("Not found" in msg or "Unrecognized" in msg or "not found" in msg)
              else type(exc).__name__)
        return {"ok": False, "error_type": et,
                  "error_message": msg[:400]}


def _bq_execute(sql: str, *, max_rows: int = 100,
                  cap_bytes: int = 1 * 1024 ** 3) -> dict:
    g = globals()
    bq = g["bigquery"]
    t0 = time.time()
    try:
        cfg = bq.QueryJobConfig(maximum_bytes_billed=cap_bytes,
                                  use_query_cache=False)
        job = g["_BQ_CLIENT"].query(sql, job_config=cfg)
        rs = job.result(max_results=max_rows)
        rows = []
        for r in rs:
            try: rows.append(dict(r))
            except Exception: rows.append(None)
        return {"ok": True, "row_count": len(rows),
                  "bytes_processed": job.total_bytes_processed,
                  "bytes_billed": job.total_bytes_billed or 0,
                  "query_id": job.job_id,
                  "elapsed_ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        msg = str(exc)
        et = ("bytes_billed_exceeded" if "bytes" in msg.lower() and "billed" in msg.lower()
              else "object_not_found" if "Not found" in msg or "not found" in msg
              else "syntax" if "Syntax error" in msg
              else type(exc).__name__)
        return {"ok": False, "error_type": et,
                  "error_message": msg[:400],
                  "elapsed_ms": int((time.time() - t0) * 1000)}


def run_pilot(limit: int = 10, *, run_id: str = None,
                max_repair_rounds: int = 1, max_rows: int = 100,
                cap_bytes_billed: int = 1 * 1024 ** 3,
                max_new_sql: int = 800, max_new_cte: int = 1100):
    """Run BQ pilot of `limit` bq* tasks. All I/O stays in Colab."""
    if run_id is None:
        run_id = f"lite_bq_v10_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"
    cand_path = out_dir / "candidates.jsonl"
    trace_path = out_dir / "traces.jsonl"
    print(f"RUN_ID={run_id}", flush=True)
    print(f"OUT_DIR={out_dir}", flush=True)

    # Load tasks
    rows = []
    with LITE_JSONL.open(encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            d = json.loads(ln)
            iid = str(d.get("instance_id") or "")
            if not (iid.startswith("sf") or iid.startswith("local")):
                rows.append(d)
            if limit and limit > 0 and len(rows) >= limit:
                break
    print(f"TASKS={len(rows)}", flush=True)

    _ensure_model()
    _ensure_bq()

    metrics = Counter()
    err_tax = Counter()
    src_break = Counter()
    cost_rows = []
    schemas_cache = {}

    for i, it in enumerate(rows, 1):
        iid = it["instance_id"]; db = it["db"]; q = it["question"]
        t_task = time.time()
        print(f"\n[{i}/{len(rows)}] {iid} db={db} ...", flush=True)

        # Schema
        if db not in schemas_cache:
            schemas_cache[db] = _build_bq_schema_index(db)
        idx = schemas_cache[db]
        if not idx:
            print(f"  SKIP schema_missing for {db}", flush=True)
            row = {"instance_id": iid, "db": db, "lane": "A_bq",
                    "mode": "blocked_no_schema",
                    "sql": "", "parses": False, "executable": False,
                    "error_type": "schema_missing",
                    "wall_time_s": round(time.time() - t_task, 2),
                    "utc": datetime.now(timezone.utc).isoformat()}
            with pred_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            metrics["n"] += 1
            err_tax["schema_missing"] += 1
            continue

        keys = _retrieve_keys(idx, q, k=6)
        schema_text = _render_subset(idx, keys, max_cols=22)

        # Generate 3 candidates
        cands = []
        for src, builder, mn in (
            ("C0_direct", _direct_prompt, max_new_sql),
            ("C1_retrieval", _retrieval_prompt, max_new_sql),
            ("C2_cte", _cte_prompt, max_new_cte),
        ):
            try:
                raw = _gen(builder(q, schema_text), max_new=mn)
                sql_raw = _extract_sql_v10(raw)
            except Exception as exc:
                sql_raw = ""
                print(f"  gen_err {src}: {type(exc).__name__}", flush=True)
            norm = _bq_normalize(sql_raw)
            sql = norm["sql"]
            ver = _bq_dry_run(sql) if sql else {"ok": False, "error_type": "empty_sql"}
            cands.append({"source": src, "sql": sql, "original_sql": sql_raw,
                            "applied_fixes": norm["applied_fixes"],
                            "verifier": ver})

        # Pick best dry-run-passing; bias C1 > C0 > C2 on ties
        order_bias = {"C1_retrieval": 0.05, "C0_direct": 0.0, "C2_cte": 0.02}
        def score(c):
            v = c["verifier"]
            s = 0.0
            if v.get("ok"): s += 3.0
            s += order_bias.get(c["source"], 0)
            s -= len(c["sql"]) / 8000.0  # prefer shorter when tied
            return s
        chosen = max(cands, key=score)

        # Bounded repair if no candidate passed dry_run
        repair_record = None
        if not chosen["verifier"].get("ok"):
            broken = chosen["sql"] or cands[0]["sql"]
            err = chosen["verifier"].get("error_message") or chosen["verifier"].get("error_type", "")
            for r_n in range(1, max_repair_rounds + 1):
                try:
                    raw = _gen(_repair_prompt(q, schema_text, broken, err), max_new=max_new_sql)
                    new_sql = _extract_sql_v10(raw)
                except Exception as exc:
                    repair_record = {"rounds": r_n, "success": False,
                                       "error": type(exc).__name__}
                    break
                norm = _bq_normalize(new_sql)
                check = _bq_dry_run(norm["sql"]) if norm["sql"] else {"ok": False}
                if check.get("ok"):
                    repaired = {"source": "C3_repaired", "sql": norm["sql"],
                                  "original_sql": new_sql,
                                  "applied_fixes": norm["applied_fixes"],
                                  "verifier": check}
                    cands.append(repaired)
                    chosen = repaired
                    repair_record = {"rounds": r_n, "success": True}
                    break
                broken = norm["sql"] or new_sql
                err = check.get("error_message") or check.get("error_type", "")
                repair_record = {"rounds": r_n, "success": False}

        # Real execute if dry_run passed
        exec_res = None
        if chosen["verifier"].get("ok"):
            exec_res = _bq_execute(chosen["sql"], max_rows=max_rows,
                                       cap_bytes=cap_bytes_billed)

        # Aggregate
        metrics["n"] += 1
        if chosen["verifier"].get("ok"): metrics["parse_ok"] += 1
        if exec_res and exec_res.get("ok"): metrics["execute_ok"] += 1
        et = (chosen["verifier"].get("error_type")
                if not chosen["verifier"].get("ok")
                else (exec_res.get("error_type") if exec_res and not exec_res.get("ok")
                       else "none"))
        err_tax[et or "none"] += 1
        src_break[chosen["source"]] += 1
        if repair_record and repair_record.get("success"):
            metrics["repair_helpful"] += 1

        wall = round(time.time() - t_task, 2)
        pred = {"instance_id": iid, "db": db, "lane": "A_bq",
                  "sql": chosen["sql"], "original_sql": chosen.get("original_sql", ""),
                  "final_source": chosen["source"],
                  "parses": bool(chosen["verifier"].get("ok")),
                  "executable": bool(exec_res and exec_res.get("ok")),
                  "rows_count": (exec_res or {}).get("row_count", 0),
                  "bytes_processed": (exec_res or chosen["verifier"]).get("bytes_processed", 0),
                  "bytes_billed": (exec_res or {}).get("bytes_billed", 0),
                  "elapsed_ms_exec": (exec_res or {}).get("elapsed_ms"),
                  "error_type": et, "error_message":
                       chosen["verifier"].get("error_message", "") if not chosen["verifier"].get("ok")
                       else (exec_res.get("error_message", "") if exec_res and not exec_res.get("ok") else ""),
                  "applied_fixes": chosen.get("applied_fixes", []),
                  "wall_time_s": wall,
                  "utc": datetime.now(timezone.utc).isoformat()}
        with pred_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(pred, ensure_ascii=False) + "\n")
        with cand_path.open("a", encoding="utf-8") as f:
            for c in cands:
                f.write(json.dumps({"instance_id": iid,
                                       "source": c["source"],
                                       "parses": bool(c["verifier"].get("ok")),
                                       "sql_chars": len(c["sql"]),
                                       "applied_fixes": c.get("applied_fixes", []),
                                       "error_type": c["verifier"].get("error_type", "")},
                                      ensure_ascii=False) + "\n")
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"instance_id": iid, "db": db,
                                   "repair_record": repair_record,
                                   "candidates_n": len(cands),
                                   "utc": datetime.now(timezone.utc).isoformat()},
                                  ensure_ascii=False) + "\n")
        cost_rows.append({"instance_id": iid, "db": db, "wall_time_s": wall,
                            "bytes_processed": pred["bytes_processed"],
                            "bytes_billed": pred["bytes_billed"]})
        print(f"  parse={pred['parses']} exec={pred['executable']} "
                f"rows={pred['rows_count']} err={et} fixes={pred['applied_fixes']} "
                f"bytes={pred['bytes_billed']} wall={wall}s", flush=True)

    # Summary CSVs
    import csv
    with (out_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        for k in ("n", "parse_ok", "execute_ok", "repair_helpful"):
            w.writerow([k, metrics[k]])
    with (out_dir / "error_taxonomy.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["error_type", "count"])
        for k, v in err_tax.most_common(): w.writerow([k, v])
    with (out_dir / "source_breakdown.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["final_source", "count"])
        for k, v in src_break.most_common(): w.writerow([k, v])
    with (out_dir / "cost_runtime.csv").open("w", newline="", encoding="utf-8") as f:
        if cost_rows:
            w = csv.DictWriter(f, fieldnames=list(cost_rows[0].keys()))
            w.writeheader()
            for r in cost_rows: w.writerow(r)

    n = max(1, metrics["n"])
    md = [f"# Spider2-Lite BQ v10 — run `{run_id}`", "",
            "## Aggregate metrics (BQ lane only)", "",
            "| metric | value | rate |", "|---|---:|---:|",
            f"| n_total | {metrics['n']} | — |",
            f"| parse_ok | {metrics['parse_ok']} | {(metrics['parse_ok']/n)*100:.1f}% |",
            f"| execute_ok | {metrics['execute_ok']} | {(metrics['execute_ok']/n)*100:.1f}% |",
            f"| repair_helpful | {metrics['repair_helpful']} | — |",
            "", "## Error taxonomy", "", "| error_type | count |", "|---|---:|"]
    for k, v in err_tax.most_common(15): md.append(f"| `{k}` | {v} |")
    md += ["", "## Source breakdown", "", "| source | count |", "|---|---:|"]
    for k, v in src_break.most_common(): md.append(f"| `{k}` | {v} |")
    (out_dir / "readout.md").write_text("\n".join(md), encoding="utf-8")

    # Done marker — local poller looks for this file
    (out_dir / "_DONE").write_text(json.dumps({
        "run_id": run_id, "n_total": metrics["n"],
        "parse_ok": metrics["parse_ok"], "execute_ok": metrics["execute_ok"],
        "repair_helpful": metrics["repair_helpful"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    print(f"\nDONE run_id={run_id}", flush=True)
    print(f"  parse_ok={metrics['parse_ok']}/{metrics['n']} "
            f"execute_ok={metrics['execute_ok']}/{metrics['n']}", flush=True)
    print(f"  out_dir={out_dir}", flush=True)
    return {"run_id": run_id, "out_dir": str(out_dir),
              "n_total": metrics["n"], "parse_ok": metrics["parse_ok"],
              "execute_ok": metrics["execute_ok"]}


def start_pilot_bg(limit: int = 10, *, run_id: str = None,
                       max_repair_rounds: int = 1, max_rows: int = 100,
                       cap_bytes_billed: int = 1 * 1024 ** 3):
    """Launch run_pilot in a daemon thread to avoid Cloudflare 524 edge timeout.
    Returns immediately with the run_id and out_dir; poll via pilot_status."""
    import threading
    if run_id is None:
        run_id = f"lite_bq_v10_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    # Mark started so the local side can verify the thread launched
    (out_dir / "_STARTED").write_text(json.dumps({
        "run_id": run_id, "limit": limit,
        "ts": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    def _runner():
        try:
            run_pilot(limit=limit, run_id=run_id,
                         max_repair_rounds=max_repair_rounds,
                         max_rows=max_rows, cap_bytes_billed=cap_bytes_billed)
        except Exception as exc:
            (out_dir / "_FAILED").write_text(json.dumps({
                "run_id": run_id,
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
                "traceback": traceback.format_exc()[:4000],
                "ts": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
    t = threading.Thread(target=_runner, name=f"pilot_{run_id}", daemon=True)
    t.start()
    return {"run_id": run_id, "out_dir": str(out_dir), "started": True}


def pilot_status(run_id: str) -> dict:
    """Read state of an in-flight pilot. Used by local poller."""
    out_dir = RUNS_BASE / run_id
    if not out_dir.exists():
        return {"run_id": run_id, "exists": False}
    state = {"run_id": run_id, "exists": True,
              "started": (out_dir / "_STARTED").exists(),
              "done": (out_dir / "_DONE").exists(),
              "failed": (out_dir / "_FAILED").exists(),
              "n_predictions": 0}
    pred = out_dir / "predictions.jsonl"
    if pred.exists():
        with pred.open(encoding="utf-8") as f:
            state["n_predictions"] = sum(1 for _ in f)
    if state["done"]:
        try:
            state["summary"] = json.loads((out_dir / "_DONE").read_text(encoding="utf-8"))
        except Exception: pass
    if state["failed"]:
        try:
            state["failure"] = json.loads((out_dir / "_FAILED").read_text(encoding="utf-8"))
        except Exception: pass
    return state
'''
