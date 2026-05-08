"""spider2_snow_v13_colab_runner — rich render (v11) + 3-round repair (v12).

Reverses the v12 regression: bring back column descriptions, sample
values, and external_knowledge in the schema render while keeping
v12's 3-round repair, alias-aware validator, self-recovery on
`/content/` wipe.

Per-task pipeline (v13):
  1. Re-extract Snow tarball if /content/spider2_snow_extract is empty.
  2. Build/reuse per-DB catalog from local Snow extract.
  3. Render schema RICH: top-K tables, column type + DESCRIPTION +
     SAMPLE VALUES preserved. Deterministic ordering.
  4. Inject `external_knowledge` (Spider2-Snow per-task field) into
     prompt — was only used by v9 in some prompts; v13 always.
  5. Generate C0_direct, C1_retrieval, C2_cte.
  6. v9 dialect normalizer + v10 4-part collapse + v10 quoted-blob
     unwrap chain.
  7. Strict pre-execution validator (sqlglot AST + catalog + alias map).
  8. 3-round schema-aware repair: r1 unknown-id, r2 syntax, r3 regenerate.
  9. SF dry_run + execute on schema-valid only.

Async pattern (start_v13_bg / v13_status) for Cloudflare safety.
"""
from __future__ import annotations


def _self_contained_runner_template() -> str:
    return r'''
# ---------- Colab-side Snow v13 pilot runner ----------
import os, sys, json, re, time, traceback, threading
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

DRV = Path("/content/drive/MyDrive/diploma_plan_sql")
SNOW_JSONL = DRV / "external_benchmarks/spider2_snow/processed/spider2_snow_547.jsonl"
SNOW_RES_BASE = Path("/content/spider2_snow_extract/spider2-snow/resource/databases")
SNOW_TGZ_DRIVE = DRV / "external_benchmarks/spider2_snow/raw/spider2_main.tgz"
RUNS_BASE = DRV / "outputs/spider2_snow/runs"
SF_SECRET_PATH = DRV / "secrets/snowflake.json"


def _ensure_snow_extract():
    if SNOW_RES_BASE.is_dir() and len(list(SNOW_RES_BASE.iterdir())) >= 50:
        return
    print("Snow extract missing; re-extracting from Drive tarball ...", flush=True)
    import tarfile
    EXTRACT = SNOW_RES_BASE.parent.parent.parent
    EXTRACT.mkdir(parents=True, exist_ok=True)
    n = 0
    with tarfile.open(str(SNOW_TGZ_DRIVE), "r:gz") as t:
        for m in t:
            parts = m.name.split("/", 2)
            if len(parts) < 2 or parts[1] != "spider2-snow": continue
            rel = "/".join(parts[1:])
            out = EXTRACT / rel
            if m.isdir() or rel.endswith("/"):
                out.mkdir(parents=True, exist_ok=True); continue
            out.parent.mkdir(parents=True, exist_ok=True)
            fp = t.extractfile(m)
            if fp:
                out.write_bytes(fp.read()); n += 1
    print(f"re-extracted {n} files", flush=True)


# ---- Normalizer chain (v9 + v10) ----
_QUOT = r'"([^"]+)"|([A-Za-z_][\w$]*)'
_DOT_4PART_RE = re.compile(fr'(?:{_QUOT})\.(?:{_QUOT})\.(?:{_QUOT})\.(?:{_QUOT})')
_QUOTED_3PART_BLOB_RE = re.compile(r'"([A-Za-z_][\w$]*\.[A-Za-z_][\w$]*\.[A-Za-z_][\w$]*)"')
_BACKTICK_TRIPLE_RE = re.compile(r'`([A-Za-z_][\w-]*)\.([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)`')
_UNNEST_RE = re.compile(r'\bUNNEST\s*\(\s*([^)]+)\s*\)\s*(?:AS\s+(\w+))?', re.IGNORECASE)
_SAFE_CAST_RE = re.compile(r'\bSAFE_CAST\b', re.IGNORECASE)
_DATEDIFF_BQ_RE = re.compile(r'\bDATE_DIFF\s*\(\s*([^,]+),\s*([^,]+),\s*(\w+)\s*\)', re.IGNORECASE)
_REGEXP_CONTAINS_RE = re.compile(r'\bREGEXP_CONTAINS\b', re.IGNORECASE)


def _seg(m, base): return m.group(base) or m.group(base + 1)


def _normalize(sql):
    if not sql: return {"sql": "", "applied_fixes": []}
    cur = sql; applied = []
    out = _BACKTICK_TRIPLE_RE.sub(
        lambda m: f"{m.group(2).upper()}.{m.group(3).upper()}" if ('-' in m.group(1) or m.group(1).islower())
                   else f"{m.group(1).upper()}.{m.group(2).upper()}.{m.group(3).upper()}", cur)
    if out != cur: applied.append("backtick_3part"); cur = out
    out = _UNNEST_RE.sub(
        lambda m: f"LATERAL FLATTEN(input => {m.group(1).strip()}) AS {m.group(2) or 'f'}", cur)
    if out != cur: applied.append("unnest_to_flatten"); cur = out
    out = _SAFE_CAST_RE.sub("TRY_CAST", cur)
    if out != cur: applied.append("safe_cast_to_try_cast"); cur = out
    out = _DATEDIFF_BQ_RE.sub(
        lambda m: f"DATEDIFF({m.group(3).upper()}, {m.group(2).strip()}, {m.group(1).strip()})", cur)
    if out != cur: applied.append("date_diff_arg_order"); cur = out
    out = _REGEXP_CONTAINS_RE.sub("REGEXP_LIKE", cur)
    if out != cur: applied.append("regexp_contains_to_like"); cur = out
    out = _QUOTED_3PART_BLOB_RE.sub(lambda m: m.group(1), cur)
    if out != cur: applied.append("unwrap_quoted_3part_blob"); cur = out
    n_4 = 0
    def _4part(m):
        nonlocal n_4
        s1, s2, s3, s4 = _seg(m,1), _seg(m,3), _seg(m,5), _seg(m,7)
        if s2 and s3 and s2.upper() == s3.upper():
            n_4 += 1
            return f"{s1}.{s2}.{s4}"
        return m.group(0)
    out = _DOT_4PART_RE.sub(_4part, cur)
    if n_4: applied.append(f"4part_collapsed:{n_4}"); cur = out
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
def _build_db_catalog(db, *, max_tables_per_schema=80):
    db_dir = SNOW_RES_BASE / db
    schemas = {}
    if not db_dir.is_dir():
        return {"schemas": schemas, "tables_flat": {}}
    for sch_dir in sorted(db_dir.iterdir()):
        if not sch_dir.is_dir(): continue
        sch = sch_dir.name
        tables = {}
        n = 0
        for jf in sorted(sch_dir.glob("*.json")):
            try: d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception: continue
            if not isinstance(d, dict): continue
            tname = (d.get("table_name") or jf.stem).strip()
            cols = d.get("column_names") or []
            types = d.get("column_types") or []
            descs = d.get("column_descriptions") or [""] * len(cols)
            samples = d.get("sample_rows") or []
            if not tname or not cols: continue
            col_metas = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else "VARCHAR") or "VARCHAR"
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
            tables[tname] = {"fq_name": f"{db}.{sch}.{tname}",
                              "database": db, "schema": sch, "table": tname,
                              "description": str(d.get("description") or "")[:300],
                              "columns": col_metas}
            n += 1
            if n >= max_tables_per_schema: break
        if tables: schemas[sch] = tables
    flat = {}
    for sch, tbls in schemas.items():
        for tname, td in tbls.items():
            flat[tname.upper()] = td
    return {"schemas": schemas, "tables_flat": flat}


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


# ---- v13 RICH render: descriptions + samples preserved ----
def _render_rich(tables, max_cols_per_table=20):
    out = ["# Allowed Snowflake identifiers (use ONLY these, EXACTLY as listed):"]
    for t in tables:
        out.append(f"\nTABLE: {t['fq_name']}")
        if t.get("description"):
            out.append(f"  -- {t['description'][:200]}")
        cols = t["columns"][:max_cols_per_table]
        for c in cols:
            line = f"  {c['name']}: {c['type']}"
            if c.get("description"):
                line += f"  -- {c['description'][:120]}"
            if c.get("samples"):
                line += f"  /* eg. {', '.join(c['samples'][:3])} */"
            out.append(line)
        if len(t["columns"]) > max_cols_per_table:
            out.append(f"  -- {len(t['columns']) - max_cols_per_table} more columns omitted")
    return "\n".join(out)


_SF_RULES_V13 = """You generate Snowflake SQL. STRICTEST rules:

1. Use ONLY identifiers (tables, columns) listed under "Allowed Snowflake identifiers" — EXACTLY as written. If a needed column isn't listed, pick the CLOSEST listed one. Do NOT invent identifiers.
2. 3-part identifiers ONLY: DB.SCHEMA.TABLE. Never 4-part. Never repeat any segment.
3. No backticks, no [brackets].
4. Snowflake date/time: DATEDIFF(DAY, d1, d2); DATEADD(DAY, n, d); DATE_TRUNC('DAY', d); TO_DATE(s, 'YYYYMMDD').
5. Repeated/array: LATERAL FLATTEN(input => arr) AS f, f.value.
6. TRY_CAST (no SAFE_CAST). ILIKE (no REGEXP_CONTAINS). QUALIFY supported.
7. Single statement. SQL only.
"""


def _direct_prompt(q, schema, ext_knowledge=""):
    parts = [_SF_RULES_V13, schema]
    if ext_knowledge:
        parts.append(f"DOMAIN_KNOWLEDGE:\n{ext_knowledge[:1500]}")
    parts.append(f"Question: {q}\nSQL:")
    return "\n\n".join(parts)


def _retrieval_prompt(q, schema, ext_knowledge=""):
    parts = [_SF_RULES_V13, schema]
    if ext_knowledge:
        parts.append(f"DOMAIN_KNOWLEDGE:\n{ext_knowledge[:1500]}")
    parts.append(f"Question: {q}\nThink step-by-step which listed columns answer the question, then write SQL.\nSQL:")
    return "\n\n".join(parts)


def _cte_prompt(q, schema, ext_knowledge=""):
    parts = [_SF_RULES_V13, schema]
    if ext_knowledge:
        parts.append(f"DOMAIN_KNOWLEDGE:\n{ext_knowledge[:1500]}")
    parts.append(f"Decompose into named CTEs. Each CTE = one logical step.\n\nQuestion: {q}\nSQL:")
    return "\n\n".join(parts)


def _repair_round1(q, schema, broken_sql, validation_msg):
    return (f"Your previous SQL referenced identifiers that don't exist.\n"
            f"Replace each unknown identifier with one from the SCHEMA.\n"
            f"Output SQL only.\n\n{schema}\n\nVALIDATION:\n{validation_msg}\n\n"
            f"QUESTION: {q}\nBROKEN_SQL:\n{broken_sql}\nFIXED_SQL:")


def _repair_round2(q, schema, broken_sql, engine_err):
    return (f"Identifiers correct; Snowflake rejected SQL with syntax error.\n"
            f"Fix syntax. Output SQL only.\n\n{schema}\n\n"
            f"SNOWFLAKE_ERROR:\n{(engine_err or '')[:600]}\n\n"
            f"QUESTION: {q}\nBROKEN_SQL:\n{broken_sql}\nFIXED_SQL:")


def _repair_round3(q, schema):
    return (f"Generate Snowflake SQL from scratch using ONLY identifiers below. Be conservative.\n\n"
            f"{schema}\n\nQuestion: {q}\nSQL:")


# ---- Validator (alias-aware) ----
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


def _validate_sql(sql, catalog, db, selected_tables=None):
    res = {"schema_valid": False, "unknown_tables": [], "unknown_columns": [],
            "false_positive_aliases": [], "notes": []}
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
        tree = sqlglot.parse_one(sql, read="snowflake")
    except Exception as exc:
        res["notes"].append(f"sqlglot_parse_failed:{type(exc).__name__}")
        return res

    alias_map = _build_alias_map(tree)
    # Tables
    for t in tree.find_all(exp.Table):
        try:
            tbl = (t.name or "").upper()
            if not tbl: continue
            if tbl not in {n.upper() for n in avail}:
                sugg = _suggest(tbl, avail)
                res["unknown_tables"].append({"table": tbl, "suggestions": sugg})
        except Exception:
            continue

    col_by_table = {n: {c["name"].upper() for c in flat[n]["columns"]} for n in flat}
    # Set of column names known to be VARIANT/array/struct types → their
    # nested-field accesses should NOT be flagged as unknown columns.
    variant_cols_per_table = {}
    for tname, td in flat.items():
        var_cols = set()
        for c in td["columns"]:
            tt = (c.get("type") or "").upper()
            if any(k in tt for k in ("VARIANT", "OBJECT", "ARRAY", "STRUCT")):
                var_cols.add(c["name"].upper())
        variant_cols_per_table[tname] = var_cols

    for c in tree.find_all(exp.Column):
        try:
            cname = (c.name or "").upper()
            if not cname: continue
            qual = ((c.args.get("table") and c.args["table"].name) or "").upper()
            if qual:
                resolved = alias_map.get(qual.lower(), qual)
                tbls = [resolved]
                if resolved != qual:
                    res["false_positive_aliases"].append(
                        {"alias": qual, "resolved_table": resolved, "col": cname})
            else:
                tbls = list(selected_set)

            # If qualifier itself is a VARIANT/STRUCT column on any selected
            # table, treat nested access as fine (skip column validation).
            if qual:
                qual_u = qual.upper()
                is_variant_access = any(qual_u in variant_cols_per_table.get(tt, set())
                                            for tt in selected_set)
                if is_variant_access:
                    continue  # skip this column — it's a nested-field access

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


# ---- Model + SF ----
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


def _ensure_sf():
    g = globals()
    if g.get("_SF_CONN") is not None: return
    import snowflake.connector
    sf = json.loads(SF_SECRET_PATH.read_text(encoding="utf-8"))
    cn = snowflake.connector.connect(
        account=sf["account"], user=sf["user"], password=sf["password"],
        role=sf.get("role"), warehouse=sf.get("warehouse"),
        database=sf.get("database", "PATENTS"),
        schema=sf.get("schema", "PUBLIC"),
        application="spider2_snow_v13")
    g["_SF_CONN"] = cn
    print("SF_CONN_READY", flush=True)


def _sf_dry(sql):
    g = globals(); cur = g["_SF_CONN"].cursor()
    try:
        cur.execute("EXPLAIN USING TEXT " + sql); cur.fetchall()
        return {"ok": True}
    except Exception as exc:
        msg = str(exc)
        et = ("syntax" if ("syntax error" in msg.lower() or "compilation error" in msg.lower())
                          and "invalid identifier" not in msg.lower()
              else "object_not_found" if "invalid identifier" in msg.lower() or "does not exist" in msg.lower()
              else type(exc).__name__)
        return {"ok": False, "error_type": et, "error_message": msg[:400]}


def _sf_exec(sql, max_rows=100):
    g = globals(); t0 = time.time()
    cur = g["_SF_CONN"].cursor()
    try:
        cur.execute(sql); rows = cur.fetchmany(max_rows)
        return {"ok": True, "row_count": len(rows),
                  "elapsed_ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        msg = str(exc)
        et = ("syntax" if "syntax error" in msg.lower()
              else "object_not_found" if "invalid identifier" in msg.lower() or "does not exist" in msg.lower()
              else type(exc).__name__)
        return {"ok": False, "error_type": et, "error_message": msg[:400],
                  "elapsed_ms": int((time.time() - t0) * 1000)}


def run_pilot_v13(limit=10, *, run_id=None, max_rows=100, no_execute=False,
                       max_new_sql=800, max_new_cte=1100):
    if run_id is None:
        run_id = f"snow_v13_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"
    cand_path = out_dir / "candidates.jsonl"
    trace_path = out_dir / "traces.jsonl"
    print(f"RUN_ID={run_id}", flush=True)

    _ensure_snow_extract()

    rows = []
    with SNOW_JSONL.open(encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            d = json.loads(ln)
            adapted = {"instance_id": d.get("instance_id", ""),
                          "db": d.get("db_id") or d.get("db") or "",
                          "question": d.get("instruction") or d.get("question") or "",
                          "external_knowledge": d.get("external_knowledge", "")}
            rows.append(adapted)
            if limit and limit > 0 and len(rows) >= limit: break
    print(f"TASKS={len(rows)}", flush=True)

    _ensure_model()
    _ensure_sf()

    metrics = Counter()
    err_tax = Counter()
    src_break = Counter()
    catalogs = {}

    for i, it in enumerate(rows, 1):
        iid = it["instance_id"]; db = it["db"]; q = it["question"]; ek = it["external_knowledge"]
        t_task = time.time()
        print(f"\n[{i}/{len(rows)}] {iid} db={db} ...", flush=True)

        if db not in catalogs:
            catalogs[db] = _build_db_catalog(db)
        cat = catalogs[db]
        if not cat["tables_flat"]:
            print(f"  SKIP no_catalog for {db}", flush=True)
            row = {"instance_id": iid, "db": db, "lane": "A_sf",
                    "mode": "blocked_no_catalog",
                    "sql": "", "parses": False, "executable": False,
                    "schema_valid": False, "error_type": "catalog_missing",
                    "wall_time_s": round(time.time() - t_task, 2)}
            with pred_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            metrics["n"] += 1; err_tax["catalog_missing"] += 1
            continue

        selected = _retrieve_keys(cat, q, k=6)
        schema_text = _render_rich(selected, max_cols_per_table=20)

        cands = []
        for src, builder, mn in (
            ("C0_direct", _direct_prompt, max_new_sql),
            ("C1_retrieval", _retrieval_prompt, max_new_sql),
            ("C2_cte", _cte_prompt, max_new_cte),
        ):
            try:
                raw = _gen(builder(q, schema_text, ek), max_new=mn)
                sql_raw = _extract_sql(raw)
            except Exception as exc:
                sql_raw = ""; print(f"  gen_err {src}: {type(exc).__name__}", flush=True)
            norm = _normalize(sql_raw)
            sql = norm["sql"]
            val = _validate_sql(sql, cat, db, selected)
            cands.append({"source": src, "sql": sql, "original_sql": sql_raw,
                            "applied_fixes": norm["applied_fixes"],
                            "validation": val})

        repair_record = None
        schema_valid_before = any(c["validation"]["schema_valid"] for c in cands)
        if not schema_valid_before:
            seed = cands[0]
            rounds_log = []
            for r_n in range(1, 4):
                if r_n == 1:
                    prompt = _repair_round1(q, schema_text, seed["sql"],
                                                   _render_validation_report(seed["validation"]))
                elif r_n == 2:
                    if seed["validation"]["schema_valid"]:
                        dr = _sf_dry(seed["sql"])
                        prompt = _repair_round2(q, schema_text, seed["sql"],
                                                       dr.get("error_message", "") if not dr.get("ok") else "")
                    else:
                        prompt = _repair_round1(q, schema_text, seed["sql"],
                                                       _render_validation_report(seed["validation"]))
                else:
                    prompt = _repair_round3(q, schema_text)
                try:
                    raw = _gen(prompt, max_new=max_new_sql)
                    new_sql = _extract_sql(raw)
                except Exception as exc:
                    rounds_log.append({"round": r_n, "gen_error": type(exc).__name__})
                    break
                norm = _normalize(new_sql)
                val = _validate_sql(norm["sql"], cat, db, selected)
                rounds_log.append({"round": r_n, "schema_valid": val["schema_valid"],
                                      "n_unknown_t": len(val["unknown_tables"]),
                                      "n_unknown_c": len(val["unknown_columns"])})
                if val["schema_valid"]:
                    repaired = {"source": f"C3_repaired_r{r_n}", "sql": norm["sql"],
                                  "original_sql": new_sql,
                                  "applied_fixes": norm["applied_fixes"],
                                  "validation": val}
                    cands.append(repaired)
                    repair_record = {"rounds": r_n, "success": True, "log": rounds_log}
                    break
                seed = {**seed, "sql": norm["sql"], "validation": val}
            if not repair_record:
                repair_record = {"rounds": 3, "success": False, "log": rounds_log}

        valid_cands = [c for c in cands if c["validation"]["schema_valid"]]
        if valid_cands:
            chosen = max(valid_cands,
                            key=lambda c: 0.10 if c["source"].startswith("C3_repaired")
                            else (0.05 if c["source"] == "C1_retrieval" else 0.0))
        else:
            chosen = min(cands, key=lambda c: len(c["validation"].get("unknown_tables", []))
                            + len(c["validation"].get("unknown_columns", [])))

        verifier = {"parses": False, "executable": None,
                     "rows_count": 0, "error_type": "", "error_message": ""}
        if chosen["validation"]["schema_valid"]:
            dr = _sf_dry(chosen["sql"])
            if dr["ok"]:
                verifier["parses"] = True
                if not no_execute:
                    er = _sf_exec(chosen["sql"], max_rows=max_rows)
                    verifier["executable"] = bool(er["ok"])
                    verifier["rows_count"] = er.get("row_count", 0)
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
            metrics[f"repair_helpful_round_{repair_record['rounds']}"] += 1

        wall = round(time.time() - t_task, 2)
        pred = {"instance_id": iid, "db": db, "lane": "A_sf",
                  "sql": chosen["sql"], "original_sql": chosen.get("original_sql", ""),
                  "final_source": chosen["source"],
                  "schema_valid": chosen["validation"]["schema_valid"],
                  "schema_valid_before_repair": schema_valid_before,
                  "repair_attempted": bool(repair_record is not None),
                  "repair_helpful": bool(repair_record and repair_record.get("success")),
                  "repair_rounds_used": repair_record.get("rounds") if repair_record else 0,
                  "parses": verifier["parses"],
                  "executable": verifier.get("executable"),
                  "rows_count": verifier.get("rows_count", 0),
                  "error_type": et,
                  "error_message": verifier["error_message"][:400] if verifier["error_message"] else "",
                  "applied_fixes": chosen.get("applied_fixes", []),
                  "selected_tables": [t["fq_name"] for t in selected],
                  "n_unknown_tables": len(chosen["validation"]["unknown_tables"]),
                  "n_unknown_columns": len(chosen["validation"]["unknown_columns"]),
                  "external_knowledge_present": bool(ek),
                  "wall_time_s": wall,
                  "utc": datetime.now(timezone.utc).isoformat()}
        with pred_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(pred, ensure_ascii=False) + "\n")
        with cand_path.open("a", encoding="utf-8") as f:
            for c in cands:
                f.write(json.dumps({"instance_id": iid, "source": c["source"],
                                       "schema_valid": c["validation"]["schema_valid"],
                                       "n_unknown_tables": len(c["validation"]["unknown_tables"]),
                                       "n_unknown_columns": len(c["validation"]["unknown_columns"])},
                                      ensure_ascii=False) + "\n")
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"instance_id": iid, "db": db,
                                   "repair_record": repair_record,
                                   "candidates_n": len(cands),
                                   "selected_tables": [t["fq_name"] for t in selected],
                                   "ext_knowledge_chars": len(ek),
                                   "utc": datetime.now(timezone.utc).isoformat()},
                                  ensure_ascii=False) + "\n")
        print(f"  schema_valid={pred['schema_valid']} parse={pred['parses']} "
                f"exec={pred['executable']} ut={pred['n_unknown_tables']} "
                f"uc={pred['n_unknown_columns']} repair={pred['repair_helpful']} "
                f"rounds={pred['repair_rounds_used']} err={et} wall={wall}s", flush=True)

    import csv
    with (out_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        for k in ("n", "chosen_schema_valid", "parse_ok", "execute_ok",
                    "repair_helpful", "repair_helpful_round_1",
                    "repair_helpful_round_2", "repair_helpful_round_3"):
            w.writerow([k, metrics[k]])
    with (out_dir / "error_taxonomy.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["error_type", "count"])
        for k, v in err_tax.most_common(): w.writerow([k, v])
    with (out_dir / "source_breakdown.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["final_source", "count"])
        for k, v in src_break.most_common(): w.writerow([k, v])

    n = max(1, metrics["n"])
    md = [f"# Spider2-Snow v13 — run `{run_id}` (rich render + 3-round repair)", "",
            "## Aggregate metrics", "",
            "| metric | value | rate |", "|---|---:|---:|",
            f"| n_total | {metrics['n']} | — |",
            f"| chosen_schema_valid | {metrics['chosen_schema_valid']} | "
            f"{(metrics['chosen_schema_valid']/n)*100:.1f}% |",
            f"| parse_ok | {metrics['parse_ok']} | {(metrics['parse_ok']/n)*100:.1f}% |",
            f"| execute_ok | {metrics['execute_ok']} | {(metrics['execute_ok']/n)*100:.1f}% |",
            f"| repair_helpful | {metrics['repair_helpful']} | — |",
            f"| repair_helpful_round_1 | {metrics['repair_helpful_round_1']} | — |",
            f"| repair_helpful_round_2 | {metrics['repair_helpful_round_2']} | — |",
            f"| repair_helpful_round_3 | {metrics['repair_helpful_round_3']} | — |",
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
        "ts": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    print(f"\nDONE run_id={run_id}", flush=True)
    return {"run_id": run_id, "out_dir": str(out_dir)}


def start_v13_bg(limit=10, *, run_id=None, max_rows=100, no_execute=False):
    if run_id is None:
        run_id = f"snow_v13_pilot{limit}_{int(time.time())}"
    out_dir = RUNS_BASE / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_STARTED").write_text(json.dumps({"run_id": run_id, "limit": limit,
                                                       "ts": datetime.now(timezone.utc).isoformat()}),
                                            encoding="utf-8")
    def _runner():
        try:
            run_pilot_v13(limit=limit, run_id=run_id, max_rows=max_rows,
                              no_execute=no_execute)
        except Exception as exc:
            (out_dir / "_FAILED").write_text(json.dumps({
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
                "traceback": traceback.format_exc()[:4000],
                "ts": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
    t = threading.Thread(target=_runner, name=f"v13_{run_id}", daemon=True)
    t.start()
    return {"run_id": run_id, "out_dir": str(out_dir), "started": True}


def v13_status(run_id):
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
