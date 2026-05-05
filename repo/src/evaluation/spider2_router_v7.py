"""spider2_router_v7 — per-item lane assignment for Spider2-Lite.

Spider2-Lite items split across multiple execution backends. Each backend
needs different credentials and capabilities; we cannot run all 547 items
through a single executor. The router decides — *before* the agent runs
— which lane each item belongs to, so the runner can route honestly.

Lanes:
  A_bq      — BigQuery; gold dialect is bigquery AND we have credentials
              AND the referenced dataset is in the BQ access whitelist.
              The only lane where we report execution_match (== official EX).
  A_sf      — Snowflake; we don't have SF creds; skipped with explicit
              `blocked_snowflake` reason.
  B_sqlite  — Local SQLite stub; resource/databases/sqlite/<db>/<db>.sqlite
              exists. Executable WITHOUT any cloud creds, but the underlying
              data is a sample, not the real warehouse — so the result is
              an oracle-on-sample number, not official EX. Reported in a
              separate column with explicit "non-comparable" annotation.
  C_struct  — fallback; no execution backend matches. We compute parse +
              dialect-valid + schema-valid structural features only.

Ladder of decision (first match wins):
  1. native SQLite stub present  -> B_sqlite
  2. dialect == 'bigquery' and BQ creds available and dataset in whitelist
                                  -> A_bq
  3. dialect == 'snowflake'       -> A_sf
  4. dialect == 'bigquery' and (no creds OR dataset out of whitelist)
                                  -> C_struct (with reason)
  5. anything else                -> C_struct

The router has no GPU / network deps — it's a thin metadata function.

Public API:
  route_item(item, *, sqlite_root, bq_creds_present, bq_dataset_whitelist)
    -> {lane, reason, dialect, db_id, sqlite_path, bq_dataset_hint}
  summarize_routes(items, ...) -> {by_lane: Counter, by_dialect: Counter,
                                    sqlite_avail_count, bq_avail_count, ...}
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Iterable


SUPPORTED_DIALECTS = ('sqlite', 'bigquery', 'snowflake')


def _detect_dialect(item: dict) -> str:
    """Spider2-Lite encodes dialect in instance_id prefix and/or db root.

    Empirically (547 items in spider2-lite.jsonl):
      sf*    -> snowflake (207)
      bq*    -> bigquery  (180)
      ga*    -> bigquery — Google Analytics public datasets (25)
      local* -> sqlite    (135)
    Some releases carry an explicit 'dialect' or 'db_engine' field.
    """
    if 'dialect' in item: return str(item['dialect']).lower()
    if 'db_engine' in item: return str(item['db_engine']).lower()
    iid = str(item.get('instance_id') or item.get('id') or '').lower()
    if iid.startswith('sf'): return 'snowflake'
    if iid.startswith('bq') or iid.startswith('ga'): return 'bigquery'
    if iid.startswith('local') or iid.startswith('sl'): return 'sqlite'
    db = str(item.get('db') or item.get('db_id') or '').lower()
    if 'snowflake' in db or db.startswith('sf'): return 'snowflake'
    if 'bigquery' in db or db.startswith('bq'): return 'bigquery'
    return 'unknown'


def _norm_db_name(s: str) -> str:
    """Normalize 'sqlite-sakila' / 'SQLITE_SAKILA' / 'sqlite sakila' -> same."""
    return re.sub(r'[\s_\-]+', '', (s or '').strip().lower())


def _db_id(item: dict) -> str:
    return str(item.get('db') or item.get('db_id') or '')


def _bq_dataset_hint(item: dict) -> str:
    """Best-effort guess at which BQ dataset this item touches.

    Real Spider2 items often don't tell you directly; we scrape
    backticked refs from the gold SQL if present, else from the question.
    Used only for whitelist matching, never for control flow once the
    lane is decided.
    """
    sources = []
    for k in ('gold_sql', 'sql', 'query', 'question'):
        v = item.get(k)
        if isinstance(v, str): sources.append(v)
    blob = ' '.join(sources)
    # `project.dataset.table` or `dataset.table`
    refs = re.findall(r'`([\w-]+(?:\.[\w-]+){1,2})`', blob)
    if refs: return refs[0]
    return ''


def route_item(item: dict, *,
                sqlite_root: str | Path | None = None,
                bq_creds_present: bool = False,
                bq_dataset_whitelist: Iterable[str] | None = None) -> dict:
    """Assign a lane to one item. See module docstring for the ladder.

    `sqlite_root` should point at `.../spider2_lite/.../resource/databases/sqlite`.
    `bq_dataset_whitelist` is a set/list of dataset identifiers (either
    `project.dataset` or just `dataset`) the BQ creds can read.
    """
    db = _db_id(item)
    dialect = _detect_dialect(item)
    sqlite_path = ''  # populated when a `<db>.sqlite` file is present (rare)
    sqlite_dir = ''   # populated when a stub-dir of DDL.csv + *.json is present
    if sqlite_root:
        root = Path(sqlite_root)
        # 1) direct `.sqlite` file (uncommon — Spider2 currently ships JSON stubs)
        for cand in (root / db / f'{db}.sqlite',
                     root / db.lower() / f'{db.lower()}.sqlite'):
            if cand.exists(): sqlite_path = str(cand); break
        # 2) stub dir match by normalized name (handles
        #    'sqlite-sakila' vs 'SQLITE_SAKILA')
        if not sqlite_path:
            target = _norm_db_name(db)
            for d in root.iterdir() if root.exists() else ():
                if d.is_dir() and _norm_db_name(d.name) == target:
                    if any(d.glob('*.json')) or (d / 'DDL.csv').exists():
                        sqlite_dir = str(d)
                    break

    bq_hint = _bq_dataset_hint(item)
    wl = set(bq_dataset_whitelist or [])

    # 1. Snowflake first — always blocked, dialect signals it from
    #    instance_id (`sf*`) regardless of whether a similarly-named
    #    sqlite dir happens to exist.
    if dialect == 'snowflake':
        return {'lane': 'A_sf', 'reason': 'blocked_snowflake_no_creds',
                'dialect': 'snowflake', 'db_id': db,
                'sqlite_path': '', 'sqlite_dir': '', 'bq_dataset_hint': bq_hint}

    # 2. BigQuery items — even if a sqlite stub dir happens to share the
    #    db name, the gold SQL is BigQuery-specific (UNNEST, _TABLE_SUFFIX,
    #    etc.); evaluating BQ candidates against a tiny local sample would
    #    silently disagree with the gold result rows. Route to A_bq.
    if dialect == 'bigquery' and bq_creds_present:
        match = (not wl) or any(
            bq_hint == w or bq_hint.startswith(w + '.') or w in bq_hint
            for w in wl)
        if match:
            return {'lane': 'A_bq', 'reason': 'bq_creds_and_dataset_match',
                    'dialect': 'bigquery', 'db_id': db,
                    'sqlite_path': '', 'sqlite_dir': '',
                    'bq_dataset_hint': bq_hint}
        return {'lane': 'C_struct', 'reason': 'bq_dataset_not_in_whitelist',
                'dialect': 'bigquery', 'db_id': db,
                'sqlite_path': '', 'sqlite_dir': '',
                'bq_dataset_hint': bq_hint}

    # 3. SQLite-dialect items — must have either a stub file or stub dir
    if sqlite_path or sqlite_dir:
        return {'lane': 'B_sqlite',
                'reason': 'sqlite_file_present' if sqlite_path else 'sqlite_stub_dir_present',
                'dialect': 'sqlite', 'db_id': db,
                'sqlite_path': sqlite_path, 'sqlite_dir': sqlite_dir,
                'bq_dataset_hint': bq_hint}

    # 4. BQ-dialect item but no creds — structural-only
    if dialect == 'bigquery':
        return {'lane': 'C_struct', 'reason': 'bq_creds_missing',
                'dialect': 'bigquery', 'db_id': db,
                'sqlite_path': '', 'sqlite_dir': '',
                'bq_dataset_hint': bq_hint}

    # 5. Unknown / other
    return {'lane': 'C_struct', 'reason': f'unknown_dialect:{dialect}',
            'dialect': dialect, 'db_id': db,
            'sqlite_path': '', 'bq_dataset_hint': bq_hint}


def summarize_routes(items: list[dict], **route_kwargs) -> dict:
    """Run route_item over every input and return a summary."""
    by_lane: Counter = Counter()
    by_dialect: Counter = Counter()
    by_reason: Counter = Counter()
    routes: list[dict] = []
    for it in items:
        r = route_item(it, **route_kwargs)
        routes.append(r)
        by_lane[r['lane']] += 1
        by_dialect[r['dialect']] += 1
        by_reason[r['reason']] += 1
    return {
        'n_total': len(items),
        'by_lane': dict(by_lane),
        'by_dialect': dict(by_dialect),
        'by_reason': dict(by_reason),
        'routes': routes,
    }
