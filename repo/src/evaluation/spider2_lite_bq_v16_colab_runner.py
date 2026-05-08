"""spider2_lite_bq_v16_colab_runner — BQ pilot with constrained repair.

Pipeline per task:
  1. Build catalog (lazy, BQ from Drive resource).
  2. Generate 3 candidates (C0_direct, C1_retrieval, C2_cte).
  3. Normalize (BQ-isms + 4-part collapse — same as v12).
  4. **Apply BQ nested rewrite v16** (GA4 event_params EXISTS+UNNEST).
  5. **Validator** (struct/wildcard/4-part-aware — same as v12).
  6. If `schema_invalid`: **catalog-constrained substitution v16** —
     for each unknown identifier, try top-1 catalog suggestion via
     identifier_mapper_v16 multi-signal scoring; build replacement
     variants; re-validate; pick first schema-valid variant.
  7. Send schema-valid winner to BQ dry_run + (capped) live execute.

Logs per task: applied_nested_rewrites, applied_substitutions,
schema_valid_before_subst, schema_valid_after_subst, dry_run_ok,
execute_ok, bytes_processed/billed.

Async pattern: start_v16_bq_bg + v16_bq_status.
"""
from __future__ import annotations


def _self_contained_runner_template() -> str:
    return r'''
# ---------- Colab-side BQ v16 pilot runner (constrained repair) ----------
import os, sys, json, re, time, traceback, threading
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
LITE_JSONL = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
BQ_RES_BASE = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery"
SA_PATH = str(DRV / "secrets/spider2_bq_sa.json")
RUNS_BASE = DRV / "outputs/spider2_lite/runs"


# ---- v12 BQ-isms postprocessor + 4-part collapse ----
_DATE_BAD_RE = re.compile(r'\bDATE\s*\(\s*["\'](\d{4})(\d{2})(\d{2})["\']\s*\)', re.IGNORECASE)
_DATE_DASH_RE = re.compile(r'\bDATE\s*\(\s*["\'](\d{4})-(\d{2})-(\d{2})["\']\s*\)', re.IGNORECASE)
_TRY_CAST_RE = re.compile(r'\bTRY_CAST\b', re.IGNORECASE)
_DATEDIFF_SF_RE = re.compile(r'\bDATEDIFF\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\s*\)', re.IGNORECASE)
_BT_4PART_RE = re.compile(r'`([A-Za-z][\w-]*)\.([A-Za-z][\w-]*)\.([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)`')


def _bq_normalize(sql):
    if not sql: return {"sql": "", "applied_fixes": []}
    cur = sql; applied = []
    out, n = _DATE_BAD_RE.subn(
        lambda m: f"DATE '{m.group(1)}-{m.group(2)}-{m.group(3)}'", cur)
    if n: applied.append("date_yyyymmdd_to_typed"); cur = out
    out, n = _DATE_DASH_RE.subn(
        lambda m: f"DATE '{m.group(1)}-{m.group(2)}-{m.group(3)}'", cur)
    if n: applied.append("date_dashed_to_typed"); cur = out
    out, n = _TRY_CAST_RE.subn("SAFE_CAST", cur)
    if n: applied.append("try_cast_to_safe_cast"); cur = out
    out, n = _DATEDIFF_SF_RE.subn(
        lambda m: f"DATE_DIFF({m.group(3).strip()}, {m.group(2).strip()}, {m.group(1).upper()})",
        cur)
    if n: applied.append("datediff_to_date_diff"); cur = out
    n_4 = 0
    def _4repl(m):
        nonlocal n_4
        s1, s2, s3, s4 = m.group(1), m.group(2), m.group(3), m.group(4)
        if s1.lower() == s2.lower():
            n_4 += 1
            return f'`{s1}.{s3}.{s4}`'
        return m.group(0)
    out = _BT_4PART_RE.sub(_4repl, cur)
    if n_4: applied.append(f"bq_4part_collapsed:{n_4}"); cur = out
    return {"sql": cur, "applied_fixes": applied}


# ---- v16 BQ nested rewrite (event_params EXISTS+UNNEST) ----
def _has_unnest_for(col, sql):
    return bool(re.search(rf'UNNEST\s*\(\s*{re.escape(col)}\s*\)', sql, re.IGNORECASE))


def _bq_nested_rewrite(sql):
    if not sql or 'event_params' not in sql.lower():
        return {"sql": sql, "applied": []}
    if _has_unnest_for("event_params", sql):
        return {"sql": sql, "applied": []}
    applied = []
    pair_re = re.compile(
        r"event_params\.key\s*=\s*'([^']+)'\s+AND\s+"
        r"event_params\.value\.(int_value|string_value|float_value|double_value)"
        r"\s*([=!<>]+|>|<|>=|<=)\s*([^\s)]+)",
        re.IGNORECASE)
    def _repl(m):
        applied.append("ga4_event_params_exists")
        return (f"EXISTS (SELECT 1 FROM UNNEST(event_params) ep "
                f"WHERE ep.key = '{m.group(1)}' AND ep.value.{m.group(2)} {m.group(3)} {m.group(4)})")
    out = pair_re.sub(_repl, sql)
    return {"sql": out, "applied": applied}


def _extract_sql(raw):
    if not raw: return ""
    m = re.search(r"```sql\s*\n([\s\S]*?)```", raw, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r"```\s*\n([\s\S]*?)```", raw)
    if m:
        cand = m.group(1).strip()
        if any(kw in cand.upper() for kw in ("SELECT", "WITH")): return cand
    upper = raw.upper()
    for tag in ("WITH ", "SELECT "):
        i = upper.find(tag)
        if i >= 0: return raw[i:].strip()
    return raw.strip()


# ---- Catalog (same as v12) ----
def _build_db_catalog(db, *, max_tables_per_dataset=80):
    db_dir = BQ_RES_BASE / db
    datasets = {}
    if not db_dir.is_dir():
        return {"datasets": datasets, "tables_flat": {}}
    for ds_dir in sorted(db_dir.iterdir()):
        if not ds_dir.is_dir(): continue
        ds_name = ds_dir.name
        tables = {}
        n = 0
        for jf in sorted(ds_dir.glob("*.json")):
            try: d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception: continue
            if not isinstance(d, dict): continue
            tname = (d.get("table_name") or jf.stem).strip()
            cols = d.get("column_names") or []
            types = d.get("column_types") or []
            descs = d.get("column_descriptions") or [""] * len(cols)
            samples = d.get("sample_rows") or []
            if not tname or not cols: continue
            tfn = d.get("table_fullname", "")
            project = ""
            if tfn and "." in tfn:
                parts = tfn.split(".")
                if len(parts) >= 3: project = parts[0]
            col_metas = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else "STRING") or "STRING"
                cd = (descs[i] if isinstance(descs, list) and i < len(descs) else "")
                sv = []
                for r in samples[:5]:
                    if isinstance(r, dict) and cn in r:
                        v = r[cn]
                        if v is None: continue
                        s = str(v)[:60]
                        if s and s not in sv: sv.append(s)
                col_metas.append({"name": str(cn), "type": str(dt),
                                   "description": str(cd)[:200], "samples": sv})
            fq = f"{project}.{ds_name}.{tname}" if project else f"{db}.{ds_name}.{tname}"
            tables[tname] = {"fq_name": fq, "project": project,
                              "dataset": ds_name, "table": tname,
                              "description": str(d.get("description") or "")[:300],
                              "columns": col_metas}
            n += 1
            if n >= max_tables_per_dataset: break
        if tables:
            datasets[ds_name] = tables
    flat = {}
    for ds, tbls in datasets.items():
        for tname, td in tbls.items():
            flat[tname.upper()] = td
    return {"datasets": datasets, "tables_flat": flat}


def _retrieve_keys(catalog, question, k=6):
    flat = catalog["tables_flat"]
    if not flat: return []
    q = re.findall(r"[A-Za-z][A-Za-z0-9_]+", question.lower())
    qset = {t for t in q if len(t) > 2}
    if not qset: return list(flat.values())[:k]
    scored = []
    for td in flat.values():
        toks = {td["table"].lower()}
        for c in td["columns"]:
            toks.add(c["name"].lower())
            toks.update(re.findall(r"[A-Za-z][A-Za-z0-9_]+", (c.get("description") or "").lower()))
        toks = {x for x in toks if len(x) > 2}
        overlap = len(qset & toks) / max(1, len(qset | toks))
        if overlap > 0:
            scored.append((overlap, td))
    scored.sort(key=lambda x: -x[0])
    return [td for _, td in scored[:k]] or list(flat.values())[:k]


def _render_schema(tables, max_cols=22):
    out = ["# BigQuery schema. Use canonical `project.dataset.table` form. Use ONLY listed identifiers."]
    for t in tables:
        out.append(f"\nTABLE: `{t['fq_name']}`")
        if t.get("description"):
            out.append(f"  -- {t['description'][:160]}")
        for c in t["columns"][:max_cols]:
            line = f"  {c['name']}: {c['type']}"
            if c.get("description"): line += f"  -- {c['description'][:90]}"
            if c.get("samples"): line += f"  /* eg. {', '.join(c['samples'][:2])} */"
            out.append(line)
        if len(t["columns"]) > max_cols:
            out.append(f"  -- ...{len(t['columns']) - max_cols} more columns")
    return "\n".join(out)


_BQ_RULES = """You generate BigQuery Standard SQL. STRICT rules:
1. Use ONLY tables/columns from the SCHEMA. Do NOT invent identifiers.
2. Backtick fully-qualified `project.dataset.table` — NEVER repeat the project segment.
3. Date/time: DATE_DIFF(end, start, DAY); DATE_TRUNC(d, DAY); typed-date `DATE 'YYYY-MM-DD'`.
4. Cast: SAFE_CAST(x AS T). No TRY_CAST.
5. Repeated/struct: UNNEST(arr) AS f, then f.field. STRUCT access via dot.
6. Wildcard tables: FROM `project.dataset.events_*` WHERE _TABLE_SUFFIX BETWEEN '...' AND '...'.
7. Single statement. SQL only.
"""


def _direct_prompt(q, schema):
    return f"{_BQ_RULES}\n\n{schema}\n\nQuestion: {q}\nSQL:"

def _retrieval_prompt(q, schema):
    return (f"{_BQ_RULES}\n\nUse ONLY tables/columns below.\n\n{schema}\n\n"
            f"Question: {q}\nSQL:")

def _cte_prompt(q, schema):
    return (f"{_BQ_RULES}\n\nDecompose into named CTEs.\n\n{schema}\n\n"
            f"Question: {q}\nSQL:")


# ---- Validator (v12 — struct/wildcard/4part-aware) ----
_BQ_RESERVED_PSEUDO_COLS = {"_TABLE_SUFFIX", "_PARTITIONTIME", "_PARTITIONDATE"}


def _levenshtein(a, b):
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    a, b = a.lower(), b.lower()
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[j-1] + 1, prev[j] + 1, prev[j-1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _norm_id(s): return re.sub(r'[\W_]+', '', (s or '').lower())


def _score_replacement(needle, candidate, *, question="", evidence=""):
    if not candidate: return 0.0
    if _norm_id(needle) == _norm_id(candidate): return 1.0
    s = 0.0
    lev = _levenshtein(needle, candidate)
    max_len = max(len(needle), len(candidate))
    if max_len: s += 0.4 * max(0, 1 - lev / max_len)
    nt = {t.lower() for t in re.split(r'[\W_]+', needle or '') if t}
    ct = {t.lower() for t in re.split(r'[\W_]+', candidate or '') if t}
    if nt or ct:
        s += 0.25 * (len(nt & ct) / max(1, len(nt | ct)))
    qct = {t.lower() for t in re.split(r'[\W_]+', (question or '') + ' ' + (evidence or '')) if t}
    if qct & ct: s += 0.20
    return min(1.0, s)


def _suggest_table(unknown_table, catalog, *, question="", evidence="", top_k=3):
    flat = catalog["tables_flat"]
    scored = [(_score_replacement(unknown_table, t,
                                         question=question, evidence=evidence), t)
              for t in flat.keys()]
    scored.sort(reverse=True)
    return [t for sc, t in scored[:top_k] if sc > 0]


def _suggest_column(unknown_col, qual, catalog, selected, *,
                          question="", evidence="", top_k=3):
    flat = catalog["tables_flat"]
    candidate_tables = list(flat.keys())
    if qual:
        candidate_tables = [t for t in candidate_tables if t == qual.upper()]
    elif selected:
        sel_tn = {t.upper().split(".")[-1] for t in selected}
        candidate_tables = [t for t in candidate_tables if t in sel_tn]
    if not candidate_tables:
        candidate_tables = list(flat.keys())
    scored = []
    for tname in candidate_tables:
        for c in flat[tname]["columns"]:
            sc = _score_replacement(unknown_col, c["name"],
                                          question=question, evidence=evidence)
            if sc > 0:
                scored.append((sc, tname, c["name"]))
    scored.sort(reverse=True)
    return [(t, c) for sc, t, c in scored[:top_k]]


def _build_alias_map(tree):
    try: from sqlglot import exp
    except ImportError: return {}
    am = {}
    try:
        for t in tree.find_all(exp.Table):
            tbl = (t.name or "").upper()
            if not tbl: continue
            alias_node = t.args.get("alias")
            alias_str = None
            if alias_node:
                a = alias_node.args.get("this") or alias_node
                alias_str = getattr(a, "name", None)
            if alias_str: am[alias_str.lower()] = tbl
            am[tbl.lower()] = tbl
    except Exception: pass
    return am


def _wildcard_match(tbl_pattern, available):
    if "*" not in tbl_pattern: return False
    prefix = tbl_pattern.upper().rstrip("*").rstrip("_") + "_"
    return any(t.upper().startswith(prefix) for t in available)


def _validate_sql(sql, catalog, db, selected_tables=None):
    res = {"schema_valid": False, "unknown_tables": [], "unknown_columns": [],
            "false_positive_struct_cols": [], "wildcard_resolved": [],
            "notes": []}
    if not sql.strip():
        res["notes"].append("empty_sql"); return res
    flat = catalog["tables_flat"]
    avail = list(flat.keys())
    selected_set = ({t["table"].upper() for t in (selected_tables or [])}
                       or set(avail))

    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        res["notes"].append("sqlglot_unavailable"); return res
    try:
        tree = sqlglot.parse_one(sql, read="bigquery")
    except Exception as exc:
        res["notes"].append(f"sqlglot_parse_failed:{type(exc).__name__}")
        return res

    for t in tree.find_all(exp.Table):
        try:
            tbl = (t.name or "").upper()
            if not tbl: continue
            if tbl in {n.upper() for n in avail}: continue
            if "*" in tbl or tbl.endswith("_"):
                if _wildcard_match(tbl, avail):
                    res["wildcard_resolved"].append({"pattern": tbl}); continue
            res["unknown_tables"].append({"table": tbl,
                                              "suggestions": _suggest_table(tbl, catalog)})
        except Exception: continue

    col_by_table = {n: {c["name"].upper() for c in flat[n]["columns"]} for n in flat}
    struct_cols = {}
    for tname, td in flat.items():
        sc = set()
        for c in td["columns"]:
            tt = (c.get("type") or "").upper()
            if any(k in tt for k in ("STRUCT", "RECORD", "REPEATED", "ARRAY")):
                sc.add(c["name"].upper())
            if c["name"].lower() in ("event_params", "user_properties", "items",
                                          "device", "geo", "traffic_source",
                                          "ecommerce", "user_ltv", "hits", "totals"):
                sc.add(c["name"].upper())
        struct_cols[tname] = sc

    alias_map = _build_alias_map(tree)
    all_struct_q = set()
    for tname in selected_set:
        all_struct_q |= struct_cols.get(tname, set())

    for c in tree.find_all(exp.Column):
        try:
            cname = (c.name or "").upper()
            if not cname: continue
            qual = ((c.args.get("table") and c.args["table"].name) or "").upper()
            if cname in _BQ_RESERVED_PSEUDO_COLS: continue
            if qual and qual in all_struct_q:
                res["false_positive_struct_cols"].append({"qual": qual, "col": cname})
                continue
            if qual in ("VALUE", "INT_VALUE", "STRING_VALUE", "FLOAT_VALUE",
                          "DOUBLE_VALUE", "PARAMS"):
                res["false_positive_struct_cols"].append({"qual": qual, "col": cname})
                continue
            if qual:
                resolved = alias_map.get(qual.lower(), qual)
                tbls = [resolved]
            else:
                tbls = list(selected_set)
            found = any(cname in col_by_table.get(tt, set()) for tt in tbls)
            if not found:
                sugg = _suggest_column(cname, qual, catalog, selected_tables or [])
                # Convert to "table.col" string form for memo
                sugg_str = [f"{t}.{cc}" for t, cc in sugg]
                res["unknown_columns"].append({"col": cname, "qual": qual,
                                                   "suggestions": sugg_str,
                                                   "suggest_pairs": sugg})
        except Exception: continue

    res["schema_valid"] = (not res["unknown_tables"]) and (not res["unknown_columns"])
    return res


def _render_validation_report(val):
    lines = []
    if val["unknown_tables"]:
        lines.append("UNKNOWN_TABLES:")
        for ent in val["unknown_tables"][:10]:
            lines.append(f"  - {ent['table']}  suggestions={ent.get('suggestions', [])}")
    if val["unknown_columns"]:
        lines.append("UNKNOWN_COLUMNS:")
        for ent in val["unknown_columns"][:10]:
            lines.append(f"  - {ent['col']} (qual={ent['qual'] or '-'})  suggestions={ent.get('suggestions', [])}")
    if not lines: lines.append("OK")
    return "\n".join(lines)


# ---- v16 constrained substitution ----
def _apply_substitutions(sql, replacements):
    cur = sql
    applied = []
    for old, new in replacements:
        if not old or not new or old.upper() == new.upper(): continue
        pat = re.compile(rf'\b{re.escape(old)}\b', re.IGNORECASE)
        out, n = pat.subn(new, cur)
        if n > 0:
            applied.append({"old": old, "new": new, "count": n})
            cur = out
    return cur, applied


def _constrained_repair(sql, validation, catalog, db, selected_tables,
                              *, question="", evidence="", max_attempts=3):
    """Try top-1 substitution per unknown ident, rebuild SQL, revalidate.
    If first attempt still invalid, try top-2, etc.

    Returns dict with applied list, final_sql, final_validation, attempts.
    """
    attempts_log = []
    cur_sql = sql
    cur_val = validation
    for attempt in range(1, max_attempts + 1):
        replacements = []
        for ent in cur_val.get("unknown_tables", []):
            sug = ent.get("suggestions") or []
            if not sug: continue
            replacements.append((ent["table"], sug[min(attempt - 1, len(sug) - 1)]))
        for ent in cur_val.get("unknown_columns", []):
            sug = ent.get("suggestions") or []
            if not sug: continue
            # suggestion format is "TABLE.COL"
            top = sug[min(attempt - 1, len(sug) - 1)]
            new_col = top.split(".")[-1]
            replacements.append((ent["col"], new_col))
        if not replacements:
            attempts_log.append({"attempt": attempt, "n_replacements": 0,
                                       "schema_valid": cur_val["schema_valid"]})
            break
        new_sql, applied = _apply_substitutions(cur_sql, replacements)
        new_val = _validate_sql(new_sql, catalog, db, selected_tables)
        attempts_log.append({"attempt": attempt, "n_replacements": len(applied),
                                  "applied": applied,
                                  "schema_valid": new_val["schema_valid"]})
        cur_sql = new_sql
        cur_val = new_val
        if new_val["schema_valid"]:
            break
    return {"final_sql": cur_sql, "final_validation": cur_val,
              "attempts": attempts_log,
              "succeeded": cur_val["schema_valid"]}


# ---- Model + BQ ----
def _ensure_model():
    g = globals()
    if g.get("_GEN_READY"): return
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


def _gen(prompt, max_new=800):
    g = globals(); import torch
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


def _bq_dry(sql):
    g = globals(); bq = g["bigquery"]
    try:
        cfg = bq.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = g["_BQ_CLIENT"].query(sql, job_config=cfg)
        _ = job.total_bytes_processed
        return {"ok": True, "bytes_processed": job.total_bytes_processed}
    except Exception as exc:
        msg = str(exc)
        et = ("syntax" if "Syntax error" in msg
              else "object_not_found" if ("Not found" in msg or "Unrecognized" in msg or "not found" in msg)
              else type(exc).__name__)
        return {"ok": False, "error_type": et, "error_message": msg[:400]}


def _bq_exec(sql, *, max_rows=100, cap_bytes=1*1024**3):
    g = globals(); bq = g["bigquery"]; t0 = time.time()
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
                  "elapsed_ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        msg = str(exc)
        et = ("bytes_billed_exceeded" if "bytes" in msg.lower() and "billed" in msg.lower()
              else "object_not_found" if "Not found" in msg or "not found" in msg
              else "syntax" if "Syntax error" in msg
              else type(exc).__name__)
        return {"ok": False, "error_type": et, "error_message": msg[:400],
                  "elapsed_ms": int((time.time() - t0) * 1000)}


def run_pilot_v16(limit=10, *, run_id=None, max_rows=100,
                       cap_bytes_billed=1*1024**3, no_execute=False,
                       max_new_sql=800, max_new_cte=1100):
    if run_id is None:
        run_id = f"lite_bq_v16_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"
    cand_path = out_dir / "candidates.jsonl"
    trace_path = out_dir / "traces.jsonl"
    print(f"RUN_ID={run_id}", flush=True)

    rows = []
    with LITE_JSONL.open(encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            d = json.loads(ln)
            iid = str(d.get("instance_id") or "")
            if iid.startswith("sf") or iid.startswith("local"): continue
            rows.append(d)
            if limit and limit > 0 and len(rows) >= limit: break
    print(f"TASKS={len(rows)}", flush=True)

    _ensure_model()
    _ensure_bq()

    metrics = Counter(); err_tax = Counter(); src_break = Counter()
    fp_count = Counter()
    catalogs = {}

    for i, it in enumerate(rows, 1):
        iid = it["instance_id"]; db = it["db"]; q = it.get("question", "")
        ek = it.get("external_knowledge") or ""
        t_task = time.time()
        print(f"\n[{i}/{len(rows)}] {iid} db={db} ...", flush=True)

        try:
            if db not in catalogs:
                catalogs[db] = _build_db_catalog(db)
            cat = catalogs[db]
            if not cat["tables_flat"]:
                row = {"instance_id": iid, "db": db, "lane": "A_bq",
                        "mode": "blocked_no_catalog",
                        "sql": "", "schema_valid": False,
                        "error_type": "catalog_missing",
                        "wall_time_s": round(time.time() - t_task, 2)}
                with pred_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                metrics["n"] += 1; err_tax["catalog_missing"] += 1
                continue

            selected = _retrieve_keys(cat, q, k=6)
            schema_text = _render_schema(selected, max_cols=22)

            cands = []
            for src, builder, mn in (
                ("C0_direct", _direct_prompt, max_new_sql),
                ("C1_retrieval", _retrieval_prompt, max_new_sql),
                ("C2_cte", _cte_prompt, max_new_cte),
            ):
                try:
                    raw = _gen(builder(q, schema_text), max_new=mn)
                    sql_raw = _extract_sql(raw)
                except Exception as exc:
                    sql_raw = ""
                # Step 4: normalize (BQ-isms + 4-part collapse)
                norm = _bq_normalize(sql_raw)
                sql = norm["sql"]
                # Step 5: BQ nested rewrite (event_params)
                rewrite = _bq_nested_rewrite(sql)
                if rewrite["applied"]:
                    sql = rewrite["sql"]
                # Step 6: validate
                val = _validate_sql(sql, cat, db, selected)
                # Step 7: constrained repair if invalid
                repair_attempted = False
                repair_succeeded = False
                repair_log = []
                if not val["schema_valid"]:
                    rep = _constrained_repair(sql, val, cat, db, selected,
                                                    question=q, evidence=ek)
                    repair_attempted = True
                    repair_succeeded = rep["succeeded"]
                    repair_log = rep["attempts"]
                    if rep["succeeded"]:
                        sql = rep["final_sql"]
                        val = rep["final_validation"]
                if val.get("false_positive_struct_cols"):
                    fp_count["struct_field_access"] += len(val["false_positive_struct_cols"])
                if val.get("wildcard_resolved"):
                    fp_count["wildcard_table"] += len(val["wildcard_resolved"])
                cands.append({"source": src, "sql": sql, "original_sql": sql_raw,
                                "applied_norm": norm["applied_fixes"],
                                "applied_nested_rewrite": rewrite["applied"],
                                "repair_attempted": repair_attempted,
                                "repair_succeeded": repair_succeeded,
                                "repair_log": repair_log,
                                "validation": val})

            valid_cands = [c for c in cands if c["validation"]["schema_valid"]]
            if valid_cands:
                chosen = max(valid_cands,
                                key=lambda c: 0.10 if c.get("repair_succeeded")
                                else (0.05 if c["source"] == "C1_retrieval" else 0.0))
            else:
                chosen = min(cands, key=lambda c: len(c["validation"].get("unknown_tables", []))
                                + len(c["validation"].get("unknown_columns", [])))

            verifier = {"parses": False, "executable": None,
                         "rows_count": 0, "bytes_processed": 0, "bytes_billed": 0,
                         "error_type": "", "error_message": ""}
            if chosen["validation"]["schema_valid"]:
                dr = _bq_dry(chosen["sql"])
                if dr["ok"]:
                    verifier["parses"] = True
                    verifier["bytes_processed"] = dr.get("bytes_processed", 0)
                    if not no_execute:
                        er = _bq_exec(chosen["sql"], max_rows=max_rows, cap_bytes=cap_bytes_billed)
                        verifier["executable"] = bool(er["ok"])
                        verifier["rows_count"] = er.get("row_count", 0)
                        verifier["bytes_processed"] = er.get("bytes_processed", verifier["bytes_processed"])
                        verifier["bytes_billed"] = er.get("bytes_billed", 0)
                        verifier["elapsed_ms"] = er.get("elapsed_ms")
                        if not er["ok"]:
                            verifier["error_type"] = er["error_type"]
                            verifier["error_message"] = er["error_message"]
                else:
                    verifier["error_type"] = dr["error_type"]
                    verifier["error_message"] = dr["error_message"]
            else:
                verifier["error_type"] = "schema_invalid"
                verifier["error_message"] = _render_validation_report(chosen["validation"])

            metrics["n"] += 1
            if chosen["validation"]["schema_valid"]: metrics["chosen_schema_valid"] += 1
            if verifier["parses"]: metrics["parse_ok"] += 1
            if verifier["executable"]: metrics["execute_ok"] += 1
            if chosen.get("repair_succeeded"): metrics["constrained_repair_helpful"] += 1
            if chosen.get("applied_nested_rewrite"): metrics["nested_rewrite_applied"] += 1
            et = verifier["error_type"] or "none"
            err_tax[et] += 1
            src_break[chosen["source"]] += 1

            wall = round(time.time() - t_task, 2)
            pred = {"instance_id": iid, "db": db, "lane": "A_bq",
                      "sql": chosen["sql"], "original_sql": chosen.get("original_sql", ""),
                      "final_source": chosen["source"],
                      "schema_valid": chosen["validation"]["schema_valid"],
                      "constrained_repair_attempted": chosen.get("repair_attempted", False),
                      "constrained_repair_helpful": chosen.get("repair_succeeded", False),
                      "applied_nested_rewrite": chosen.get("applied_nested_rewrite", []),
                      "parses": verifier["parses"],
                      "executable": verifier.get("executable"),
                      "rows_count": verifier.get("rows_count", 0),
                      "bytes_processed": verifier.get("bytes_processed", 0),
                      "bytes_billed": verifier.get("bytes_billed", 0),
                      "error_type": et,
                      "error_message": verifier["error_message"][:400] if verifier["error_message"] else "",
                      "applied_norm": chosen.get("applied_norm", []),
                      "n_unknown_tables": len(chosen["validation"]["unknown_tables"]),
                      "n_unknown_columns": len(chosen["validation"]["unknown_columns"]),
                      "n_struct_fp_skipped": len(chosen["validation"].get("false_positive_struct_cols", [])),
                      "n_wildcard_resolved": len(chosen["validation"].get("wildcard_resolved", [])),
                      "wall_time_s": wall,
                      "utc": datetime.now(timezone.utc).isoformat()}
            with pred_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(pred, ensure_ascii=False) + "\n")
            with cand_path.open("a", encoding="utf-8") as f:
                for c in cands:
                    f.write(json.dumps({"instance_id": iid, "source": c["source"],
                                           "schema_valid": c["validation"]["schema_valid"],
                                           "applied_nested_rewrite": c.get("applied_nested_rewrite", []),
                                           "repair_succeeded": c.get("repair_succeeded", False),
                                           "n_unknown_tables": len(c["validation"]["unknown_tables"]),
                                           "n_unknown_columns": len(c["validation"]["unknown_columns"])},
                                          ensure_ascii=False) + "\n")
            with trace_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"instance_id": iid, "db": db,
                                       "repair_log_for_chosen": chosen.get("repair_log", []),
                                       "selected_tables": [t["fq_name"] for t in selected],
                                       "utc": datetime.now(timezone.utc).isoformat()},
                                      ensure_ascii=False) + "\n")
            print(f"  schema_valid={pred['schema_valid']} parse={pred['parses']} "
                    f"exec={pred['executable']} ut={pred['n_unknown_tables']} "
                    f"uc={pred['n_unknown_columns']} repair_helpful={pred['constrained_repair_helpful']} "
                    f"nested={pred['applied_nested_rewrite']} err={et} wall={wall}s", flush=True)
        except Exception as exc:
            # Per task: log failure but don't crash the batch
            print(f"  TASK_EXC {iid}: {type(exc).__name__}: {exc}", flush=True)
            row = {"instance_id": iid, "db": db, "lane": "A_bq",
                    "mode": "task_exception",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:400],
                    "wall_time_s": round(time.time() - t_task, 2)}
            with pred_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            metrics["n"] += 1; err_tax[f"task_exc_{type(exc).__name__}"] += 1

    import csv
    with (out_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        for k in ("n", "chosen_schema_valid", "parse_ok", "execute_ok",
                    "constrained_repair_helpful", "nested_rewrite_applied"):
            w.writerow([k, metrics[k]])
        w.writerow(["false_positive_struct_skips", fp_count["struct_field_access"]])
        w.writerow(["wildcard_table_resolves", fp_count["wildcard_table"]])
    with (out_dir / "error_taxonomy.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["error_type", "count"])
        for k, v in err_tax.most_common(): w.writerow([k, v])
    with (out_dir / "source_breakdown.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["final_source", "count"])
        for k, v in src_break.most_common(): w.writerow([k, v])

    n = max(1, metrics["n"])
    md = [f"# Spider2-Lite-BQ v16 — run `{run_id}` (constrained repair + nested rewrite)", "",
            "## Aggregate metrics", "",
            "| metric | value | rate |", "|---|---:|---:|",
            f"| n_total | {metrics['n']} | — |",
            f"| chosen_schema_valid | {metrics['chosen_schema_valid']} | {(metrics['chosen_schema_valid']/n)*100:.1f}% |",
            f"| parse_ok | {metrics['parse_ok']} | {(metrics['parse_ok']/n)*100:.1f}% |",
            f"| execute_ok | {metrics['execute_ok']} | {(metrics['execute_ok']/n)*100:.1f}% |",
            f"| constrained_repair_helpful | {metrics['constrained_repair_helpful']} | — |",
            f"| nested_rewrite_applied | {metrics['nested_rewrite_applied']} | — |",
            f"| struct_field_skips (FP avoided) | {fp_count['struct_field_access']} | — |",
            f"| wildcard_resolves | {fp_count['wildcard_table']} | — |",
            "", "## Error taxonomy", "", "| error_type | count |", "|---|---:|"]
    for k, v in err_tax.most_common(15): md.append(f"| `{k}` | {v} |")
    md += ["", "## Source breakdown", "", "| source | count |", "|---|---:|"]
    for k, v in src_break.most_common(): md.append(f"| `{k}` | {v} |")
    (out_dir / "readout.md").write_text("\n".join(md), encoding="utf-8")

    (out_dir / "_DONE").write_text(json.dumps({
        "run_id": run_id, "n_total": metrics["n"],
        "chosen_schema_valid": metrics["chosen_schema_valid"],
        "parse_ok": metrics["parse_ok"], "execute_ok": metrics["execute_ok"],
        "constrained_repair_helpful": metrics["constrained_repair_helpful"],
        "nested_rewrite_applied": metrics["nested_rewrite_applied"],
        "struct_fp_skips": fp_count["struct_field_access"],
        "wildcard_resolves": fp_count["wildcard_table"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    print(f"\nDONE run_id={run_id}", flush=True)
    return {"run_id": run_id, "out_dir": str(out_dir)}


def start_v16_bq_bg(limit=10, *, run_id=None, max_rows=100,
                          cap_bytes_billed=1*1024**3, no_execute=False):
    if run_id is None:
        run_id = f"lite_bq_v16_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_STARTED").write_text(json.dumps({"run_id": run_id, "limit": limit,
                                                       "ts": datetime.now(timezone.utc).isoformat()}),
                                            encoding="utf-8")
    def _runner():
        try:
            run_pilot_v16(limit=limit, run_id=run_id, max_rows=max_rows,
                              cap_bytes_billed=cap_bytes_billed, no_execute=no_execute)
        except Exception as exc:
            (out_dir / "_FAILED").write_text(json.dumps({
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
                "traceback": traceback.format_exc()[:4000],
                "ts": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
    t = threading.Thread(target=_runner, name=f"bq_v16_{run_id}", daemon=True)
    t.start()
    return {"run_id": run_id, "out_dir": str(out_dir), "started": True}


def v16_bq_status(run_id):
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
        try: state["summary"] = json.loads((out_dir / "_DONE").read_text(encoding="utf-8"))
        except Exception: pass
    if state["failed"]:
        try: state["failure"] = json.loads((out_dir / "_FAILED").read_text(encoding="utf-8"))
        except Exception: pass
    return state
'''
