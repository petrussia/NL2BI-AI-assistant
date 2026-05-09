"""spider2_bq_retrieval_v8 — question -> relevant tables/columns/docs.

Three retrievers in one module:
  1. table_retriever:  question token overlap with table identifiers,
     column identifiers, sample values, descriptions. Stem-aware.
  2. doc_retriever:     external_knowledge file + resource/documents
     chunked by markdown headings, retrieved by token overlap.
  3. join_hint_retriever: name-based foreign-key heuristic; emits hints
     like "tableA.user_id <-> tableB.user_id (likely join on user_id)".

The retrieval is fully deterministic, no LLM calls.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from spider2_tools_v7 import _split_identifier, _stem, _question_terms
from spider2_bq_schema_index_v8 import BqSchemaIndex, BqTable


@dataclass
class TableHit:
    fq_name: str
    family_canonical: str
    score: float
    why: str  # human-readable reason


@dataclass
class ColumnHit:
    fq_name: str
    column_name: str
    dtype: str
    score: float
    sample_values: list[str] = field(default_factory=list)


@dataclass
class DocChunk:
    source: str  # filename
    title: str
    text: str
    score: float = 0.0


def _stemmed_set(s: str) -> set[str]:
    return {_stem(t) for t in _split_identifier(s)}


def retrieve_tables(idx: BqSchemaIndex, question: str, *,
                      k: int = 8) -> list[TableHit]:
    """Rank tables by token overlap of question with table+column tokens."""
    qt = {_stem(t) for t in _question_terms(question)}
    if not qt: return []
    hits: list[TableHit] = []
    seen_fams: set[str] = set()
    for t in idx.tables:
        if t.family_canonical:
            if t.family_canonical in seen_fams: continue
            seen_fams.add(t.family_canonical)
        ttoks = _stemmed_set(t.table_name) | _stemmed_set(t.dataset)
        for c in t.columns:
            ttoks |= _stemmed_set(c.name)
            if c.description: ttoks |= _stemmed_set(c.description)
        s_table = len(qt & ttoks) * 2.0
        # Bonus for rare exact matches in column names
        for c in t.columns:
            if c.name.lower() in qt: s_table += 1.0
        if t.description:
            dt = _stemmed_set(t.description)
            s_table += 0.5 * len(qt & dt)
        if s_table <= 0: continue
        why = f'token_overlap=({len(qt & ttoks)}) cols={len(t.columns)}'
        hits.append(TableHit(fq_name=t.fq_name,
                              family_canonical=t.family_canonical,
                              score=s_table, why=why))
    hits.sort(key=lambda h: -h.score)
    return hits[:k]


def retrieve_columns(idx: BqSchemaIndex, question: str, *,
                      k: int = 16) -> list[ColumnHit]:
    """Rank columns by stemmed-token overlap with the question."""
    qt = {_stem(t) for t in _question_terms(question)}
    if not qt: return []
    hits: list[ColumnHit] = []
    seen: set[tuple[str, str]] = set()
    for t, c in idx.all_columns():
        key = (t.family_canonical or t.fq_name, c.name)
        if key in seen: continue
        seen.add(key)
        cn = _stemmed_set(c.name)
        cd = _stemmed_set(c.description)
        score = len(qt & cn) * 1.5 + len(qt & cd) * 0.7
        # boost for column-question exact-token hits
        for sv in c.sample_values:
            if str(sv).lower() in question.lower():
                score += 0.4
        if score <= 0: continue
        hits.append(ColumnHit(fq_name=t.fq_name, column_name=c.name,
                                dtype=c.dtype, score=score,
                                sample_values=c.sample_values[:3]))
    hits.sort(key=lambda h: -h.score)
    return hits[:k]


_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


def chunk_markdown(text: str, *, source: str = '',
                     min_chunk: int = 100) -> list[DocChunk]:
    """Split markdown text on heading boundaries; small fragments merged."""
    if not text: return []
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        # No headings, return whole text as a single chunk
        return [DocChunk(source=source, title='', text=text.strip())]
    out: list[DocChunk] = []
    for i, m in enumerate(headings):
        start = m.start()
        end = headings[i+1].start() if i + 1 < len(headings) else len(text)
        title = m.group(2).strip()
        body = text[start:end].strip()
        if len(body) < min_chunk and out:
            out[-1].text += '\n' + body  # merge tiny chunks into the last
        else:
            out.append(DocChunk(source=source, title=title, text=body))
    return out


def retrieve_docs(question: str, doc_paths: list[Path], *,
                   k: int = 4, max_chars_per_chunk: int = 800) -> list[DocChunk]:
    """Read all doc files, chunk by markdown headings, rank by overlap.

    `doc_paths` should include the `external_knowledge` file plus any
    other relevant docs from `resource/documents/`. Returns the top-k
    chunks (truncated at `max_chars_per_chunk` for the prompt).
    """
    qt = {_stem(t) for t in _question_terms(question)}
    chunks: list[DocChunk] = []
    for p in doc_paths:
        if not p.exists(): continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for c in chunk_markdown(text, source=p.name):
            ts = _stemmed_set(c.title) | _stemmed_set(c.text[:1000])
            c.score = float(len(qt & ts))
            chunks.append(c)
    chunks.sort(key=lambda c: -c.score)
    out = []
    for c in chunks[:k]:
        c.text = c.text[:max_chars_per_chunk]
        out.append(c)
    return out


def join_hints(idx: BqSchemaIndex, table_keys: list[str]) -> list[str]:
    """Heuristic FK-like join hints: same-named ID columns across selected
    tables. Cheap, avoids relying on FK metadata that BQ doesn't ship.
    """
    sel: list[BqTable] = []
    for k in table_keys:
        kl = k.lower()
        for t in idx.tables:
            if t.fq_name.lower() == kl or t.family_canonical.lower() == kl:
                sel.append(t); break
    out: list[str] = []
    by_col: dict[str, list[tuple[str, str]]] = {}
    for t in sel:
        for c in t.columns:
            cn = c.name.lower()
            if cn.endswith('id') or cn.endswith('_id') or cn == 'id':
                by_col.setdefault(cn, []).append((t.fq_name, c.name))
    for cn, owners in by_col.items():
        if len(owners) >= 2:
            t1, c1 = owners[0]; t2, c2 = owners[1]
            out.append(f'-- likely join: `{t1}`.{c1} <-> `{t2}`.{c2} (shared id `{cn}`)')
    return out


@dataclass
class RetrievalBundle:
    tables: list[TableHit]
    columns: list[ColumnHit]
    docs: list[DocChunk]
    joins: list[str]
    selected_keys: list[str]
    fallback_used: bool = False
    rationale: list[str] = field(default_factory=list)


def retrieve_for_question(idx: BqSchemaIndex, question: str, *,
                            doc_paths: list[Path] | None = None,
                            k_tables: int = 6,
                            k_columns: int = 14,
                            k_docs: int = 3) -> RetrievalBundle:
    """One-shot retrieval bundle for the agent's prompt construction."""
    tabs = retrieve_tables(idx, question, k=k_tables)
    cols = retrieve_columns(idx, question, k=k_columns)
    docs = retrieve_docs(question, list(doc_paths or []), k=k_docs)

    # Selected keys: union of table_hits + tables that own retrieved columns
    keys: list[str] = [h.family_canonical or h.fq_name for h in tabs]
    for ch in cols:
        # Convert column.fq_name back to its family if relevant
        for t in idx.tables:
            if t.fq_name == ch.fq_name:
                keys.append(t.family_canonical or t.fq_name); break
    seen_keys: list[str] = []
    for k in keys:
        if k not in seen_keys: seen_keys.append(k)

    # Fallback: if no tables retrieved, take first 6 tables in the index
    fallback = False
    if not seen_keys:
        fallback = True
        seen_keys = [(t.family_canonical or t.fq_name) for t in idx.tables[:k_tables]]

    return RetrievalBundle(tables=tabs, columns=cols, docs=docs,
                              joins=join_hints(idx, seen_keys[:k_tables]),
                              selected_keys=seen_keys[:k_tables],
                              fallback_used=fallback,
                              rationale=[f'k_tables={len(tabs)}',
                                         f'k_columns={len(cols)}',
                                         f'k_docs={len(docs)}',
                                         f'fallback={fallback}'])
