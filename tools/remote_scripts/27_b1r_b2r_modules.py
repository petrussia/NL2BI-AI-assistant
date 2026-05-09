# Stage 5 (a): author retrieval + baselines_b1r + baselines_b2r modules.

import datetime as dt
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
REPO = PROJECT_ROOT / 'repo'
EVAL_DIR = REPO / 'src' / 'evaluation'
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 1. retrieval.py (cross-DB lexical retrieval) ----------
retrieval_src = '''"""Cross-DB lexical retrieval helper for B1R / B2R baselines.

Given a question and the full tables_map (all 166 Spider DBs), score each DB
by token overlap of the question against (db_id + table_names + column_names).
Return top-k candidate DBs.

Weighting:
  db_id    x3 per token match
  table    x2 per token match (per table; sum over all tables in DB)
  column   x1 per token match

Tie-break alphabetical on db_id.
"""
from __future__ import annotations
import re

STOP = {
    "a","an","the","of","in","on","at","for","to","from","by","with","is","are","was","were",
    "what","which","who","whom","whose","how","many","much","show","list","find","give","me",
    "all","each","every","any","do","does","did","that","this","there","their","them","they",
    "as","or","and","be","been","has","have","had"
}


def _toks(s):
    parts = re.split(r"[\\s_]+", str(s).lower())
    return {p for p in parts if p and p not in STOP and len(p) > 1}


def score_db(question_tokens: set, tables_obj: dict) -> dict:
    """Return per-DB score breakdown for ranking + audit."""
    db_id = tables_obj.get("db_id", "")
    name_score = len(question_tokens & _toks(db_id)) * 3
    table_score = 0
    table_hits = []
    for t in (tables_obj.get("table_names_original") or tables_obj.get("table_names") or []):
        ov = len(question_tokens & _toks(t))
        if ov > 0:
            table_hits.append((t, ov))
            table_score += ov * 2
    column_score = 0
    column_hits = []
    for ti, col in (tables_obj.get("column_names_original") or tables_obj.get("column_names") or []):
        if ti < 0:
            continue
        ov = len(question_tokens & _toks(col))
        if ov > 0:
            column_hits.append((col, ov))
            column_score += ov * 1
    return {
        "db_id": db_id,
        "score": name_score + table_score + column_score,
        "name_score": name_score,
        "table_score": table_score,
        "column_score": column_score,
        "table_hits": table_hits[:5],
        "column_hits": column_hits[:5],
    }


def retrieve_db(question: str, tables_map: dict, top_k: int = 3):
    """Score all DBs in tables_map; return top_k as a list of dicts.

    Stable order: sort by (-score, db_id).
    """
    qt = _toks(question)
    scored = [score_db(qt, tables_obj) for tables_obj in tables_map.values()]
    scored.sort(key=lambda x: (-x["score"], x["db_id"]))
    return scored[:top_k], qt
'''
(EVAL_DIR / 'retrieval.py').write_text(retrieval_src, encoding='utf-8')
print(f'WROTE {EVAL_DIR / "retrieval.py"} ({(EVAL_DIR / "retrieval.py").stat().st_size} B)')

# ---------- 2. baselines_b1r.py ----------
b1r_src = '''"""B1R: cross-DB lexical retrieval + B1 reduced schema + direct SQL.

Pipeline per item:
  question -> retrieval.retrieve_db (top-3, use top-1) -> retrieved_db_id
  within retrieved_db: lexical_schema_linking (reused from baselines.py)
  build reduced_schema_context for retrieved_db
  single-shot prompt -> SQL
  execute against retrieved_db (NOT gold)
  EX = match against gold rows from gold_db
"""
from __future__ import annotations

import textwrap


def make_b1r_prompt(question: str, reduced_schema_context: str) -> str:
    return textwrap.dedent(f\"\"\"
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema (which was retrieved from a multi-database collection).
    Return SQL only, no markdown and no explanation.

    {reduced_schema_context}

    Question: {question}
    SQL:
    \"\"\").strip()
'''
(EVAL_DIR / 'baselines_b1r.py').write_text(b1r_src, encoding='utf-8')
print(f'WROTE {EVAL_DIR / "baselines_b1r.py"} ({(EVAL_DIR / "baselines_b1r.py").stat().st_size} B)')

# ---------- 3. baselines_b2r.py ----------
b2r_src = '''"""B2R: cross-DB lexical retrieval + Plan->SQL.

Pipeline per item:
  question -> retrieval.retrieve_db (top-3, use top-1)
  within retrieved_db: lexical_schema_linking
  reduced_schema_context for retrieved_db
  baselines_b2_v1.make_plan_prompt -> plan_raw -> parse_and_validate_plan
  if valid: baselines_b2_v1.make_plan_to_sql_prompt -> SQL
  execute against retrieved_db
"""
from __future__ import annotations

# B2R reuses the v1 planner + plan->SQL prompt builders directly (no need
# to duplicate prompts here). The only B2R-specific concern is that the
# schema in the prompt comes from a *retrieved* DB, not the gold one.
'''
(EVAL_DIR / 'baselines_b2r.py').write_text(b2r_src, encoding='utf-8')
print(f'WROTE {EVAL_DIR / "baselines_b2r.py"} ({(EVAL_DIR / "baselines_b2r.py").stat().st_size} B)')

print('STATUS=DONE')
