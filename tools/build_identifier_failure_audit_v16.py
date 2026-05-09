"""build_identifier_failure_audit_v16.py — root-cause audit across all pilots.

Reads predictions.jsonl + candidates.jsonl + traces.jsonl from every
historical pilot run and produces a per-task row classifying the
failure mode. Output: outputs/tables/spider2_identifier_failure_audit_v16.csv

Categories the auditor recognizes (by inspecting error_message,
unknown_tables, unknown_columns text + the SQL itself):

- is_close_typo: unknown identifier within Levenshtein <= 2 of a catalog entry
- is_alias_issue: unknown column whose qualifier matches an alias in FROM
- is_struct_array_issue: BQ event_params.key, value.int_value, hits.product etc.
- is_wildcard_issue: unknown table that's a `*` wildcard pattern
- is_project_qualification_issue: 4-part with repeated project segment
- is_catalog_render_missing: identifier IS in catalog but NOT in selected_tables
  (so retrieval missed it, not the model)
- is_true_hallucination: nothing structural; pure invention
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def _levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    a, b = a.lower(), b.lower()
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[j-1] + 1, prev[j] + 1,
                              prev[j-1] + (ca != cb)))
        prev = cur
    return prev[-1]


# Hardcoded GA4 / GA360 nested column patterns
_GA4_NESTED = {'event_params', 'user_properties', 'items', 'device',
                  'geo', 'traffic_source', 'ecommerce', 'user_ltv'}
_GA360_NESTED = {'hits', 'totals', 'trafficsource', 'device',
                    'geonetwork', 'customdimensions', 'customvariables'}
_NESTED_LEAF_TOKENS = {'value', 'int_value', 'string_value', 'float_value',
                            'double_value', 'key', 'product',
                            'v2productname', 'v2productcategory'}


def _classify_unknown_column(col: str, qual: str, ctx_tables: list,
                                  selected_tables: list, sql: str) -> dict:
    """Decide which class this unknown column falls into."""
    cu = (col or '').upper()
    qu = (qual or '').upper()
    out = {'is_close_typo': False, 'is_alias_issue': False,
            'is_struct_array_issue': False,
            'is_catalog_render_missing': False,
            'is_true_hallucination': False}

    # Struct/array issue: qualifier looks like a known nested column
    if qu.lower() in _GA4_NESTED or qu.lower() in _GA360_NESTED:
        out['is_struct_array_issue'] = True
        return out
    if cu.lower() in _NESTED_LEAF_TOKENS:
        out['is_struct_array_issue'] = True
        return out

    # Alias issue: qualifier appears as alias in FROM / JOIN
    if qu and re.search(rf'\bAS\s+{re.escape(qu)}\b', sql, re.IGNORECASE):
        out['is_alias_issue'] = True
        return out

    # Catalog-render-missing: column exists in some catalog table
    # but selected_tables doesn't include that table
    pool_in_selected = []
    pool_other = []
    for t in (ctx_tables or []):
        for c in t.get('columns', []):
            cn = c.get('name', '').upper()
            in_sel = any(s.endswith(t.get('table', '').upper())
                            for s in selected_tables)
            if cn == cu:
                (pool_in_selected if in_sel else pool_other).append(t.get('table'))
    if pool_other and not pool_in_selected:
        out['is_catalog_render_missing'] = True
        return out

    # Close typo: edit distance <= 2 to any catalog column
    candidates = set()
    for t in (ctx_tables or []):
        for c in t.get('columns', []):
            candidates.add(c.get('name', ''))
    for cand in candidates:
        if cand and _levenshtein(cu, cand.upper()) <= 2:
            out['is_close_typo'] = True
            return out

    out['is_true_hallucination'] = True
    return out


def _classify_unknown_table(tbl: str, sql: str) -> dict:
    out = {'is_wildcard_issue': False,
            'is_project_qualification_issue': False,
            'is_close_typo': False, 'is_true_hallucination': False}
    tu = (tbl or '').upper()
    if '*' in tu:
        out['is_wildcard_issue'] = True
        return out
    # Project doubled: pattern A.A.B.C in SQL
    if re.search(r'`([\w-]+)\.\1\.', sql):
        out['is_project_qualification_issue'] = True
        return out
    # Could not separate close-typo vs hallucination at this layer
    return out


def parse_validation_msg(msg: str) -> dict:
    """Extract unknown_tables and unknown_columns lists from the
    error_message string formatted like:
        UNKNOWN_TABLES (...):
          - X  suggestions=[...]
        UNKNOWN_COLUMNS (...):
          - Y (qual=Z)  suggestions=[...]
    """
    out = {'unknown_tables': [], 'unknown_columns': []}
    if not msg: return out
    section = None
    for line in msg.splitlines():
        s = line.strip()
        if not s: continue
        if s.startswith('UNKNOWN_TABLES'):
            section = 'tables'; continue
        if s.startswith('UNKNOWN_COLUMNS'):
            section = 'columns'; continue
        if not s.startswith('-'): continue
        body = s.lstrip('- ').strip()
        if section == 'tables':
            m = re.match(r'`?(\S+?)`?\s*(?:\(.*?\))?\s*suggestions=\[(.*)\]', body)
            if m:
                tbl = m.group(1).strip()
                sug = [x.strip().strip("'\"") for x in m.group(2).split(',') if x.strip()]
                out['unknown_tables'].append({'table': tbl, 'suggestions': sug})
        elif section == 'columns':
            m = re.match(r'`?(\S+?)`?\s*\(qual=(\S*?)\)\s*suggestions=\[(.*)\]', body)
            if m:
                col = m.group(1)
                qual = m.group(2).strip('-')
                sug = [x.strip().strip("'\"") for x in m.group(3).split(',') if x.strip()]
                out['unknown_columns'].append({'col': col, 'qual': qual,
                                                    'suggestions': sug})
    return out


def main() -> int:
    out_csv = REPO / 'outputs' / 'tables' / 'spider2_identifier_failure_audit_v16.csv'
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    counts = Counter()

    pilot_dirs = []
    for runs_root, lane in (
        (REPO / 'outputs' / 'spider2_lite' / 'runs', 'A_bq_or_sf'),
        (REPO / 'outputs' / 'spider2_snow' / 'runs', 'A_sf'),
    ):
        if not runs_root.exists(): continue
        for d in sorted(runs_root.iterdir()):
            if not d.is_dir(): continue
            pred = d / 'predictions.jsonl'
            if pred.exists():
                pilot_dirs.append((d.name, lane, d))

    print(f'pilots found: {len(pilot_dirs)}')

    for run_id, lane_hint, d in pilot_dirs:
        pred_path = d / 'predictions.jsonl'
        # Determine actual lane from run_id stem
        if 'sqlite' in run_id.lower(): lane = 'C_sqlite_stub'
        elif 'bq' in run_id.lower(): lane = 'A_bq'
        else: lane = 'A_sf'

        for ln in pred_path.open(encoding='utf-8'):
            if not ln.strip(): continue
            try:
                p = json.loads(ln)
            except Exception:
                continue
            if p.get('mode', '').startswith('blocked'): continue

            iid = p.get('instance_id', '')
            db = p.get('db', '')
            sql = p.get('sql', '') or p.get('original_sql', '')
            err_type = p.get('error_type', '')
            err_msg = p.get('error_message', '')

            parsed = parse_validation_msg(err_msg)
            ut_classes = []
            for ent in parsed['unknown_tables']:
                cls = _classify_unknown_table(ent['table'], sql)
                ut_classes.append(cls)
            uc_classes = []
            for ent in parsed['unknown_columns']:
                cls = _classify_unknown_column(ent['col'], ent['qual'],
                                                    [], p.get('selected_tables') or [],
                                                    sql)
                uc_classes.append(cls)

            # Aggregate per-row
            agg = {
                'is_close_typo': any(c.get('is_close_typo') for c in (ut_classes + uc_classes)),
                'is_alias_issue': any(c.get('is_alias_issue') for c in uc_classes),
                'is_struct_array_issue': any(c.get('is_struct_array_issue') for c in uc_classes),
                'is_wildcard_issue': any(c.get('is_wildcard_issue') for c in ut_classes),
                'is_project_qualification_issue': any(c.get('is_project_qualification_issue') for c in ut_classes),
                'is_catalog_render_missing': any(c.get('is_catalog_render_missing') for c in uc_classes),
                'is_true_hallucination': (not any(c for c in (ut_classes + uc_classes)) or
                                              any(c.get('is_true_hallucination') for c in (ut_classes + uc_classes))),
            }

            recommended = 'none'
            if agg['is_struct_array_issue']:
                recommended = 'bq_nested_rewrite'
            elif agg['is_wildcard_issue']:
                recommended = 'wildcard_validator_fix'
            elif agg['is_project_qualification_issue']:
                recommended = '4part_collapse_normalizer'
            elif agg['is_close_typo']:
                recommended = 'identifier_substitution'
            elif agg['is_catalog_render_missing']:
                recommended = 'expand_retrieval_topk'
            elif agg['is_alias_issue']:
                recommended = 'alias_aware_validator'

            row = {
                'lane': lane,
                'run_id': run_id,
                'instance_id': iid,
                'db_id': db,
                'error_type': err_type,
                'unknown_tables_n': len(parsed['unknown_tables']),
                'unknown_columns_n': len(parsed['unknown_columns']),
                'first_unknown_table': (parsed['unknown_tables'][0]['table']
                                              if parsed['unknown_tables'] else ''),
                'first_unknown_column': (parsed['unknown_columns'][0]['col']
                                                if parsed['unknown_columns'] else ''),
                'first_suggestion': (
                    ((parsed['unknown_columns'][0]['suggestions'][:1]
                         if parsed['unknown_columns'] else []) +
                       (parsed['unknown_tables'][0]['suggestions'][:1]
                          if parsed['unknown_tables'] else []))
                    or ['']
                )[0] if (parsed['unknown_columns'] or parsed['unknown_tables']) else '',
                'is_close_typo': agg['is_close_typo'],
                'is_alias_issue': agg['is_alias_issue'],
                'is_struct_array_issue': agg['is_struct_array_issue'],
                'is_wildcard_issue': agg['is_wildcard_issue'],
                'is_project_qualification_issue': agg['is_project_qualification_issue'],
                'is_catalog_render_missing': agg['is_catalog_render_missing'],
                'is_true_hallucination': agg['is_true_hallucination'],
                'recommended_repair_type': recommended,
                'parses': p.get('parses'),
                'executable': p.get('executable'),
                'schema_valid': p.get('schema_valid'),
            }
            rows.append(row)

            for k, v in agg.items():
                if v: counts[k] += 1
            counts[f'reco:{recommended}'] += 1

    if rows:
        with out_csv.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows: w.writerow(r)
    print(f'WROTE {out_csv} rows={len(rows)}')

    print('\n=== ROOT CAUSE COUNTS ===')
    for k, v in counts.most_common():
        print(f'  {k}: {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
