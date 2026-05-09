"""candidate_selector_v18 — validator + minimal probe + selection policy.

Validator-first selection over a list of candidate SQLs. Re-uses the v16
schema-grounding validator behaviour by importing it lazily; for v18.0
we keep the validator inline-light (sqlglot parse + identifier residency
check) and skip the full mapper/repair stack to keep the v18 entry point
deterministic.

Probe layer is intentionally minimal in v18.0 (TODO: ambiguity probing
becomes meaningful only after we have an ambiguity bank — deferred to
v18.1). For now the probe step is a no-op that records 'no probe' for
each candidate.

Selection policy (in priority order):
  1. dry_run_ok (BQ live dry_run / explain) — first non-zero signal
  2. parse_ok (sqlglot in BQ dialect)
  3. schema_valid (identifiers exist in pack)
  4. preference for family A (deterministic) over B (LLM) when tied
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CandEval:
    family: str
    sql: str
    parse_ok: bool = False
    schema_valid: bool = False
    dry_run_ok: bool = False
    error_class: str = ''
    error_msg: str = ''
    notes: list = field(default_factory=list)


def _identifiers_in_sql(sql: str) -> set:
    # crude but predictable: pull all alphanumeric identifiers and
    # backquoted segments
    out = set()
    for m in re.findall(r'`([^`]+)`', sql):
        # Inside backticks BQ allows `proj.dataset.table` — split
        for part in m.split('.'):
            out.add(part)
    for m in re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', sql):
        out.add(m)
    return out


def parse_with_sqlglot_bq(sql: str) -> tuple:
    try:
        import sqlglot
        sqlglot.parse_one(sql, read='bigquery')
        return True, ''
    except Exception as e:
        return False, f'{type(e).__name__}:{str(e)[:200]}'


def schema_valid_against_pack(sql: str, pack: dict) -> tuple:
    pack_names = set()
    for d in pack.get('databases', []):
        pack_names.add(d['name'])
        for s in d.get('schemas', []):
            pack_names.add(s)
    for t in pack.get('tables', []):
        pack_names.add(t['table'])
        for c in t.get('columns', []):
            # columns may have struct paths; index by leaf and root
            pack_names.add(c['name'])
            pack_names.add(c['name'].split('.')[0])
    sql_idents = _identifiers_in_sql(sql)
    sql_keywords = {
        'SELECT','FROM','WHERE','GROUP','BY','ORDER','HAVING','AS','AND','OR',
        'NOT','IN','LIKE','BETWEEN','IS','NULL','TRUE','FALSE','LIMIT',
        'DISTINCT','ON','JOIN','LEFT','RIGHT','INNER','OUTER','UNION',
        'COUNT','SUM','AVG','MIN','MAX','CAST','EXTRACT','DATE','TIMESTAMP',
        'INT','INT64','FLOAT','STRING','ARRAY','STRUCT','UNNEST','SAFE_CAST',
        'OVER','PARTITION','WITH','EXISTS','TRY_CAST','THEN','CASE','WHEN','ELSE','END',
        'INTERVAL','CURRENT_DATE','CURRENT_TIMESTAMP','LATERAL','FLATTEN','INPUT',
        'DATETIME','TIME','BOOL','BOOLEAN','BYTES','NUMERIC','BIGNUMERIC','DESC','ASC',
    }
    leaks = []
    for tok in sql_idents:
        u = tok.upper()
        if u in sql_keywords:
            continue
        if tok in pack_names:
            continue
        if tok.isdigit() or len(tok) <= 1:
            continue
        # tolerate aliases (a, b, t1, t2 ... too short already filtered;
        # also allow common single-letter+digit aliases)
        if re.fullmatch(r'[a-z]\d?', tok):
            continue
        leaks.append(tok)
    return (not leaks), ('leaked:' + ','.join(leaks[:5])) if leaks else ''


def dry_run_bq(sql: str, *, max_bytes_billed: int = 1 * 1024**3) -> tuple:
    """Return (ok, error). Uses google-cloud-bigquery if available."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client()
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        if max_bytes_billed:
            cfg.maximum_bytes_billed = max_bytes_billed
        client.query(sql, job_config=cfg)
        return True, ''
    except Exception as e:
        return False, f'{type(e).__name__}:{str(e)[:300]}'


def evaluate_candidate(cand: dict, pack: dict, *, do_dry_run: bool = True) -> CandEval:
    sql = cand.get('sql') or ''
    ev = CandEval(family=cand.get('family', '?'), sql=sql)
    if not sql:
        ev.error_class = 'empty_sql'
        return ev
    pok, perr = parse_with_sqlglot_bq(sql)
    ev.parse_ok = pok
    if not pok:
        ev.error_class = 'parse_error'
        ev.error_msg = perr
    sok, serr = schema_valid_against_pack(sql, pack)
    ev.schema_valid = sok
    if not sok:
        ev.error_class = ev.error_class or 'schema_invalid'
        ev.error_msg = ev.error_msg or serr
    if do_dry_run and pok:
        dok, derr = dry_run_bq(sql)
        ev.dry_run_ok = dok
        if not dok:
            ev.error_class = ev.error_class or 'bq_dry_run_failed'
            ev.error_msg = ev.error_msg or derr
    return ev


def select(candidates: list, pack: dict, *, do_dry_run: bool = True) -> dict:
    evals = [evaluate_candidate(c, pack, do_dry_run=do_dry_run) for c in candidates]

    def score(ev: CandEval) -> tuple:
        return (
            int(ev.dry_run_ok),
            int(ev.parse_ok),
            int(ev.schema_valid),
            1 if ev.family == 'A' else 0,
        )

    chosen = max(range(len(evals)), key=lambda i: score(evals[i])) if evals else -1
    return {
        'evals': [ev.__dict__ for ev in evals],
        'chosen_idx': chosen,
        'chosen': evals[chosen].__dict__ if chosen >= 0 else None,
    }
