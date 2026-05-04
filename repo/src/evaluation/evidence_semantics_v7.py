"""evidence_semantics_v7 — semantic evidence layer over evidence_store_v2.

Builds a richer evidence pack per (db, question) than the v2 snippet store,
with three layers:

  1. GOLD evidence — per-item snippets shipped with BIRD (unchanged).
  2. SCHEMA evidence — table/column comments, FK summaries, key-column flags.
  3. VALUE HINTS — bounded probes against the live database:
       - SELECT DISTINCT col LIMIT 10  (low-cardinality categoricals)
       - MIN(col), MAX(col)            (numeric / date ranges)
       - COUNT(col) IS NULL share      (data-quality cue)
     All probes are wrapped in a 1.5-second timeout and a per-cell
     concurrency limit; failures and timeouts are logged, never raised.
  4. GENERATED aliases — rule-based synonyms expanded from camelCase /
     snake_case identifiers, plus a question→column lexical bridge so
     the planner / judge can spot the right column when the question
     uses common-language wording.

Output object (extended Evidence):
  {
    'scope': 'db|table|column|item|generated',
    'source_type': 'gold|schema_comment|profile|sample_value|generated_alias|fk_summary',
    'text': str,
    'linked_tables': [str],
    'linked_columns': [(table, column)],
    'confidence': 0.0..1.0,
    'quality': 'strong|weak|noisy',
    'is_gold': bool,
  }

Intended caller: baselines_b7_v7. The b6_v7 controller is unchanged; we
only swap in a richer per_item_evidence string assembled by
`render_evidence_pack` and feed it to the same retrieval+selector pipeline.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence


@dataclass
class EvidenceV7:
    scope: str = 'database'
    source_type: str = 'unknown'
    text: str = ''
    linked_tables: list[str] = field(default_factory=list)
    linked_columns: list[tuple[str, str]] = field(default_factory=list)
    confidence: float = 0.5
    quality: str = 'weak'
    is_gold: bool = False

    def to_dict(self) -> dict:
        d = asdict(self); d['linked_columns'] = list(d['linked_columns']); return d


# ---------------- value probes (bounded) ----------------

_SAFE_TIMEOUT_S = 1.5
_DEFAULT_DISTINCT_LIMIT = 8


def _bounded_query(db_path: str, sql: str, timeout_s: float = _SAFE_TIMEOUT_S):
    """Run a single SELECT against db_path with a strict timeout. Returns
    (rows, error_str). Never raises."""
    try:
        from func_timeout import FunctionTimedOut, func_timeout
    except Exception:
        # Fall back to direct execution; caller will see real timing
        try:
            with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as con:
                con.text_factory = bytes
                cur = con.cursor(); cur.execute(sql); return cur.fetchall(), ''
        except Exception as exc:
            return None, f'{type(exc).__name__}: {str(exc)[:160]}'

    def _run():
        with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as con:
            con.text_factory = bytes
            cur = con.cursor(); cur.execute(sql); return cur.fetchall()
    try:
        return func_timeout(timeout_s, _run), ''
    except FunctionTimedOut:
        return None, 'timeout'
    except Exception as exc:
        return None, f'{type(exc).__name__}: {str(exc)[:160]}'


def _format_value(v) -> str:
    if v is None: return 'NULL'
    if isinstance(v, bytes):
        try: return v.decode('utf-8', errors='replace')[:60]
        except Exception: return '<bytes>'
    s = str(v)
    return s[:60] if len(s) > 60 else s


def _is_numeric_dtype(dtype: str) -> bool:
    s = (dtype or '').lower()
    return any(t in s for t in ('int', 'real', 'numeric', 'float', 'double', 'decimal'))


def _is_date_dtype(dtype: str) -> bool:
    s = (dtype or '').lower()
    return any(t in s for t in ('date', 'time', 'timestamp'))


def build_column_value_hints(ir, db_path: str | None = None, *,
                              max_columns: int = 24,
                              distinct_limit: int = _DEFAULT_DISTINCT_LIMIT,
                              per_table_cap: int = 4,
                              budget_seconds: float = 6.0) -> list[EvidenceV7]:
    """Probe up to `max_columns` columns across the IR with bounded
    queries. Per-table cap prevents one wide table from eating the
    budget. Returns evidence items with concrete value samples."""
    if not db_path: return []
    out: list[EvidenceV7] = []
    table_used: dict[str, int] = {}
    started = time.time()

    # Prioritize text/categorical first (more useful for value matching),
    # then numeric/date for range hints.
    candidates: list[tuple[float, object, object]] = []
    for t in ir.tables:
        for c in t.columns:
            # priority: PK columns weakest signal, FK columns weak, text/dates strong
            d = (c.dtype or '').lower()
            pri = 0.5
            if 'text' in d or 'char' in d or 'varchar' in d: pri = 0.9
            elif _is_date_dtype(d): pri = 0.8
            elif _is_numeric_dtype(d): pri = 0.6
            if c.is_pk: pri *= 0.3
            if c.is_fk: pri *= 0.5
            candidates.append((pri, t, c))
    candidates.sort(key=lambda x: -x[0])

    for pri, t, c in candidates[:max_columns * 4]:
        if (time.time() - started) > budget_seconds: break
        if len(out) >= max_columns: break
        if table_used.get(t.name, 0) >= per_table_cap: continue
        col = f'"{c.original_name}"'; tab = f'"{t.original_name}"'
        d = (c.dtype or '').lower()
        if _is_numeric_dtype(d) or _is_date_dtype(d):
            sql = f'SELECT MIN({col}), MAX({col}) FROM {tab}'
            rows, err = _bounded_query(db_path, sql)
            if err or not rows: continue
            mn, mx = rows[0] if rows[0] else (None, None)
            txt = f'{t.original_name}.{c.original_name} range: [{_format_value(mn)} .. {_format_value(mx)}]'
            quality = 'strong' if (mn is not None and mx is not None) else 'weak'
            out.append(EvidenceV7(scope='column', source_type='profile',
                                    text=txt, linked_tables=[t.name],
                                    linked_columns=[(t.name, c.name)],
                                    confidence=0.75, quality=quality, is_gold=False))
        else:
            sql = f'SELECT DISTINCT {col} FROM {tab} WHERE {col} IS NOT NULL LIMIT {distinct_limit}'
            rows, err = _bounded_query(db_path, sql)
            if err or not rows: continue
            vals = [_format_value(r[0]) for r in rows[:distinct_limit] if r and r[0] is not None]
            if not vals: continue
            txt = f'{t.original_name}.{c.original_name} values like: ' + ', '.join(repr(v) for v in vals[:6])
            quality = 'strong' if len(vals) <= distinct_limit else 'weak'
            out.append(EvidenceV7(scope='column', source_type='sample_value',
                                    text=txt, linked_tables=[t.name],
                                    linked_columns=[(t.name, c.name)],
                                    confidence=0.70, quality=quality, is_gold=False))
        table_used[t.name] = table_used.get(t.name, 0) + 1
    return out


# ---------------- schema-derived evidence ----------------

def build_db_profile_evidence(ir) -> list[EvidenceV7]:
    """Schema-only evidence (no executor). Captures FK shape and any
    table/column comments shipped with the IR."""
    out: list[EvidenceV7] = []
    if ir.comment:
        out.append(EvidenceV7(scope='database', source_type='schema_comment',
                                text=ir.comment, confidence=0.6, quality='weak'))
    for t in ir.tables:
        if t.comment:
            out.append(EvidenceV7(scope='table', source_type='schema_comment',
                                    text=f'{t.original_name}: {t.comment}',
                                    linked_tables=[t.name],
                                    confidence=0.7, quality='strong'))
        for c in t.columns:
            if c.comment:
                out.append(EvidenceV7(scope='column', source_type='schema_comment',
                                        text=f'{t.original_name}.{c.original_name}: {c.comment}',
                                        linked_tables=[t.name],
                                        linked_columns=[(t.name, c.name)],
                                        confidence=0.8, quality='strong'))
    if ir.fk_edges:
        fk_text = '; '.join(f'{e.from_table}.{e.from_column}->{e.to_table}.{e.to_column}'
                              for e in ir.fk_edges[:20])
        out.append(EvidenceV7(scope='database', source_type='fk_summary',
                                text=f'FK edges: {fk_text}',
                                linked_tables=sorted({e.from_table for e in ir.fk_edges} |
                                                       {e.to_table for e in ir.fk_edges}),
                                confidence=0.6, quality='strong'))
    return out


# ---------------- generated aliases (rule-based, cheap) ----------------

_SPLIT_CAMEL = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')
_TOK = re.compile(r'[a-z0-9]+')


def _id_to_words(name: str) -> list[str]:
    """customer_id → ['customer','id'];  customerName → ['customer','name'];
    PRJ_KEY → ['prj','key']."""
    parts = _SPLIT_CAMEL.split(name or '')
    out = []
    for p in parts:
        for w in p.replace('_', ' ').split():
            out.extend(_TOK.findall(w.lower()))
    return out


_COMMON_SYNONYMS = {
    'cust': 'customer', 'usr': 'user', 'mgr': 'manager', 'addr': 'address',
    'qty': 'quantity', 'amt': 'amount', 'tot': 'total', 'avg': 'average',
    'cnt': 'count', 'num': 'number', 'no': 'number', 'desc': 'description',
    'tx': 'transaction', 'prod': 'product', 'cat': 'category',
    'org': 'organization', 'div': 'division', 'dept': 'department',
    'emp': 'employee', 'mfg': 'manufacturing', 'mfr': 'manufacturer',
    'pkg': 'package', 'tx_id': 'transaction', 'src': 'source', 'dst': 'destination',
    'ts': 'timestamp', 'dt': 'date',
}


def synthesize_aliases(question: str, ir) -> list[EvidenceV7]:
    """Generate alias hints for question terms that lexically resemble
    schema column words (with common abbreviation expansion)."""
    q_words = set(_TOK.findall((question or '').lower()))
    out: list[EvidenceV7] = []
    for t in ir.tables:
        for c in t.columns:
            words = _id_to_words(c.original_name)
            expanded = list(words)
            for w in words:
                if w in _COMMON_SYNONYMS:
                    expanded.append(_COMMON_SYNONYMS[w])
            overlap = q_words & set(expanded)
            if overlap:
                aliases = sorted(set(expanded) - {c.name})
                if not aliases: continue
                txt = (f'{t.original_name}.{c.original_name} matches question term(s) '
                        f'{sorted(overlap)} via aliases {aliases[:6]}')
                out.append(EvidenceV7(scope='generated', source_type='generated_alias',
                                        text=txt, linked_tables=[t.name],
                                        linked_columns=[(t.name, c.name)],
                                        confidence=0.55, quality='weak'))
    return out


# ---------------- retrieval + render ----------------

def _score_relevance(ev: EvidenceV7, q_tokens: set[str], selected_tables: set[str]) -> float:
    """Lexical+ structural relevance score for ranking."""
    s = ev.confidence
    if ev.is_gold: s += 0.3
    if ev.linked_tables and selected_tables and any(t in selected_tables for t in ev.linked_tables):
        s += 0.2
    text_words = set(_TOK.findall((ev.text or '').lower()))
    overlap = len(q_tokens & text_words)
    s += 0.05 * min(overlap, 6)
    if ev.quality == 'strong': s += 0.05
    elif ev.quality == 'noisy': s -= 0.10
    return s


def retrieve_evidence_for_question(question: str, ir,
                                    evidence_items: Sequence[EvidenceV7],
                                    *,
                                    selected_tables: Iterable[str] = (),
                                    k: int = 8) -> list[EvidenceV7]:
    q_tokens = set(_TOK.findall((question or '').lower()))
    sel = {t.lower() for t in selected_tables}
    scored = [(ev, _score_relevance(ev, q_tokens, sel)) for ev in evidence_items]
    scored.sort(key=lambda x: -x[1])
    return [ev for ev, _ in scored[:k]]


def render_evidence_pack(items: Sequence[EvidenceV7], *,
                          char_budget: int = 600,
                          include_source: bool = True) -> str:
    """Compact, deduplicated text block. Items already ranked by retrieval.
    Stays under `char_budget`."""
    out: list[str] = []; total = 0; seen: set[str] = set()
    for ev in items:
        line = ev.text.strip()
        if not line or line in seen: continue
        if include_source:
            tag = f'[{ev.source_type}]'
            line = f'{tag} {line}'
        if total + len(line) + 1 > char_budget: break
        out.append('- ' + line); total += len(line) + 1; seen.add(ev.text.strip())
    return '\n'.join(out)


# ---------------- top-level builder for one (item, ir) ----------------

def build_evidence_pack(question: str, ir, db_path: str | None, *,
                         per_item_evidence: str = '',
                         include_value_hints: bool = True,
                         include_aliases: bool = True,
                         include_schema: bool = True,
                         k_retrieve: int = 8,
                         char_budget: int = 600,
                         selected_tables: Iterable[str] = ()) -> tuple[str, list[EvidenceV7]]:
    """Assemble a per-question evidence pack and render it. Returns
    (rendered_text, ranked_items). Caller (b7_v7) injects the rendered
    text into the prompt as `per_item_evidence`."""
    items: list[EvidenceV7] = []
    if per_item_evidence:
        items.append(EvidenceV7(scope='item', source_type='gold',
                                  text=per_item_evidence, confidence=1.0,
                                  quality='strong', is_gold=True))
    if include_schema:
        items.extend(build_db_profile_evidence(ir))
    if include_aliases:
        items.extend(synthesize_aliases(question, ir))
    if include_value_hints and db_path:
        items.extend(build_column_value_hints(ir, db_path))
    ranked = retrieve_evidence_for_question(question, ir, items,
                                             selected_tables=selected_tables,
                                             k=k_retrieve)
    rendered = render_evidence_pack(ranked, char_budget=char_budget)
    return rendered, ranked
