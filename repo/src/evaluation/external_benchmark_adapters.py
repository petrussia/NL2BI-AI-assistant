"""External benchmark adapters: BIRD Mini-Dev (executable) + Spider 2.0-Lite (prediction-only).

BIRD provides SQLite databases — full EX evaluation is supported.
Spider 2.0-Lite ships DDL + sample-row JSON, no real SQLite engine instance and
no public gold SQL inside the lite tasks file (gold lives in evaluation_suite).
For Spider 2.0-Lite we therefore compute structural metrics only.

Public API:
- bird_load(slice_path) -> list[dict]
- bird_full_schema(db_id, tables_meta) -> str
- bird_db_path(db_id) -> Path
- spider2_load(slice_path) -> list[dict]
- spider2_full_schema_proxy(db, root_resource) -> str
"""
from __future__ import annotations
import csv
import json
import sqlite3
from pathlib import Path

# Drive locations
BIRD_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/bird_mini_dev/raw/minidev/minidev/MINIDEV')
SPIDER2_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/resource/databases/sqlite')


# ============================================================
# BIRD Mini-Dev
# ============================================================
def bird_load(slice_path: str | Path) -> list[dict]:
    """Load a processed BIRD slice (list of dicts with idx, db_id, question, gold_sql)."""
    return json.loads(Path(slice_path).read_text(encoding='utf-8'))


def bird_db_path(db_id: str) -> Path:
    """Path to the SQLite database file for a BIRD example."""
    return BIRD_ROOT / 'dev_databases' / db_id / f'{db_id}.sqlite'


def _bird_tables_meta() -> dict:
    """dev_tables.json maps db_id -> {table_names_original, column_names_original, ...} like Spider tables.json."""
    meta = json.loads((BIRD_ROOT / 'dev_tables.json').read_text(encoding='utf-8'))
    return {row['db_id']: row for row in meta}


_BIRD_TM_CACHE: dict | None = None


def bird_full_schema(db_id: str) -> str:
    """Full schema text in the same format as our internal Spider builders."""
    global _BIRD_TM_CACHE
    if _BIRD_TM_CACHE is None:
        _BIRD_TM_CACHE = _bird_tables_meta()
    t = _BIRD_TM_CACHE.get(db_id)
    if not t:
        return f'Database: {db_id} (schema metadata not found)'
    tn = t.get('table_names_original') or t.get('table_names') or []
    cn = t.get('column_names_original') or t.get('column_names') or []
    by_table: dict = {i: [] for i in range(len(tn))}
    for ti, col in cn:
        if ti >= 0:
            by_table.setdefault(ti, []).append(col)
    lines = [f'Database: {db_id}', 'Tables and columns:']
    for idx, name in enumerate(tn):
        lines.append(f'- {name}(' + ', '.join(by_table.get(idx, [])) + ')')
    return '\n'.join(lines)


def bird_lex_link(question: str, db_id: str, min_score: float = 0.5) -> dict:
    """Simple lexical schema linker (same as internal Spider one)."""
    import re
    STOP = {'a','an','the','of','in','on','at','for','to','from','by','with',
            'is','are','was','were','what','which','who','whom','whose','how',
            'many','much','show','list','find','give','me','all','each','every',
            'any','do','does','did'}
    def _toks(s):
        parts = re.split(r'[\s_]+', str(s).lower())
        return {p for p in parts if p and p not in STOP and len(p) > 1}
    global _BIRD_TM_CACHE
    if _BIRD_TM_CACHE is None:
        _BIRD_TM_CACHE = _bird_tables_meta()
    t = _BIRD_TM_CACHE[db_id]
    tn = t.get('table_names_original') or t.get('table_names') or []
    cn = t.get('column_names_original') or t.get('column_names') or []
    qt = _toks(question)
    scores = {i: 0.0 for i in range(len(tn))}
    for i, name in enumerate(tn):
        scores[i] += len(qt & _toks(name)) * 2.0
    for ti, col in cn:
        if ti >= 0:
            scores[ti] += len(qt & _toks(col)) * 1.0
    above = [(i, s) for i, s in scores.items() if s >= min_score]
    above.sort(key=lambda x: -x[1])
    if not above:
        selected = list(range(len(tn))); fallback = True
    else:
        selected = sorted([i for i, _ in above]); fallback = False
    return {'selected_table_indexes': selected,
            'selected_tables': [tn[i] for i in selected],
            'reduction_ratio': len(selected) / len(tn) if tn else 1.0,
            'fallback_used': fallback}


