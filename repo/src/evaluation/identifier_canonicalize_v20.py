"""identifier_canonicalize_v20 — shared identifier-slot canonicaliser.

Stage A1 of the Phase 20 brief: one helper used by structured_plan_v18,
sql_renderer_v18, and candidate_selector_v18 so plan validation, SQL
rendering, and AST residency check all agree on what
`selected_database`, `selected_schema`, and `selected_tables` mean.

Phase 19 pilot50 traces showed the planner reliably emits FQN-form
`selected_tables` like
  "bigquery-public-data.google_analytics_sample.ga_sessions_20170201"
while the validator looked up *bare* names (`ga_sessions_20170201`) and
*non-canonical project/dataset slots*. The renderer happened to do its
own collapse but in a private function. Result: pilot50 plan_validation_ok
was 42% even though the SAME plans rendered as engine-acceptable SQL.

This module exposes a single function — `canonicalize_identifier_slots`
— whose output is the canonical, validator-friendly view of the plan's
identifier slots. The originals are preserved in the returned dict so
downstream callers (e.g. renderer, error reports) can still see what
the model actually emitted.

The implementation is intentionally pack-aware: a bare table name is
normalised to its `<base>_*` wildcard form when the pack lists at least
one date-shard sibling and the planner enumerated more than one shard.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional


_DATE_SHARD_RE = re.compile(r'^(?P<base>.+?)_(?P<date>\d{6,8})$')


def _split_fqn(value: str) -> list:
    """Split a possibly-FQN string like 'project.dataset.table' into parts."""
    return [p for p in (value or '').split('.') if p]


def _pack_known_projects(pack: dict) -> set:
    out = set()
    for d in pack.get('databases', []):
        if d.get('name'):
            out.add(d['name'])
    for t in pack.get('tables', []):
        if t.get('db'):
            out.add(t['db'])
    return out


def _pack_known_datasets(pack: dict) -> set:
    out = set()
    for d in pack.get('databases', []):
        for s in d.get('schemas', []):
            out.add(s)
    for t in pack.get('tables', []):
        if t.get('schema'):
            out.add(t['schema'])
    return out


def _pack_known_tables(pack: dict) -> set:
    return {t['table'] for t in pack.get('tables', [])}


def _pack_wildcard_bases(pack: dict) -> set:
    bases = set()
    for t in pack.get('tables', []):
        m = _DATE_SHARD_RE.match(t.get('table', ''))
        if m:
            bases.add(m.group('base'))
    for w in pack.get('wildcards', []) or []:
        if w.get('base'):
            bases.add(w['base'])
    return bases


def _canon_database(value: str, projects: set, datasets: set) -> str:
    """Normalise selected_database to a bare project name when possible.

    Accepts:
      - 'bigquery-public-data'                        -> as-is
      - 'bigquery-public-data.google_analytics_sample' -> 'bigquery-public-data'
      - 'google_analytics_sample' (dataset emitted in db slot)
        -> kept as-is; downstream still treats it as residency-ok
      - 'bq' or other phantom shortnames -> kept as-is (validator will
        reject; helper does not invent identifiers)
    """
    if not value:
        return ''
    parts = _split_fqn(value)
    if not parts:
        return ''
    if parts[0] in projects:
        return parts[0]
    if len(parts) >= 2 and parts[1] in datasets and parts[0] in projects:
        return parts[0]
    return value


def _canon_schema(value: str, datasets: set) -> str:
    if not value:
        return ''
    parts = _split_fqn(value)
    for p in reversed(parts):
        if p in datasets:
            return p
    return parts[-1] if parts else value


def _canon_one_table(value: str, tables: set, wildcard_bases: set) -> str:
    """Strip FQN prefix; collapse to wildcard form if a date-shard family exists."""
    if not value:
        return ''
    bare = _split_fqn(value)[-1] if '.' in value else value
    if bare.endswith('_*'):
        return bare
    if bare in tables:
        return bare
    m = _DATE_SHARD_RE.match(bare)
    if m and m.group('base') in wildcard_bases:
        # keep the bare shard name; the renderer/validator decide whether
        # to roll it up to the wildcard
        return bare
    return bare  # pass through; validator will flag if truly unknown


def canonicalize_identifier_slots(plan: dict, pack: dict) -> dict:
    """Return a *new* dict with canonicalised identifier slots.

    The returned dict has the same keys as `plan` plus an internal
    `_canon` block carrying the canonical forms separately. Callers
    that want full transparency can compare `_canon` to the original
    plan slots in error reports.
    """
    if not isinstance(plan, dict):
        return plan
    projects = _pack_known_projects(pack)
    datasets = _pack_known_datasets(pack)
    tables = _pack_known_tables(pack)
    wildcard_bases = _pack_wildcard_bases(pack)

    canon = dict(plan)
    sd_orig = plan.get('selected_database') or ''
    ss_orig = plan.get('selected_schema') or ''
    st_orig = list(plan.get('selected_tables') or [])

    sd = _canon_database(sd_orig, projects, datasets)
    # If the planner stuffed the dataset into the db slot, surface it
    # for the schema slot as a fallback.
    fallback_schema = ''
    parts_sd = _split_fqn(sd_orig)
    if len(parts_sd) >= 2 and parts_sd[-1] in datasets:
        fallback_schema = parts_sd[-1]
    ss = _canon_schema(ss_orig or fallback_schema, datasets)

    st_bare = [_canon_one_table(t, tables, wildcard_bases) for t in st_orig]

    # Wildcard collapse: if multiple shards share a base, advertise the
    # wildcard form ONCE in addition to the bare list. Both forms are
    # residency-valid; the renderer picks the wildcard.
    wildcard_form = None
    bases = set()
    for t in st_bare:
        m = _DATE_SHARD_RE.match(t)
        if m:
            bases.add(m.group('base'))
    if len(st_bare) > 1 and len(bases) == 1 and next(iter(bases)) in wildcard_bases:
        wildcard_form = next(iter(bases)) + '_*'

    canon['selected_database'] = sd
    canon['selected_schema'] = ss
    canon['selected_tables'] = list(st_bare)
    if wildcard_form:
        if wildcard_form not in canon['selected_tables']:
            canon['selected_tables'].append(wildcard_form)
    canon['_canon'] = {
        'database_orig': sd_orig, 'database': sd,
        'schema_orig': ss_orig, 'schema': ss,
        'tables_orig': st_orig, 'tables_bare': st_bare,
        'wildcard_form': wildcard_form,
        'projects_seen': sorted(projects)[:5],
        'datasets_seen': sorted(datasets)[:5],
    }
    return canon


def canonical_table_for_render(plan: dict, pack: dict) -> tuple:
    """Helper for the renderer: return (project, dataset, table_or_wildcard)
    given a plan + pack. Mirrors what the validator considers canonical."""
    canon = canonicalize_identifier_slots(plan, pack)
    sd = canon.get('selected_database', '')
    ss = canon.get('selected_schema', '')
    tables = canon.get('selected_tables') or []
    wf = canon.get('_canon', {}).get('wildcard_form')
    table = wf or (tables[0] if tables else '')
    return sd, ss, table
