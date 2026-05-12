"""B2_v3: compact planner over a shortlist schema with strict B1_v3 fallback.

Pipeline:
1. Bidirectional schema linker (from baselines_b1_v3) -> selected_table_indexes,
   link_confidence.
2. Planner gate: if link_confidence < threshold -> fall back directly to B1_v3.
3. Compact planner: shortlist schema + FK summary + (optional) evidence.
4. Plan validator: jsonschema (plan_schema_v2). Invalid -> fall back to B1_v3.
5. Synthesizer: full schema + plan -> SQL. (Synthesis context is RICHER than
   planner context to recover from over-pruning.)
6. Executor + bounded repair (depth 1 default). On total failure -> fall back
   to B1_v3.

Public API:
- run_b2v3_step(question, db_id, tables_meta, *, build_full_schema, build_reduced_schema,
                 gen, validator, evidence='', repair_depth=1, link_confidence_gate=0.40,
                 b1v3_fallback) -> dict
"""
from __future__ import annotations
import re

from baselines_b1_v3 import link_for_b1v3
from planner_gate import (
    parse_plan_v2, should_invoke_planner, make_compact_planner_prompt,
    make_compact_synth_prompt, make_repair_prompt, build_fk_summary, is_safe_select,
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


def run_b2v3_step(question: str, db_id: str, tables_meta: dict,
                  *,
                  build_full_schema, build_reduced_schema,
                  gen, validator, executor,
                  evidence: str = "",
                  repair_depth: int = 1,
                  link_confidence_gate: float = 0.40,
                  b1v3_fallback) -> dict:
    """Execute one B2_v3 step end-to-end. ``executor`` is a callable
    (sql) -> (executable: bool, rows: list|None, error_msg: str)."""
    info = link_for_b1v3(question, db_id, tables_meta)
    selected = info["selected_table_indexes"]
    fb_used = info["fallback_used"]
    link_conf = info["link_confidence"]

    # Decide whether to even run the planner
    if not should_invoke_planner(link_conf, link_confidence_gate):
        sql = b1v3_fallback(question, db_id, tables_meta,
                            build_full_schema=build_full_schema,
                            build_reduced_schema=build_reduced_schema,
                            gen=gen)
        return {"sql": sql, "path": "skip_planner_low_confidence",
                "plan": None, "plan_error": f"link_confidence_below_{link_confidence_gate}",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": False, "repair_count": 0}

    # Compact planner
    if fb_used:
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
                "fallback_used": True, "planner_used": True, "repair_count": 0}

    # Synthesis with FULL schema (richer)
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
                "fallback_used": True, "planner_used": True, "repair_count": 0}

    # Executor + bounded repair
    executable, rows, err = executor(sql)
    repair_count = 0
    while not executable and repair_count < repair_depth:
        rep_prompt = make_repair_prompt(question, plan_obj, full_schema, sql, err)
        rep_raw = gen(rep_prompt, max_new=256)
        rep_sql = _extract_sql(rep_raw)
        ok_r, _ = is_safe_select(rep_sql)
        if not ok_r: break
        sql = rep_sql
        repair_count += 1
        executable, rows, err = executor(sql)

    if not executable:
        sql_fb = b1v3_fallback(question, db_id, tables_meta,
                                build_full_schema=build_full_schema,
                                build_reduced_schema=build_reduced_schema,
                                gen=gen)
        return {"sql": sql_fb, "path": f"b1v3_fallback_repair_failed_after_{repair_count}",
                "plan": plan_obj, "plan_error": "",
                "selected_tables": selected, "link_confidence": link_conf,
                "fallback_used": True, "planner_used": True, "repair_count": repair_count}

    return {"sql": sql, "path": ("plan_then_synth" if repair_count == 0 else f"plan_repair_{repair_count}"),
            "plan": plan_obj, "plan_error": "",
            "selected_tables": selected, "link_confidence": link_conf,
            "fallback_used": False, "planner_used": True, "repair_count": repair_count}
