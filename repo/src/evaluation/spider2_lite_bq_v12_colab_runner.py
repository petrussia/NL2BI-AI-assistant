"""spider2_lite_bq_v12_colab_runner — BQ v11 + validator/normalizer fixes.

Fixes identified from BQ v11 pilot10 root-cause memo:

  1. **Project-doubled 4-part identifiers** like
     `bigquery-public-data.bigquery-public-data.dataset.table` →
     normalizer now collapses repeated project segments BEFORE the
     validator sees them. Same `A.A.B.C` → `A.B.C` shape as Snow's
     4-part-with-duplicated-schema, just at a different position.
  2. **STRUCT / UNNEST nested-field access** — validator no longer
     flags `event_params.key`, `event_params.value.int_value`, etc.
     If the qualifier matches a column name (not a table) on any
     selected table, the column reference is treated as a nested
     field access and skipped.
  3. **Wildcard tables** — `events_*` patterns are matched against
     any catalog table whose name starts with `events_` (case-
     insensitive). `_TABLE_SUFFIX` references in WHERE are not
     flagged as unknown columns.
  4. **Dashed identifiers** parsed correctly via sqlglot BigQuery
     dialect (already works; we just keep raw text intact through the
     normalizer).

Pipeline: same as v11 (Colab batch + 2-round repair) plus the above.
Async pattern preserved.
"""
from __future__ import annotations