def bird_reduced_schema(db_id: str, selected_idx: list) -> str:
    global _BIRD_TM_CACHE
    if _BIRD_TM_CACHE is None:
        _BIRD_TM_CACHE = _bird_tables_meta()
    t = _BIRD_TM_CACHE[db_id]
    tn = t.get('table_names_original') or t.get('table_names') or []
    cn = t.get('column_names_original') or t.get('column_names') or []
    by_table: dict = {i: [] for i in range(len(tn))}
    for ti, col in cn:
        if ti >= 0:
            by_table.setdefault(ti, []).append(col)
    lines = [f'Database: {db_id}',
             'Tables and columns (reduced via lexical schema linking):']
    for idx in selected_idx:
        lines.append(f'- {tn[idx]}(' + ', '.join(by_table.get(idx, [])) + ')')
    return '\n'.join(lines)


# ============================================================
# Spider 2.0-Lite (prediction-only)
# ============================================================
def spider2_load(slice_path: str | Path) -> list[dict]:
    """Load processed Spider2-Lite slice."""
    return json.loads(Path(slice_path).read_text(encoding='utf-8'))


def _read_ddl_csv(p: Path) -> list[tuple[str, str]]:
    """Returns list of (table_name, column_name) from a Spider2-Lite DDL.csv."""
    rows = []
    if not p.exists(): return rows
    try:
        with p.open(encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                t = row.get('table_name') or row.get('Table') or ''
                c = row.get('column_name') or row.get('Column') or ''
                if t and c:
                    rows.append((t, c))
    except Exception:
        pass
    return rows


def spider2_full_schema_proxy(db: str) -> str:
    """Build a schema description proxy from Spider2-Lite resource files.

    We use the SQLite-style sample directories under resource/databases/sqlite/<DB>/
    when available; otherwise fall back to a stub. Real BigQuery/Snowflake DDLs
    live in resource/databases/{bigquery,snowflake}/<DB>/DDL.csv but we keep the
    prompt small for prediction-only evaluation.
    """
    candidates = [SPIDER2_ROOT / db, SPIDER2_ROOT / db.lower()]
    # Try each known top dir (BigQuery/Snowflake/SQLite)
    for top_kind in ('sqlite', 'bigquery', 'snowflake'):
        cand_root = SPIDER2_ROOT.parent / top_kind / db
        if cand_root.exists():
            candidates.append(cand_root)
    by_table: dict[str, list[str]] = {}
    db_dir = None
    for c in candidates:
        if c.exists() and c.is_dir():
            db_dir = c; break
    if db_dir is None:
        return f'Database: {db}\n(Schema metadata not found in resource/.)'
    # Each subdir or file is a table; DDL.csv enumerates schema
    for ddl in db_dir.rglob('DDL.csv'):
        for tname, cname in _read_ddl_csv(ddl):
            by_table.setdefault(tname, []).append(cname)
    # JSON sample files: filename without ext is a table, fields inside are columns
    for jf in db_dir.glob('*.json'):
        try:
            data = json.loads(jf.read_text(encoding='utf-8'))
            tname = jf.stem
            if isinstance(data, list) and data and isinstance(data[0], dict):
                cols = list(data[0].keys())
            elif isinstance(data, dict) and 'columns' in data:
                cols = data['columns']
            else:
                cols = []
            if tname not in by_table:
                by_table[tname] = list(dict.fromkeys((by_table.get(tname, []) + cols)))
        except Exception:
            pass
    if not by_table:
        return f'Database: {db}\n(No DDL/sample data found in resource/.)'
    lines = [f'Database: {db}', 'Tables and columns:']
    for tname in sorted(by_table):
        cols = by_table[tname]
        lines.append(f'- {tname}(' + ', '.join(cols[:30]) + (')' if len(cols) <= 30 else ', ...)'))
    return '\n'.join(lines)


def spider2_lex_link_proxy(question: str, db: str, min_score: float = 0.5) -> dict:
    """Lex linker over Spider2 schema proxy. Returns same shape as Spider's."""
    import re
    STOP = {'a','an','the','of','in','on','at','for','to','from','by','with',
            'is','are','was','were','what','which','who','whom','whose','how',
            'many','much','show','list','find','give','me','all','each','every',
            'any','do','does','did'}
    def _toks(s):
        parts = re.split(r'[\s_]+', str(s).lower())
        return {p for p in parts if p and p not in STOP and len(p) > 1}
    schema = spider2_full_schema_proxy(db)
    # parse table list from the schema text we just built
    tables = []
    for ln in schema.splitlines():
        if ln.startswith('- '):
            name = ln.split('(', 1)[0][2:].strip()
            tables.append(name)
    qt = _toks(question)
    selected = [i for i, t in enumerate(tables) if (qt & _toks(t))]
    if not selected:
        selected = list(range(len(tables))); fallback = True
    else:
        fallback = False
    return {'selected_table_indexes': selected,
            'selected_tables': [tables[i] for i in selected],
            'reduction_ratio': len(selected) / len(tables) if tables else 1.0,
            'fallback_used': fallback,
            'all_tables': tables}


# ============================================================
# Structural metrics (work for any benchmark, executable or not)
# ============================================================
import re

_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|create|alter|truncate|replace|pragma|attach|detach|grant|revoke)\b',
    re.IGNORECASE)


