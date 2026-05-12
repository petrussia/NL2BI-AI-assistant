"""B4_v3: hybrid retrieval + compact planner + multi-candidate + bounded repair
+ candidate ranker + B1_v3 fallback.

Pipeline:
1. Hybrid retrieval (B3_v3 path) → selected_table_indexes, retrieval confidence.
2. Compact planner (planner_gate) over shortlist schema. Validate plan_v2.
3. Multi-candidate sampling: k=3, T=0.7, top_p=0.95, top_k=50.
4. AST safety guard per candidate.
5. Execute each candidate; build per-candidate score via candidate_ranker.
6. If best margin too small → consistency vote.
7. If no executable candidate → bounded repair (depth=1 Spider, 2 BIRD).
8. If still no executable → B1_v3 fallback.
"""
from __future__ import annotations
import re

from retrieval_hybrid import hybrid_retrieve_tables
from planner_gate import (
    parse_plan_v2, should_invoke_planner, make_compact_planner_prompt,
    make_compact_synth_prompt, make_repair_prompt, build_fk_summary, is_safe_select,
)
from candidate_ranker import score_candidate, pick_best


def _extract_sql(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"(?is)(select\b.*)", text)
    if m: text = m.group(1).strip()
    text = text.split("\n\n")[0].strip()
    if ";" in text: text = text.split(";", 1)[0].strip()
    return text.rstrip(";") + ";"


def run_b4v3_step(question: str, db_id: str, tables_meta: dict,
                  *,
                  build_full_schema, build_reduced_schema,
                  gen, gen_multi, validator, executor,
                  evidence: str = "",
                  k_candidates: int = 3,
                  repair_depth: int = 1,
                  link_confidence_gate: float = 0.40,
                  b1v3_fallback) -> dict:
    """Execute one B4_v3 step end-to-end."""
    info = hybrid_retrieve_tables(question, tables_meta, db_id, k_tables=5,
                                   use_bm25=True, use_ngram=True)
    selected = info["selected_table_indexes"]
    link_conf = info["confidence"]
    overprune = info["reduction_ratio"] >= 0.85

    # Planner gate
    if not should_invoke_planner(link_conf, link_confidence_gate):
        sql = b1v3_fallback(question, db_id, tables_meta,
                            build_full_schema=build_full_schema,
                            build_reduced_schema=build_reduced_schema,
                            gen=gen)
        return {"sql": sql, "path": "skip_planner_low_confidence",
                "plan": None, "plan_error": "low_confidence",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": False,
                "candidates": [], "repair_count": 0}

    if overprune:
        shortlist_schema = build_full_schema(db_id)
    else:
        shortlist_schema = build_reduced_schema(db_id, selected)
    fk_sum = build_fk_summary(tables_meta)
    plan_prompt = make_compact_planner_prompt(question, shortlist_schema, fk_summary=fk_sum, evidence=evidence)
    raw_plan = gen(plan_prompt, max_new=256)
    plan_obj, plan_err = parse_plan_v2(raw_plan)
    if plan_obj is not None and validator is not None:
        try:
            validator.validate(plan_obj)
        except Exception as exc:
            plan_err = f"schema_validation:{type(exc).__name__}:{str(exc)[:100]}"
            plan_obj = None
    if plan_obj is None:
        sql = b1v3_fallback(question, db_id, tables_meta,
                            build_full_schema=build_full_schema,
                            build_reduced_schema=build_reduced_schema,
                            gen=gen)
        return {"sql": sql, "path": "b1v3_fallback_invalid_plan",
                "plan": None, "plan_error": plan_err,
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": True,
                "candidates": [], "repair_count": 0}

    # Multi-candidate synthesis on full schema
    full_schema = build_full_schema(db_id)
    synth_prompt = make_compact_synth_prompt(question, plan_obj, full_schema)
    raw_cands = gen_multi(synth_prompt, max_new=256, n=k_candidates,
                          temperature=0.7, top_p=0.95, top_k=50)
    schema_tn = (tables_meta.get("table_names_original") or
                 tables_meta.get("table_names") or [])
    plan_tables = plan_obj.get("tables") or []

    cands = []
    for raw in raw_cands:
        sql = _extract_sql(raw)
        ok, reason = is_safe_select(sql)
        executable, rows, err = (False, [], f"unsafe:{reason}") if not ok else executor(sql)
        sd = score_candidate(sql, executable, ok, schema_tn,
                              plan_tables=plan_tables, repair_count=0,
                              rows_returned=(len(rows) if rows is not None else None))
        cands.append({"sql": sql, "exec": executable, "safe_select": ok,
                       "rows": rows or [], "score": sd["score"],
                       "score_dict": sd, "err": err})

    chosen = pick_best(cands, min_margin=0.05)
    repair_count = 0
    if chosen is None:
        # Repair attempt on first candidate
        first = cands[0] if cands else None
        if first is not None:
            for _ in range(repair_depth):
                rep_prompt = make_repair_prompt(question, plan_obj, full_schema, first["sql"], first.get("err",""))
                rep_raw = gen(rep_prompt, max_new=256)
                rep_sql = _extract_sql(rep_raw)
                ok_r, _ = is_safe_select(rep_sql)
                if not ok_r: break
                executable, rows, err = executor(rep_sql)
                if executable:
                    sd = score_candidate(rep_sql, True, True, schema_tn,
                                         plan_tables=plan_tables, repair_count=repair_count+1,
                                         rows_returned=(len(rows) if rows is not None else None))
                    chosen = {"sql": rep_sql, "exec": True, "safe_select": True,
                              "rows": rows, "score": sd["score"], "score_dict": sd,
                              "err": "", "repaired": True}
                    repair_count += 1
                    break
                first = {"sql": rep_sql, "exec": False, "safe_select": True,
                         "rows": [], "score": 0.05, "err": err}
                repair_count += 1

    if chosen is None:
        sql = b1v3_fallback(question, db_id, tables_meta,
                            build_full_schema=build_full_schema,
                            build_reduced_schema=build_reduced_schema,
                            gen=gen)
        return {"sql": sql, "path": "b1v3_fallback_no_executable",
                "plan": plan_obj, "plan_error": "",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": True,
                "candidates": [c["sql"] for c in cands], "repair_count": repair_count}

    return {"sql": chosen["sql"],
            "path": ("multicand" + (f"_repair_{repair_count}" if repair_count else "")),
            "plan": plan_obj, "plan_error": "",
            "selected_tables": selected, "link_confidence": link_conf,
            "fallback_used": False, "planner_used": True,
            "candidates": [c["sql"] for c in cands], "repair_count": repair_count}
