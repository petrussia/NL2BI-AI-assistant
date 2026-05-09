"""B1R: cross-DB lexical retrieval + B1 reduced schema + direct SQL.

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
    return textwrap.dedent(f"""
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema (which was retrieved from a multi-database collection).
    Return SQL only, no markdown and no explanation.

    {reduced_schema_context}

    Question: {question}
    SQL:
    """).strip()