def structural_features(sql: str) -> dict:
    s = (sql or '').strip()
    return {
        'len_chars': len(s),
        'len_tokens_est': len(s.split()),
        'starts_with_select': bool(re.match(r'^\s*(?:with\b.*?\bselect\b|select\b)', s, re.I | re.S)),
        'has_join': bool(re.search(r'\bjoin\b', s, re.I)),
        'has_groupby': bool(re.search(r'\bgroup\s+by\b', s, re.I)),
        'has_orderby': bool(re.search(r'\border\s+by\b', s, re.I)),
        'has_limit': bool(re.search(r'\blimit\b', s, re.I)),
        'has_subquery': s.count('(SELECT') + s.count('(select'),
        'safe_select': bool(re.match(r'^\s*(?:with\b.*?\bselect\b|select\b)', s, re.I | re.S))
                        and not _FORBIDDEN.search(s),
    }


def aggregate_structural(records: list[dict]) -> dict:
    if not records: return {}
    feats = [r.get('structural', {}) for r in records]
    n = len(feats)
    return {
        'avg_len_chars': sum(f.get('len_chars', 0) for f in feats) / n,
        'avg_len_tokens_est': sum(f.get('len_tokens_est', 0) for f in feats) / n,
        'pct_starts_with_select': 100 * sum(1 for f in feats if f.get('starts_with_select')) / n,
        'pct_has_join': 100 * sum(1 for f in feats if f.get('has_join')) / n,
        'pct_has_groupby': 100 * sum(1 for f in feats if f.get('has_groupby')) / n,
        'pct_has_orderby': 100 * sum(1 for f in feats if f.get('has_orderby')) / n,
        'pct_has_limit': 100 * sum(1 for f in feats if f.get('has_limit')) / n,
        'pct_safe_select': 100 * sum(1 for f in feats if f.get('safe_select')) / n,
    }
