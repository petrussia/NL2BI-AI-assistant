"""B2R: cross-DB lexical retrieval + Plan->SQL.

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
