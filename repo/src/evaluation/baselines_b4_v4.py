"""B4_v4: non-harmful full stack — multi-source candidate pool with risk-aware ranker.

Generates up to 4 candidates per query:
  - B0  (direct full schema)
  - B1_v3 (bidirectional linker)
  - B3_v4 (hybrid retrieval with optional evidence)
  - B2_v4 (planner only if gate passes)

Picks the best via candidate_ranker_v4. Critical non-harm rule: when the score
margin is small the ranker prefers a lower-risk source (B0 > B1_v3 > B3_v4 > B2_v4),
so the layered baseline cannot regress below B0 by more than a single bad
candidate's worth.
"""
from __future__ import annotations
import re

from baselines_b1_v3 import link_for_b1v3
from baselines_b3_v4 import retrieve_for_b3v4
from baselines_b2_v4 import run_b2v4_step
from planner_gate import is_safe_select
from candidate_ranker_v4 import score_candidate_v4, pick_best_v4


def _extract_sql(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"(?is)(select\b.*)", text)
    if m: text = m.group(1).strip()
    text = text.split("\n\n")[0].strip()
    if ";" in text: text = text.split(";", 1)[0].strip()
    return text.rstrip(";") + ";"


def run_b4v4_step(question: str, db_id: str, tables_meta: dict,
                   *,
                   build_full_schema, build_reduced_schema,
                   gen, validator, executor,
                   evidence: str = "",
                   include_planner: bool = True,
                   repair_depth: int = 1,
                   b0_fallback, b1v3_fallback) -> dict:
    """Execute one B4_v4 step. Returns dict with chosen sql + per-candidate audit."""
    candidates_audit = []
    schema_tn = (tables_meta.get("table_names_original") or
                 tables_meta.get("table_names") or [])

    # Candidate 1: B0
    full_schema = build_full_schema(db_id)
    import textwrap
    b0_prompt = textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {full_schema}

    Question: {question}
    SQL:
    """).strip()
    b0_sql = _extract_sql(gen(b0_prompt, max_new=256))
    ok_b0, _ = is_safe_select(b0_sql)
    exb_b0, rows_b0, err_b0 = (False, [], 'unsafe') if not ok_b0 else executor(b0_sql)
    sd_b0 = score_candidate_v4(b0_sql, "candidate_b0",
                                is_executable=exb_b0, is_safe_select=ok_b0,
                                rows=rows_b0, schema_tables=schema_tn,
                                plan_tables=[], link_confidence=1.0,
                                prompt_chars=len(b0_prompt))
    candidates_audit.append({"source":"candidate_b0", "sql": b0_sql,
                              "exec": exb_b0, "safe": ok_b0,
                              "rows": rows_b0 or [], "score": sd_b0["score"],
                              "score_dict": sd_b0})

    # Candidate 2: B1_v3
    info_b1 = link_for_b1v3(question, db_id, tables_meta)
    if info_b1["fallback_used"]:
        b1_schema = build_full_schema(db_id)
    else:
        b1_schema = build_reduced_schema(db_id, info_b1["selected_table_indexes"])
    b1_prompt = textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {b1_schema}

    Question: {question}
    SQL:
    """).strip()
    b1_sql = _extract_sql(gen(b1_prompt, max_new=256))
    ok_b1, _ = is_safe_select(b1_sql)
    exb_b1, rows_b1, err_b1 = (False, [], 'unsafe') if not ok_b1 else executor(b1_sql)
    sd_b1 = score_candidate_v4(b1_sql, "candidate_b1v3",
                                is_executable=exb_b1, is_safe_select=ok_b1,
                                rows=rows_b1, schema_tables=schema_tn,
                                plan_tables=info_b1.get("table_first_set",[]),
                                link_confidence=info_b1["link_confidence"],
                                prompt_chars=len(b1_prompt))
    candidates_audit.append({"source":"candidate_b1v3", "sql": b1_sql,
                              "exec": exb_b1, "safe": ok_b1,
                              "rows": rows_b1 or [], "score": sd_b1["score"],
                              "score_dict": sd_b1})

    # Candidate 3: B3_v4 (with evidence)
    info_b3 = retrieve_for_b3v4(question, db_id, tables_meta)
    if info_b3["fallback_used"]:
        b3_schema = build_full_schema(db_id)
    else:
        b3_schema = build_reduced_schema(db_id, info_b3["selected_table_indexes"])
    extra = f"\n\nDomain hint:\n{evidence}" if evidence and not info_b3["fallback_used"] else ""
    b3_prompt = textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {b3_schema}{extra}

    Question: {question}
    SQL:
    """).strip()
    b3_sql = _extract_sql(gen(b3_prompt, max_new=256))
    ok_b3, _ = is_safe_select(b3_sql)
    exb_b3, rows_b3, err_b3 = (False, [], 'unsafe') if not ok_b3 else executor(b3_sql)
    sd_b3 = score_candidate_v4(b3_sql, "candidate_b3v4",
                                is_executable=exb_b3, is_safe_select=ok_b3,
                                rows=rows_b3, schema_tables=schema_tn,
                                plan_tables=[], link_confidence=info_b3["confidence"],
                                prompt_chars=len(b3_prompt))
    candidates_audit.append({"source":"candidate_b3v4", "sql": b3_sql,
                              "exec": exb_b3, "safe": ok_b3,
                              "rows": rows_b3 or [], "score": sd_b3["score"],
                              "score_dict": sd_b3})

    # Candidate 4: B2_v4 (planner) — only if gate passes
    planner_attempted = False
    if include_planner:
        try:
            step_b2 = run_b2v4_step(question, db_id, tables_meta,
                                     build_full_schema=build_full_schema,
                                     build_reduced_schema=build_reduced_schema,
                                     gen=gen, validator=validator, executor=executor,
                                     evidence=evidence, repair_depth=repair_depth,
                                     b0_fallback=b0_fallback, b1v3_fallback=b1v3_fallback)
            planner_attempted = True
            b2_sql = step_b2["sql"]
            ok_b2, _ = is_safe_select(b2_sql)
            exb_b2, rows_b2, err_b2 = (False, [], 'unsafe') if not ok_b2 else executor(b2_sql)
            source = "candidate_b2v4_repair" if "repair" in step_b2.get("path","") else "candidate_b2v4"
            sd_b2 = score_candidate_v4(b2_sql, source,
                                        is_executable=exb_b2, is_safe_select=ok_b2,
                                        rows=rows_b2, schema_tables=schema_tn,
                                        plan_tables=(step_b2.get("plan") or {}).get("tables", []),
                                        link_confidence=step_b2.get("link_confidence", 0.5),
                                        repair_count=step_b2.get("repair_count",0),
                                        prompt_chars=len(b2_sql))
            candidates_audit.append({"source": source, "sql": b2_sql,
                                      "exec": exb_b2, "safe": ok_b2,
                                      "rows": rows_b2 or [], "score": sd_b2["score"],
                                      "score_dict": sd_b2,
                                      "plan": step_b2.get("plan"),
                                      "planner_used": step_b2.get("planner_used", False),
                                      "fallback_reason": step_b2.get("fallback_reason","")})
        except Exception as exc:
            candidates_audit.append({"source":"candidate_b2v4", "sql": "", "exec": False,
                                      "safe": False, "rows": [], "score": 0.0,
                                      "score_dict": {"reason": f"planner_exception:{exc}"}})

    chosen = pick_best_v4(candidates_audit, min_margin=0.04)
    return {
        "sql": chosen["sql"] if chosen else b0_sql,
        "selected_candidate_source": chosen["source"] if chosen else "candidate_b0_fallback_none_executable",
        "candidates": [{"source": c["source"], "sql": c["sql"], "score": c["score"],
                         "exec": c["exec"], "safe": c["safe"]} for c in candidates_audit],
        "candidate_count": len(candidates_audit),
        "selected_tables": info_b1["selected_table_indexes"],
        "link_confidence": info_b1["link_confidence"],
        "fallback_used": info_b1["fallback_used"],
        "planner_used": planner_attempted,
    }