def _self_contained_runner_template() -> str:
    return r'''
# ---------- Colab-side BQ v12 pilot runner ----------
import os, sys, json, re, time, traceback, threading
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
LITE_JSONL = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl"
BQ_RES_BASE = DRV / "external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/bigquery"
SA_PATH = str(DRV / "secrets/spider2_bq_sa.json")
RUNS_BASE = DRV / "outputs/spider2_lite/runs"


# ---- BQ-isms postprocessor ----
_DATE_BAD_RE = re.compile(r'\bDATE\s*\(\s*["\'](\d{4})(\d{2})(\d{2})["\']\s*\)', re.IGNORECASE)
_DATE_DASH_RE = re.compile(r'\bDATE\s*\(\s*["\'](\d{4})-(\d{2})-(\d{2})["\']\s*\)', re.IGNORECASE)
_TRY_CAST_RE = re.compile(r'\bTRY_CAST\b', re.IGNORECASE)
_DATEDIFF_SF_RE = re.compile(r'\bDATEDIFF\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\s*\)', re.IGNORECASE)


def _bq_normalize(sql):
    """v12 BQ normalizer — adds project-doubled 4-part collapse."""
    if not sql: return {"sql": "", "applied_fixes": []}
    cur = sql; applied = []

    # Date literal fixes
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

    # NEW v12: collapse project-doubled 4-part inside backticks.
    # Pattern: `A.A.B.C` (with A repeated) → `A.B.C`. Handles dashes.
    BT_4PART_RE = re.compile(r'`([A-Za-z][\w-]*)\.([A-Za-z][\w-]*)\.([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)`')
    n_4 = 0
    def _4repl(m):
        nonlocal n_4
        s1, s2, s3, s4 = m.group(1), m.group(2), m.group(3), m.group(4)
        if s1.lower() == s2.lower():
            n_4 += 1
            return f'`{s1}.{s3}.{s4}`'
        return m.group(0)
    out = BT_4PART_RE.sub(_4repl, cur)
    if n_4: applied.append(f"bq_4part_collapsed:{n_4}"); cur = out

    return {"sql": cur, "applied_fixes": applied}


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


# ---- Catalog ----
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
    out = ["# BigQuery schema. Use canonical `project.dataset.table` form. "
            "Use ONLY listed identifiers."]
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
5. Repeated/struct fields: UNNEST(arr) AS f, then f.field. STRUCT access via dot.
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

def _repair_prompt(q, schema, broken_sql, validation_msg):
    return (
        "Your previous SQL referenced identifiers that don't exist.\n"
        "Replace each unknown identifier with one from the SCHEMA. Output SQL only.\n\n"
        f"{schema}\n\nVALIDATION_REPORT:\n{validation_msg}\n\n"
        f"QUESTION: {q}\nBROKEN_SQL:\n{broken_sql}\nFIXED_SQL:"
    )


# ---- v12 BQ Validator: STRUCT/wildcard-aware ----
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


def _suggest(needle, pool, max_d=3, top_k=5):
    sc = []
    for h in pool:
        d = _levenshtein(needle, h)
        if d <= max_d: sc.append((d, h))
    sc.sort()
    return [h for _, h in sc[:top_k]]


def _build_alias_map(tree):
    try:
        from sqlglot import exp
    except ImportError:
        return {}
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
            if alias_str:
                am[alias_str.lower()] = tbl
            am[tbl.lower()] = tbl
    except Exception:
        pass
    return am


def _wildcard_match(tbl_pattern: str, available: list) -> bool:
    """tbl_pattern like 'EVENTS_*' or 'EVENTS_2021_*'."""
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

    # Tables — NEW v12: support wildcard tables
    for t in tree.find_all(exp.Table):
        try:
            tbl = (t.name or "").upper()
            if not tbl: continue
            if tbl in {n.upper() for n in avail}:
                continue
            # Wildcard?
            if "*" in tbl or tbl.endswith("_"):
                if _wildcard_match(tbl, avail):
                    res["wildcard_resolved"].append({"pattern": tbl})
                    continue
            sugg = _suggest(tbl, avail)
            res["unknown_tables"].append({"table": tbl, "suggestions": sugg})
        except Exception:
            continue

    # Build column map per selected table; also collect struct/array column
    # names per table for nested-field-access skip.
    col_by_table = {n: {c["name"].upper() for c in flat[n]["columns"]} for n in flat}
    struct_cols_per_table = {}
    for tname, td in flat.items():
        sc = set()
        for c in td["columns"]:
            tt = (c.get("type") or "").upper()
            # BQ STRUCT / RECORD / REPEATED / ARRAY / nested
            if any(k in tt for k in ("STRUCT", "RECORD", "REPEATED", "ARRAY")):
                sc.add(c["name"].upper())
            # GA4 known nested columns
            if c["name"].lower() in ("event_params", "user_properties", "items",
                                          "device", "geo", "traffic_source",
                                          "ecommerce", "user_ltv"):
                sc.add(c["name"].upper())
        struct_cols_per_table[tname] = sc

    alias_map = _build_alias_map(tree)
    # also: any struct col name itself is a valid in-SQL "qualifier" used for nested access
    all_struct_qualifiers = set()
    for tname in selected_set:
        all_struct_qualifiers |= struct_cols_per_table.get(tname, set())

    for c in tree.find_all(exp.Column):
        try:
            cname = (c.name or "").upper()
            if not cname: continue
            qual = ((c.args.get("table") and c.args["table"].name) or "").upper()

            # NEW v12: BQ pseudo-columns (_TABLE_SUFFIX etc.)
            if cname in _BQ_RESERVED_PSEUDO_COLS:
                continue

            # NEW v12: nested struct/array access
            # If qual matches a struct column on any selected table, skip column validation.
            if qual and qual in all_struct_qualifiers:
                res["false_positive_struct_cols"].append(
                    {"qual": qual, "col": cname, "kind": "struct_field_access"})
                continue
            # Heuristic: certain GA4 nested chains like `event_params.value.int_value`
            # show up as col=int_value qual=value. Treat 'VALUE' as struct-qualifier.
            if qual in ("VALUE", "INT_VALUE", "STRING_VALUE", "FLOAT_VALUE",
                          "DOUBLE_VALUE", "PARAMS", "USER_PROPERTIES_VALUE"):
                res["false_positive_struct_cols"].append(
                    {"qual": qual, "col": cname, "kind": "ga4_nested"})
                continue

            if qual:
                resolved = alias_map.get(qual.lower(), qual)
                tbls = [resolved]
            else:
                tbls = list(selected_set)

            found = any(cname in col_by_table.get(tt, set()) for tt in tbls)
            if not found:
                pool = []
                for tname, cols in col_by_table.items():
                    for cc in cols:
                        pool.append(f"{tname}.{cc}")
                sugg = _suggest(cname, pool, max_d=2)
                if not sugg:
                    just = sorted({cc for cols in col_by_table.values() for cc in cols})
                    sugg = _suggest(cname, just, max_d=2)
                res["unknown_columns"].append({"col": cname, "qual": qual,
                                                   "suggestions": sugg})
        except Exception:
            continue

    res["schema_valid"] = (not res["unknown_tables"]) and (not res["unknown_columns"])
    return res


def _render_validation_report(val):
    lines = []
    if val["unknown_tables"]:
        lines.append("UNKNOWN_TABLES:")
        for ent in val["unknown_tables"][:10]:
            lines.append(f"  - {ent['table']}  suggestions={ent['suggestions']}")
    if val["unknown_columns"]:
        lines.append("UNKNOWN_COLUMNS:")
        for ent in val["unknown_columns"][:10]:
            lines.append(f"  - {ent['col']} (qual={ent['qual'] or '-'})  suggestions={ent['suggestions']}")
    if not lines: lines.append("OK")
    return "\n".join(lines)


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
    g = globals(); bq = g["bigquery"]
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
                  "elapsed_ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        msg = str(exc)
        et = ("bytes_billed_exceeded" if "bytes" in msg.lower() and "billed" in msg.lower()
              else "object_not_found" if "Not found" in msg or "not found" in msg
              else "syntax" if "Syntax error" in msg
              else type(exc).__name__)
        return {"ok": False, "error_type": et, "error_message": msg[:400],
                  "elapsed_ms": int((time.time() - t0) * 1000)}


def run_pilot_v12(limit=10, *, run_id=None, max_repair_rounds=2, max_rows=100,
                       cap_bytes_billed=1*1024**3, no_execute=False,
                       max_new_sql=800, max_new_cte=1100):
    if run_id is None:
        run_id = f"lite_bq_v12_pilot{limit}_{int(time.time())}"
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
    cost_rows = []
    catalogs = {}

    for i, it in enumerate(rows, 1):
        iid = it["instance_id"]; db = it["db"]; q = it["question"]
        t_task = time.time()
        print(f"\n[{i}/{len(rows)}] {iid} db={db} ...", flush=True)

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
                sql_raw = ""; print(f"  gen_err {src}: {type(exc).__name__}", flush=True)
            norm = _bq_normalize(sql_raw)
            sql = norm["sql"]
            val = _validate_sql(sql, cat, db, selected)
            if val.get("false_positive_struct_cols"):
                fp_count["struct_field_access"] += len(val["false_positive_struct_cols"])
            if val.get("wildcard_resolved"):
                fp_count["wildcard_table"] += len(val["wildcard_resolved"])
            cands.append({"source": src, "sql": sql, "original_sql": sql_raw,
                            "applied_fixes": norm["applied_fixes"],
                            "validation": val})

        repair_record = None
        schema_valid_before = any(c["validation"]["schema_valid"] for c in cands)
        if not schema_valid_before:
            seed = cands[0]
            for r_n in range(1, max_repair_rounds + 1):
                rep_msg = _render_validation_report(seed["validation"])
                try:
                    raw = _gen(_repair_prompt(q, schema_text, seed["sql"], rep_msg),
                                  max_new=max_new_sql)
                    new_sql = _extract_sql(raw)
                except Exception as exc:
                    repair_record = {"rounds": r_n, "success": False,
                                       "error": type(exc).__name__}
                    break
                norm = _bq_normalize(new_sql)
                val = _validate_sql(norm["sql"], cat, db, selected)
                if val["schema_valid"]:
                    repaired = {"source": "C3_repaired", "sql": norm["sql"],
                                  "original_sql": new_sql,
                                  "applied_fixes": norm["applied_fixes"],
                                  "validation": val}
                    cands.append(repaired)
                    repair_record = {"rounds": r_n, "success": True}
                    break
                seed = {**seed, "sql": norm["sql"], "validation": val}
                repair_record = {"rounds": r_n, "success": False}

        valid_cands = [c for c in cands if c["validation"]["schema_valid"]]
        if valid_cands:
            chosen = max(valid_cands,
                            key=lambda c: 0.10 if c["source"] == "C3_repaired"
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
        et = verifier["error_type"] or "none"
        err_tax[et] += 1
        src_break[chosen["source"]] += 1
        if repair_record and repair_record.get("success"):
            metrics["repair_helpful"] += 1

        wall = round(time.time() - t_task, 2)
        pred = {"instance_id": iid, "db": db, "lane": "A_bq",
                  "sql": chosen["sql"], "original_sql": chosen.get("original_sql", ""),
                  "final_source": chosen["source"],
                  "schema_valid": chosen["validation"]["schema_valid"],
                  "schema_valid_before_repair": schema_valid_before,
                  "repair_attempted": bool(repair_record is not None),
                  "repair_helpful": bool(repair_record and repair_record.get("success")),
                  "parses": verifier["parses"],
                  "executable": verifier.get("executable"),
                  "rows_count": verifier.get("rows_count", 0),
                  "bytes_processed": verifier.get("bytes_processed", 0),
                  "bytes_billed": verifier.get("bytes_billed", 0),
                  "error_type": et,
                  "error_message": verifier["error_message"][:400] if verifier["error_message"] else "",
                  "applied_fixes": chosen.get("applied_fixes", []),
                  "n_unknown_tables": len(chosen["validation"]["unknown_tables"]),
                  "n_unknown_columns": len(chosen["validation"]["unknown_columns"]),
                  "n_wildcard_resolved": len(chosen["validation"].get("wildcard_resolved", [])),
                  "n_struct_fp_skipped": len(chosen["validation"].get("false_positive_struct_cols", [])),
                  "wall_time_s": wall,
                  "utc": datetime.now(timezone.utc).isoformat()}
        with pred_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(pred, ensure_ascii=False) + "\n")
        with cand_path.open("a", encoding="utf-8") as f:
            for c in cands:
                f.write(json.dumps({"instance_id": iid, "source": c["source"],
                                       "schema_valid": c["validation"]["schema_valid"],
                                       "n_unknown_tables": len(c["validation"]["unknown_tables"]),
                                       "n_unknown_columns": len(c["validation"]["unknown_columns"]),
                                       "applied_fixes": c.get("applied_fixes", [])},
                                      ensure_ascii=False) + "\n")
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"instance_id": iid, "db": db,
                                   "repair_record": repair_record,
                                   "selected_tables": [t["fq_name"] for t in selected],
                                   "utc": datetime.now(timezone.utc).isoformat()},
                                  ensure_ascii=False) + "\n")
        cost_rows.append({"instance_id": iid, "db": db, "wall_time_s": wall,
                            "bytes_processed": pred["bytes_processed"],
                            "bytes_billed": pred["bytes_billed"]})
        print(f"  schema_valid={pred['schema_valid']} parse={pred['parses']} "
                f"exec={pred['executable']} ut={pred['n_unknown_tables']} "
                f"uc={pred['n_unknown_columns']} wildcard={pred['n_wildcard_resolved']} "
                f"struct_fp={pred['n_struct_fp_skipped']} err={et} wall={wall}s", flush=True)

    import csv
    with (out_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        for k in ("n", "chosen_schema_valid", "parse_ok", "execute_ok",
                    "repair_helpful"):
            w.writerow([k, metrics[k]])
        w.writerow(["false_positive_struct_skips", fp_count["struct_field_access"]])
        w.writerow(["wildcard_table_resolves", fp_count["wildcard_table"]])
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
    md = [f"# Spider2-Lite-BQ v12 — run `{run_id}` (wildcard + struct-aware validator)", "",
            "## Aggregate metrics", "",
            "| metric | value | rate |", "|---|---:|---:|",
            f"| n_total | {metrics['n']} | — |",
            f"| chosen_schema_valid | {metrics['chosen_schema_valid']} | "
            f"{(metrics['chosen_schema_valid']/n)*100:.1f}% |",
            f"| parse_ok | {metrics['parse_ok']} | {(metrics['parse_ok']/n)*100:.1f}% |",
            f"| execute_ok | {metrics['execute_ok']} | {(metrics['execute_ok']/n)*100:.1f}% |",
            f"| repair_helpful | {metrics['repair_helpful']} | — |",
            f"| struct_field_skips (FP avoided) | {fp_count['struct_field_access']} | — |",
            f"| wildcard_table_resolves | {fp_count['wildcard_table']} | — |",
            "", "## Error taxonomy", "", "| error_type | count |", "|---|---:|"]
    for k, v in err_tax.most_common(15): md.append(f"| `{k}` | {v} |")
    md += ["", "## Source breakdown", "", "| source | count |", "|---|---:|"]
    for k, v in src_break.most_common(): md.append(f"| `{k}` | {v} |")
    (out_dir / "readout.md").write_text("\n".join(md), encoding="utf-8")

    (out_dir / "_DONE").write_text(json.dumps({
        "run_id": run_id, "n_total": metrics["n"],
        "chosen_schema_valid": metrics["chosen_schema_valid"],
        "parse_ok": metrics["parse_ok"], "execute_ok": metrics["execute_ok"],
        "repair_helpful": metrics["repair_helpful"],
        "struct_fp_skips": fp_count["struct_field_access"],
        "wildcard_resolves": fp_count["wildcard_table"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    print(f"\nDONE run_id={run_id}", flush=True)
    return {"run_id": run_id, "out_dir": str(out_dir)}


def start_v12_bq_bg(limit=10, *, run_id=None, max_repair_rounds=2,
                          max_rows=100, cap_bytes_billed=1*1024**3, no_execute=False):
    if run_id is None:
        run_id = f"lite_bq_v12_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_STARTED").write_text(json.dumps({"run_id": run_id, "limit": limit,
                                                       "ts": datetime.now(timezone.utc).isoformat()}),
                                            encoding="utf-8")
    def _runner():
        try:
            run_pilot_v12(limit=limit, run_id=run_id,
                              max_repair_rounds=max_repair_rounds,
                              max_rows=max_rows, cap_bytes_billed=cap_bytes_billed,
                              no_execute=no_execute)
        except Exception as exc:
            (out_dir / "_FAILED").write_text(json.dumps({
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
                "traceback": traceback.format_exc()[:4000],
                "ts": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
    t = threading.Thread(target=_runner, name=f"bq_v12_{run_id}", daemon=True)
    t.start()
    return {"run_id": run_id, "out_dir": str(out_dir), "started": True}


def v12_bq_status(run_id):
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
