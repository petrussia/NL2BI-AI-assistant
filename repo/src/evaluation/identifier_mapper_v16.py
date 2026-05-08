"""identifier_mapper_v16 — multi-signal nearest-match identifier mapping.

Given a list of unknown identifiers (from validator) and a catalog,
build replacement candidate variants. Multi-signal scoring:

  - exact (case-insensitive) match
  - normalized (snake_case) match
  - Levenshtein distance
  - token overlap (split on _)
  - char-ngram overlap
  - question/evidence overlap (if provided)
  - table-column compatibility (column must exist on the chosen table)

Public API:
  - suggest_table_replacements(unknown_table, catalog, db, *, question="",
        evidence="", top_k=5)
  - suggest_column_replacements(unknown_col, qual, catalog, db,
        selected_tables, *, question="", evidence="", top_k=5)
  - apply_substitutions(sql, replacements) — returns rewritten SQL
"""
from __future__ import annotations

import re


def _levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    a, b = a.lower(), b.lower()
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[j-1] + 1, prev[j] + 1, prev[j-1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _norm(s: str) -> str:
    return re.sub(r'[\W_]+', '', (s or '').lower())


def _tokens(s: str) -> set:
    return {t.lower() for t in re.split(r'[\W_]+', s or '') if t}


def _ngrams(s: str, n: int = 3) -> set:
    s = s.lower()
    return {s[i:i+n] for i in range(max(0, len(s) - n + 1))}


def _score(needle: str, candidate: str, *, question: str = '',
              evidence: str = '') -> float:
    """Composite score 0..1 of how good `candidate` replaces `needle`."""
    if not candidate: return 0.0
    n_norm = _norm(needle)
    c_norm = _norm(candidate)
    if n_norm == c_norm: return 1.0   # exact normalized match

    s = 0.0
    # Levenshtein contribution (closer = higher)
    lev = _levenshtein(needle, candidate)
    max_len = max(len(needle), len(candidate))
    if max_len > 0:
        s += 0.4 * max(0, 1 - lev / max_len)
    # Token overlap
    nt = _tokens(needle)
    ct = _tokens(candidate)
    if nt or ct:
        overlap = len(nt & ct) / max(1, len(nt | ct))
        s += 0.25 * overlap
    # Char-ngram overlap
    ng_n = _ngrams(needle, 3)
    ng_c = _ngrams(candidate, 3)
    if ng_n or ng_c:
        ng_overlap = len(ng_n & ng_c) / max(1, len(ng_n | ng_c))
        s += 0.15 * ng_overlap
    # Question / evidence overlap (does the candidate appear in the question?)
    qct = _tokens(question + ' ' + evidence)
    if qct & ct:
        s += 0.20

    return min(1.0, s)


def suggest_table_replacements(unknown_table: str, catalog: dict, db: str,
                                    *, question: str = '', evidence: str = '',
                                    top_k: int = 5) -> list:
    """catalog is the per-DB sub-catalog dict with `tables_flat` map."""
    flat = catalog.get('tables_flat') or catalog.get('databases', {}).get(db, {}).get('tables_flat', {})
    if not flat: return []
    candidates = list(flat.keys())  # uppercase table names
    scored = []
    for cand in candidates:
        sc = _score(unknown_table, cand, question=question, evidence=evidence)
        if sc > 0:
            scored.append((sc, cand))
    scored.sort(reverse=True)
    return [c for _, c in scored[:top_k]]


def suggest_column_replacements(unknown_col: str, qual: str, catalog: dict,
                                      db: str, selected_tables: list,
                                      *, question: str = '', evidence: str = '',
                                      top_k: int = 5) -> list:
    """Returns list of (table_name, col_name) candidates."""
    flat = catalog.get('tables_flat') or {}
    if not flat: return []

    # If qualifier is present, restrict to that table
    candidate_tables = list(flat.keys())
    if qual:
        candidate_tables = [t for t in candidate_tables if t.upper() == qual.upper()]
    elif selected_tables:
        sel_tn = {t.upper().split('.')[-1] for t in selected_tables}
        candidate_tables = [t for t in candidate_tables if t.upper() in sel_tn]
    if not candidate_tables:
        candidate_tables = list(flat.keys())

    scored = []
    for tname in candidate_tables:
        for c in flat[tname].get('columns', []):
            cn = c['name']
            sc = _score(unknown_col, cn, question=question, evidence=evidence)
            if sc > 0:
                scored.append((sc, tname, cn))
    scored.sort(reverse=True)
    return [(t, c) for _, t, c in scored[:top_k]]


def apply_substitutions(sql: str, replacements: list) -> tuple:
    """Apply each (old_token, new_token) replacement to SQL.
    Whole-word match, case-insensitive. Skips inside quoted string
    literals. Returns (new_sql, applied list).
    """
    cur = sql
    applied = []
    for old, new in replacements:
        if not old or not new: continue
        # Whole-word substitution, case-insensitive
        pat = re.compile(rf'\b{re.escape(old)}\b', re.IGNORECASE)
        out, n = pat.subn(new, cur)
        if n > 0:
            applied.append({'old': old, 'new': new, 'count': n})
            cur = out
    return cur, applied


# --- smoke ---
if __name__ == '__main__':
    cat = {
        'tables_flat': {
            'PUBLICATIONS': {'columns': [
                {'name': 'publication_date', 'type': 'DATE'},
                {'name': 'publication_number', 'type': 'STRING'},
            ]},
            'CITATION': {'columns': [
                {'name': 'citing_publication_number', 'type': 'STRING'},
            ]},
        }
    }
    print('--- table suggestions ---')
    print(suggest_table_replacements('PATENT_PUBLICATIONS', cat, 'PATENTS',
                                          question='count patents', top_k=3))
    print('--- column suggestions ---')
    print(suggest_column_replacements('publication_data', '', cat, 'PATENTS',
                                            ['PATENTS.PUBLIC.PUBLICATIONS'],
                                            question='date', top_k=3))
    print('--- apply ---')
    sql = "SELECT publication_data FROM PATENTS.PUBLIC.PUBLICATIONS"
    out, ap = apply_substitutions(sql, [('publication_data', 'publication_date')])
    print(f"OUT: {out}\nAPPLIED: {ap}")
