"""spider2_snow_candidate_generator_v8 — multi-candidate SQL generator for SF lane.

Mirrors `spider2_bq_candidate_generator_v8` but Snowflake-specific:
- C0_direct        — short prompt with selected schema subset
- C1_retrieval_docs — schema + retrieved doc snippets
- C2_cte_decomp    — explicit CTE/decomposition prompt
- C4_tool_loop     — single-turn schema-search probe (lightweight, optional)

Each candidate is a dict {source, sql, prompt_chars, ...}. Verification is
the caller's job.
"""
from __future__ import annotations

from typing import Callable

from spider2_agent_v7 import _extract_sql
from spider2_sf_schema_index_v8 import SfSchemaIndex
from spider2_sf_prompting_v8 import (
    direct_prompt, retrieval_prompt, cte_prompt,
)


def _gen_one(prompt: str, gen: Callable, max_new: int) -> str:
    try:
        raw = gen(prompt, max_new=max_new)
    except Exception as exc:
        return f'-- gen_error: {type(exc).__name__}'
    return _extract_sql(raw) or ''


def make_candidates(question: str, idx: SfSchemaIndex,
                     selected_keys: list[str], *,
                     gen: Callable,
                     include_direct: bool = True,
                     include_retrieval: bool = True,
                     include_cte: bool = True,
                     include_tool_loop: bool = False,
                     max_cols: int = 22,
                     max_new_sql: int = 800,
                     max_new_cte: int = 1100) -> list[dict]:
    cands: list[dict] = []
    if include_direct:
        p = direct_prompt(question, idx, selected_keys, max_cols=max_cols)
        cands.append({'source': 'C0_direct',
                      'sql': _gen_one(p, gen, max_new_sql),
                      'prompt_chars': len(p)})
    if include_retrieval:
        p = retrieval_prompt(question, idx, selected_keys, max_cols=max_cols)
        cands.append({'source': 'C1_retrieval_docs',
                      'sql': _gen_one(p, gen, max_new_sql),
                      'prompt_chars': len(p)})
    if include_cte:
        p = cte_prompt(question, idx, selected_keys, max_cols=max_cols)
        cands.append({'source': 'C2_cte_decomp',
                      'sql': _gen_one(p, gen, max_new_cte),
                      'prompt_chars': len(p)})
    if include_tool_loop:
        # Lightweight tool-loop seed: ask model to first list candidate tables,
        # then propose SQL. We treat this as a single-pass with explicit hint.
        tl_prompt = (
            "You are exploring a Snowflake database. Given the question and a "
            "shortlist of tables, first identify the 3-5 most relevant tables "
            "for the answer, then write the SQL.\n\n"
            f"QUESTION: {question}\n\n"
            f"SCHEMA SUBSET (top tables):\n"
            + '\n'.join(f"- {k}" for k in selected_keys[:max_cols])
            + "\n\nRespond with SQL inside ```sql ... ``` fence.\n"
        )
        cands.append({'source': 'C4_tool_loop',
                      'sql': _gen_one(tl_prompt, gen, max_new_sql),
                      'prompt_chars': len(tl_prompt)})
    return cands
