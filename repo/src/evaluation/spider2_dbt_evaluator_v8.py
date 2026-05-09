"""spider2_dbt_evaluator_v8 — Spider2-DBT task scorer facade.

Re-exports the official_eval shim from the bridge. The actual evaluator
is on the server (vendor/Spider2/spider2-dbt/evaluation_suite/evaluate.py)
and runs after `dbt run` / `dbt test` succeed.

For details on `official_score` / `official_rc` see
`outputs/logs/spider2_dbt_metrics_contract.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'spider2_dbt_bridge'))


def task_success(score: dict | None) -> bool:
    """Spider2-DBT task is 'success' when matched > 0 (rate=1.0 for n=1)."""
    if not score: return False
    matched = score.get('matched', 0) or 0
    return matched > 0
