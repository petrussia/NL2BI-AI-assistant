"""spider2_lite_router_v8 — lane router for Spider2-Lite (mixed-engine).

Spider2-Lite contains BigQuery, Snowflake, and SQLite items in one
benchmark file. Engine is encoded by `instance_id` prefix:
  - `bq*`, `ga*`, raw lowercase prefixes that aren't `sf` or `local` → BigQuery
  - `sf*` → Snowflake
  - `local*` → SQLite (stub)

Returns a per-item routing dict the runner uses to pick the right agent.

NOTE: SQLite items execute against a *stub* sample-rows database the
Spider2 repo provides; their results are NOT comparable to official EX.
The runner MUST mark them with `lane='C_sqlite_stub'` and `non_comparable=True`.
"""
from __future__ import annotations


def classify(item: dict) -> dict:
    iid = str(item.get('instance_id') or '').lower()
    db = str(item.get('db') or '')
    if iid.startswith('local'):
        lane = 'C_sqlite_stub'; engine = 'sqlite'; non_comp = True
    elif iid.startswith('sf'):
        lane = 'A_sf'; engine = 'snowflake'; non_comp = False
    else:
        lane = 'A_bq'; engine = 'bigquery'; non_comp = False
    return {
        'instance_id': item.get('instance_id', ''),
        'db': db,
        'lane': lane,
        'engine': engine,
        'non_comparable': non_comp,
        'question': item.get('question', ''),
        'external_knowledge': item.get('external_knowledge', ''),
    }
