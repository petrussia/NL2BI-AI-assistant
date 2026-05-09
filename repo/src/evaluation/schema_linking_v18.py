"""schema_linking_v18 — extractive schema linker over a live catalog jsonl.

The Phase 16 root-cause audit showed 95.7% of historical task failures
were true_hallucination — the model emitted identifiers that don't exist.
v17 confirmed that a stronger generator does not fix this in open-vocab.

Phase 18 hypothesis: feed the model a tight closed-set "schema pack"
retrieved from the LIVE catalog, then force structured JSON planning
over that closed set, then render SQL deterministically.

This module implements the retrieval. It is **deterministic** and
**embedding-free**: BM25-style lexical scoring with synonym expansion
and identifier-style normalization (camelCase → tokens, snake_case →
tokens). No GPU.

Inputs:
- live catalog jsonl (output of `tools/harvest_bq_live_catalog_v18.py`
  or `harvest_snow_live_catalog_v18.py`)
- NL question (+ optional database/alias hint)
- top_k caps for tables and columns

Output:
- ranked column records (with ancestor table info), one Python dict each
- diagnostic stats (token counts, db/table/column hit lists)
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


# --- Tokenization ---

_CAMEL_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')
_NUM_RE = re.compile(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])')
_NON_WORD = re.compile(r'[^A-Za-z0-9]+')


def tokenize(s: str) -> list:
    if not s:
        return []
    s = _NON_WORD.sub(' ', s)
    parts = []
    for w in s.split():
        # split camelCase, then numeric boundaries, then lower
        for sub in _CAMEL_RE.split(w):
            for sub2 in _NUM_RE.split(sub):
                if sub2:
                    parts.append(sub2.lower())
    return parts


# Light synonym table tuned for analytics / Spider2 question vocabulary.
# Goal: catch the typical NL question phrasings -> known schema lemmas.
_SYNONYMS: dict = {
    'count': ['n', 'num', 'number', 'cnt', 'total'],
    'total': ['sum', 'amount', 'aggregate'],
    'amount': ['value', 'sum', 'total'],
    'avg': ['average', 'mean'],
    'mean': ['avg', 'average'],
    'date': ['day', 'time', 'datetime', 'timestamp', 'dt'],
    'year': ['yr'],
    'month': ['mon', 'mo'],
    'user': ['users', 'customer', 'customers', 'client', 'clients', 'account', 'visitor'],
    'product': ['products', 'item', 'items', 'sku', 'goods'],
    'order': ['orders', 'purchase', 'transaction'],
    'price': ['cost', 'amount', 'value', 'fee'],
    'revenue': ['sales', 'income', 'earnings', 'gmv'],
    'spent': ['paid', 'amount', 'cost'],
    'name': ['title', 'label'],
    'id': ['identifier', 'pk', 'key'],
    'event': ['events', 'action', 'activity'],
    'click': ['clicks', 'tap'],
    'session': ['sessions', 'visit'],
    'category': ['categories', 'type', 'class'],
    'country': ['countries', 'nation', 'geo'],
    'city': ['cities', 'town'],
    'state': ['states', 'province', 'region'],
    'page': ['pages', 'url'],
    'view': ['views', 'impression'],
    'ad': ['ads', 'advertisement', 'campaign'],
    'agent': ['agents', 'employee', 'staff', 'rep'],
}


def expand_with_synonyms(toks: list) -> list:
    out = list(toks)
    for t in toks:
        if t in _SYNONYMS:
            out.extend(_SYNONYMS[t])
    return out


# --- BM25 ---

@dataclass
class BM25:
    k1: float = 1.5
    b: float = 0.75
    docs: list = field(default_factory=list)         # list[list[str]]
    df: dict = field(default_factory=dict)
    avgdl: float = 0.0
    N: int = 0

    def fit(self, docs: list) -> None:
        self.docs = docs
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, self.N)
        df = Counter()
        for d in docs:
            for t in set(d):
                df[t] += 1
        self.df = dict(df)

    def idf(self, t: str) -> float:
        n_t = self.df.get(t, 0)
        if n_t == 0:
            return 0.0
        return math.log((self.N - n_t + 0.5) / (n_t + 0.5) + 1.0)

    def score(self, q_toks: list, d_toks: list) -> float:
        if not q_toks or not d_toks:
            return 0.0
        dl = len(d_toks)
        c = Counter(d_toks)
        s = 0.0
        for t in q_toks:
            f = c.get(t, 0)
            if f == 0:
                continue
            idf = self.idf(t)
            s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / max(1, self.avgdl)))
        return s


# --- Catalog records ---

@dataclass
class CatalogColumn:
    db: str       # BQ project / Snow database
    schema: str   # BQ dataset / Snow schema
    table: str
    column: str
    data_type: str = ''
    is_nullable: str = ''
    description: str = ''
    field_path: str = ''  # for BQ nested fields (overrides column when present)
    alias: str = ''       # Spider2 alias for BQ; '' for Snow

    @property
    def fq(self) -> str:
        path = self.field_path or self.column
        return f"{self.db}.{self.schema}.{self.table}.{path}"


def load_catalog_jsonl(path: Path, lane: str) -> list:
    """Load v18 live catalog jsonl into CatalogColumn records.

    lane: 'bq' or 'snow' — determines field name normalization since BQ
          INFORMATION_SCHEMA columns are lowercase and Snow are uppercase.
    """
    out = []
    with path.open(encoding='utf-8') as fh:
        for ln in fh:
            r = json.loads(ln)
            if r.get('kind') == 'error':
                continue
            if r.get('kind') == 'table':
                continue  # tables handled separately by builder
            if lane == 'bq':
                # BQ live: project / dataset / table_schema / table_name / column_name / data_type / is_nullable / description / field_path
                out.append(CatalogColumn(
                    db=r.get('project', ''),
                    schema=r.get('dataset') or r.get('table_schema', ''),
                    table=r.get('table_name', ''),
                    column=r.get('column_name', ''),
                    data_type=r.get('data_type', '') or '',
                    is_nullable=str(r.get('is_nullable', '') or ''),
                    description=r.get('description') or '',
                    field_path=r.get('field_path') or '',
                    alias=r.get('alias', '') or '',
                ))
            elif lane == 'snow':
                out.append(CatalogColumn(
                    db=r.get('database') or r.get('TABLE_CATALOG', ''),
                    schema=r.get('TABLE_SCHEMA', ''),
                    table=r.get('TABLE_NAME', ''),
                    column=r.get('COLUMN_NAME', ''),
                    data_type=r.get('DATA_TYPE', '') or '',
                    is_nullable=str(r.get('IS_NULLABLE', '') or ''),
                    description=r.get('COMMENT') or '',
                    alias='',
                ))
    return out


# --- Schema linker ---

@dataclass
class LinkerHit:
    record: CatalogColumn
    score: float
    breakdown: dict = field(default_factory=dict)  # for diagnostics


@dataclass
class LinkerOutput:
    hits: list   # list[LinkerHit] sorted by score desc
    db_score: dict
    table_score: dict
    n_columns_indexed: int
    n_tables_indexed: int


class SchemaLinker:
    """Lexical schema linker over column records.

    The linker indexes each column with a "token bag" combining:
      tokenized(table_name) + tokenized(column_name) + tokenized(description)
      + tokenized(schema) + a coarse type tag
    Synonym expansion is applied to query tokens.
    """

    def __init__(self, columns: list):
        self.columns = columns
        self._docs = [self._make_doc(c) for c in columns]
        self.bm25 = BM25()
        self.bm25.fit(self._docs)

    @staticmethod
    def _make_doc(c: CatalogColumn) -> list:
        toks = []
        toks += tokenize(c.column)
        if c.field_path and c.field_path != c.column:
            toks += tokenize(c.field_path)
        toks += tokenize(c.table)
        toks += tokenize(c.schema)
        toks += tokenize(c.description)
        toks += tokenize(c.data_type)
        # Type signal: rough keyword for common types
        dt = (c.data_type or '').lower()
        if 'int' in dt or 'numeric' in dt or 'float' in dt or 'number' in dt:
            toks.append('numeric')
        if 'date' in dt or 'time' in dt or 'timestamp' in dt:
            toks.append('temporal')
        if 'string' in dt or 'text' in dt or 'varchar' in dt:
            toks.append('text')
        if 'array' in dt or 'repeated' in dt:
            toks.append('array')
        if 'struct' in dt or 'record' in dt:
            toks.append('struct')
        return toks

    def query(self, question: str, *, alias_filter: Optional[str] = None,
              top_columns: int = 80, top_tables: int = 25,
              db_filter: Optional[str] = None) -> LinkerOutput:
        q_toks = expand_with_synonyms(tokenize(question))
        # Score every column
        scored = []
        db_score = defaultdict(float)
        table_score = defaultdict(float)
        for i, c in enumerate(self.columns):
            if alias_filter and c.alias and c.alias != alias_filter:
                continue
            if db_filter and c.db != db_filter:
                continue
            s = self.bm25.score(q_toks, self._docs[i])
            if s <= 0:
                continue
            scored.append(LinkerHit(record=c, score=s, breakdown={'bm25': s}))
            db_key = f"{c.db}.{c.schema}"
            tab_key = f"{c.db}.{c.schema}.{c.table}"
            db_score[db_key] += s
            table_score[tab_key] += s
        scored.sort(key=lambda h: h.score, reverse=True)
        scored = scored[:top_columns]
        return LinkerOutput(
            hits=scored,
            db_score=dict(db_score),
            table_score=dict(table_score),
            n_columns_indexed=len(self.columns),
            n_tables_indexed=len({(c.db, c.schema, c.table) for c in self.columns}),
        )


# --- Tiny CLI smoke ---

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', required=True)
    ap.add_argument('--lane', choices=['bq', 'snow'], required=True)
    ap.add_argument('--question', required=True)
    ap.add_argument('--alias', default=None)
    ap.add_argument('--db', default=None)
    ap.add_argument('--top', type=int, default=15)
    a = ap.parse_args()
    cols = load_catalog_jsonl(Path(a.catalog), a.lane)
    print(f'loaded {len(cols)} columns')
    L = SchemaLinker(cols)
    r = L.query(a.question, alias_filter=a.alias, db_filter=a.db, top_columns=a.top)
    for h in r.hits:
        c = h.record
        print(f'  {h.score:7.2f}  {c.db}.{c.schema}.{c.table}.{c.field_path or c.column}  ({c.data_type})')
    print(f'top dbs:')
    for k, v in sorted(r.db_score.items(), key=lambda kv: -kv[1])[:5]:
        print(f'   {v:7.2f}  {k}')
