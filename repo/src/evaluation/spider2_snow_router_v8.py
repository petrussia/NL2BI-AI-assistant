"""spider2_snow_router_v8 — Spider2-Snow benchmark item router.

Spider2-Snow is a Snowflake-hosted benchmark. This router is intentionally
minimal: every item routes to the SF lane. It exists so the runner has a
single, dialect-aware classifier per benchmark.

For Spider2-Lite (mixed engine) we have a different router; do not confuse
the two.
"""
from __future__ import annotations


def classify(item: dict) -> dict:
    """Return {'lane': 'A_sf', 'engine': 'snowflake', ...}."""
    iid = str(item.get('instance_id') or '')
    db = str(item.get('db') or '')
    return {
        'instance_id': iid,
        'db': db,
        'lane': 'A_sf',
        'engine': 'snowflake',
        'question': item.get('question', ''),
        'external_knowledge': item.get('external_knowledge', ''),
    }
