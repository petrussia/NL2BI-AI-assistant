"""B2_v4: planner-gated Plan→SQL with v4 plan schema.

Differences vs B2_v3:
1. Uses `plan_schema_v4.json` (extended fields: nested_needed, set_operation,
   time_grain, arithmetic, join_paths with provenance, filter_value_source,
   plan_confidence).
2. Planner gate threshold raised to 0.45 (vs 0.40 in v3) — be more conservative.
3. For low link_confidence we fall back to **B0** (full schema, no planner)
   instead of B1_v3 — full schema gives the synth model more room to recover.
4. Optional benchmark `evidence` (BIRD) injected into planner context.
5. Record `plan_valid`, `planner_used`, `fallback_reason`, `repair_count`.
"""
from __future__ import annotations
import re

from baselines_b1_v3 import link_for_b1v3
from planner_gate import (
    parse_plan_v2, make_compact_planner_prompt, make_compact_synth_prompt,
    make_repair_prompt, build_fk_summary, is_safe_select,
)


def _extract_sql(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"(?is)(select\b.*)", text)
    if m: text = m.group(1).strip()
    text = text.split("\n\n")[0].strip()
    if ";" in text: text = text.split(";", 1)[0].strip()
    return text.rstrip(";") + ";"


def run_b2v4_step(question: str, db_id: str, tables_meta: dict,
                  *,
                  build_full_schema, build_reduced_schema,
                  gen, validator, executor,
                  evidence: str = "",
                  repair_depth: int = 1,
                  link_confidence_gate: float = 0.45,
                  b0_fallback,
                  b1v3_fallback) -> dict:
    """Execute one B2_v4 step end-to-end. ``executor``: (sql) -> (executable, rows, err)."""
    info = link_for_b1v3(question, db_id, tables_meta)
    selected = info["selected_table_indexes"]
    fb_used = info["fallback_used"]
    link_conf = info["link_confidence"]

    # Planner gate — if we don't trust the linker, B0 fallback (full schema, no planner)
    if not fb_used and link_conf < link_confidence_gate:
        sql = b0_fallback(question, db_id, tables_meta,
                           build_full_schema=build_full_schema, gen=gen)
        return {"sql": sql, "path": "b0_fallback_low_link_confidence",
                "plan": None, "plan_error": f"link_confidence_below_{link_confidence_gate}",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": False, "plan_valid": False,
                "fallback_reason": "low_link_confidence", "repair_count": 0}

    # Compact planner with optional evidence
    if fb_used:
        shortlist_schema = build_full_schema(db_id)
    else:
        shortlist_schema = build_reduced_schema(db_id, selected)
    fk_sum = build_fk_summary(tables_meta)
    plan_prompt = make_compact_planner_prompt(question, shortlist_schema,
                                               fk_summary=fk_sum, evidence=evidence)
    raw_plan = gen(plan_prompt, max_new=256)
    plan_obj, plan_err = parse_plan_v2(raw_plan)
    plan_valid = False
    if plan_obj is not None and validator is not None:
        try:
            validator.validate(plan_obj)
            plan_valid = True
        except Exception as exc:
            plan_err = f"schema_validation:{type(exc).__name__}:{str(exc)[:100]}"
            plan_obj = None
    elif plan_obj is not None:
        plan_valid = True

    if plan_obj is None:
        sql = b1v3_fallback(question, db_id, tables_meta,
                            build_full_schema=build_full_schema,
                            build_reduced_schema=build_reduced_schema,
                            gen=gen)
        return {"sql": sql, "path": "b1v3_fallback_invalid_plan",
                "plan": None, "plan_error": plan_err,
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": True, "plan_valid": False,
                "fallback_reason": "invalid_plan", "repair_count": 0}

    full_schema = build_full_schema(db_id)
    synth_prompt = make_compact_synth_prompt(question, plan_obj, full_schema)
    raw_sql = gen(synth_prompt, max_new=256)
    sql = _extract_sql(raw_sql)

    ok, reason = is_safe_select(sql)
    if not ok:
        sql_fb = b1v3_fallback(question, db_id, tables_meta,
                                build_full_schema=build_full_schema,
                                build_reduced_schema=build_reduced_schema,
                                gen=gen)
        return {"sql": sql_fb, "path": f"b1v3_fallback_unsafe:{reason}",
                "plan": plan_obj, "plan_error": "",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": True, "plan_valid": True,
                "fallback_reason": f"unsafe_sql:{reason}", "repair_count": 0}

    executable, rows, err = executor(sql)
    repair_count = 0
    while not executable and repair_count < repair_depth:
        rep_prompt = make_repair_prompt(question, plan_obj, full_schema, sql, err)
        rep_raw = gen(rep_prompt, max_new=256)
        rep_sql = _extract_sql(rep_raw)
        ok_r, _ = is_safe_select(rep_sql)
        if not ok_r: break
        sql = rep_sql; repair_count += 1
        executable, rows, err = executor(sql)

    if not executable:
        sql_fb = b1v3_fallback(question, db_id, tables_meta,
                                build_full_schema=build_full_schema,
                                build_reduced_schema=build_reduced_schema,
                                gen=gen)
        return {"sql": sql_fb, "path": f"b1v3_fallback_repair_failed_{repair_count}",
                "plan": plan_obj, "plan_error": "",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": True, "plan_valid": True,
                "fallback_reason": "repair_failed", "repair_count": repair_count}

    return {"sql": sql,
            "path": ("plan_then_synth" if repair_count == 0 else f"plan_repair_{repair_count}"),
            "plan": plan_obj, "plan_error": "",
            "selected_tables": selected, "link_confidence": link_conf,
            "fallback_used": False, "planner_used": True, "plan_valid": True,
            "fallback_reason": "", "repair_count": repair_count}
