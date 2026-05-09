"""evidence_store_v2 — keyed evidence corpus per benchmark.

Stores small text snippets keyed by (db_id, scope, table?, column?).
- BIRD: per-item `evidence` field becomes a (db_id, ?) snippet.
- Spider: column comments derived from CREATE TABLE -> per-column.
- Spider2-Lite: schema description text -> per-database.

Used by retrieval_hybrid_v2 as one of several corpora and by the
prompt assembler when injecting "Domain hint" content.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class EvidenceItem:
    text: str
    scope: str = 'database'        # 'database' | 'table' | 'column' | 'item'
    table: str = ''
    column: str = ''
    src: str = ''                  # provenance label
    weight: float = 1.0            # downstream confidence prior
    extra: dict = field(default_factory=dict)


class EvidenceStore:
    """In-memory store keyed by db_id."""

    def __init__(self) -> None:
        self._by_db: dict[str, list[EvidenceItem]] = {}
        self._by_item: dict[tuple[str, str], list[EvidenceItem]] = {}

    def add(self, db_id: str, item: EvidenceItem) -> None:
        self._by_db.setdefault(db_id, []).append(item)

    def add_item(self, db_id: str, item_id: str, item: EvidenceItem) -> None:
        self._by_item.setdefault((db_id, item_id), []).append(item)

    def for_db(self, db_id: str) -> list[EvidenceItem]:
        return list(self._by_db.get(db_id, []))

    def for_item(self, db_id: str, item_id: str) -> list[EvidenceItem]:
        return list(self._by_item.get((db_id, item_id), []))

    def search(self, db_id: str, *,
               table: str | None = None,
               column: str | None = None) -> list[EvidenceItem]:
        out: list[EvidenceItem] = []
        for it in self._by_db.get(db_id, []):
            if table and it.table and it.table.lower() != table.lower(): continue
            if column and it.column and it.column.lower() != column.lower(): continue
            out.append(it)
        return out


# ---------------- bulk loaders ----------------

def load_bird(store: EvidenceStore, bird_examples: Iterable[dict]) -> int:
    """Each BIRD item carries an `evidence` field — load both as
    per-item evidence (keyed by question_id) and as per-db evidence
    (so retrieval can surface other items' evidence text too).
    """
    n = 0
    for ex in bird_examples:
        ev = (ex.get('evidence') or '').strip()
        if not ev: continue
        db_id = ex['db_id']
        qid = str(ex.get('question_id', ex.get('question','')[:40]))
        item = EvidenceItem(text=ev, scope='item', src='bird_evidence')
        store.add_item(db_id, qid, item)
        store.add(db_id, item)
        n += 1
    return n


def load_spider_from_ir(store: EvidenceStore, irs: Iterable) -> int:
    """For Spider: derive per-column evidence from comments embedded in IR
    (when present) and per-table evidence from table comment.
    """
    n = 0
    for ir in irs:
        if ir.comment:
            store.add(ir.db_id, EvidenceItem(text=ir.comment, scope='database',
                                              src='spider_db_doc'))
            n += 1
        for t in ir.tables:
            if t.comment:
                store.add(ir.db_id, EvidenceItem(text=t.comment, scope='table',
                                                  table=t.name, src='spider_table_doc'))
                n += 1
            for c in t.columns:
                if c.comment:
                    store.add(ir.db_id, EvidenceItem(text=c.comment, scope='column',
                                                      table=t.name, column=c.name,
                                                      src='spider_col_doc'))
                    n += 1
    return n
