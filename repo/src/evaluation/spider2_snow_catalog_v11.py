"""spider2_snow_catalog_v11 — canonical Snowflake catalog for Spider2-Snow.

Builds a structured catalog from the canonical Snow metadata files that
ship with `xlang-ai/Spider2/spider2-snow/resource/databases/<DB>/<SCHEMA>/<table>.json`.

Catalog shape:
    {
      "databases": {
        "<DB>": {
          "schemas": {
            "<SCHEMA>": {
              "tables": {
                "<TABLE>": {
                  "fq_name": "DB.SCHEMA.TABLE",
                  "columns": [{"name": "...", "type": "...", "description": "..."}, ...],
                  "description": "..."
                }, ...
              }
            }, ...
          }
        }, ...
      },
      "version": "v11"
    }

Cached at `outputs/cache/spider2_snow_catalog_v11.json`. Build is
idempotent. Adding a `--db DB` flag at the loader allows lazy partial
build (one DB at a time) which is what the runner uses.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[3]
CACHE_PATH = REPO / 'outputs' / 'cache' / 'spider2_snow_catalog_v11.json'


@dataclass
class Column:
    name: str
    type: str = ''
    description: str = ''
    samples: list = field(default_factory=list)


@dataclass
class Table:
    fq_name: str         # DB.SCHEMA.TABLE
    database: str
    schema: str
    table: str
    columns: list[Column] = field(default_factory=list)
    description: str = ''


@dataclass
class Catalog:
    databases: dict[str, dict[str, dict[str, Table]]] = field(default_factory=dict)
    version: str = 'v11'

    def has_table(self, db: str, table: str, schema: str = None) -> bool:
        d = self.databases.get(db.upper())
        if not d: return False
        if schema:
            sch = d.get(schema.upper())
            if not sch: return False
            return table.upper() in {k.upper() for k in sch.keys()}
        for sch in d.values():
            if any(t.upper() == table.upper() for t in sch.keys()):
                return True
        return False

    def find_table(self, db: str, table: str, schema: str = None) -> Table | None:
        d = self.databases.get(db.upper())
        if not d: return None
        if schema:
            sch = d.get(schema.upper())
            if sch:
                for k, t in sch.items():
                    if k.upper() == table.upper(): return t
            return None
        for sch in d.values():
            for k, t in sch.items():
                if k.upper() == table.upper(): return t
        return None

    def all_tables(self, db: str) -> Iterable[Table]:
        d = self.databases.get(db.upper())
        if not d: return
        for sch in d.values():
            for t in sch.values():
                yield t

    def all_columns(self, db: str, table: str = None) -> Iterable[tuple[Table, Column]]:
        for t in self.all_tables(db):
            if table and t.table.upper() != table.upper(): continue
            for c in t.columns:
                yield t, c


def build_db_from_dir(db: str, db_dir: Path,
                          *, max_tables_per_schema: int = 80) -> dict:
    """Walk db_dir and produce the per-DB sub-catalog as a dict for JSON."""
    schemas: dict[str, dict[str, dict]] = {}
    if not db_dir.is_dir():
        return {}
    for sch_dir in sorted(db_dir.iterdir()):
        if not sch_dir.is_dir(): continue
        schema_name = sch_dir.name
        tables_d: dict[str, dict] = {}
        n = 0
        for jf in sorted(sch_dir.glob('*.json')):
            try:
                d = json.loads(jf.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(d, dict): continue
            tname = (d.get('table_name') or jf.stem).strip()
            cols = d.get('column_names') or []
            types = d.get('column_types') or []
            descs = d.get('column_descriptions') or [''] * len(cols)
            samples = d.get('sample_rows') or []
            if not tname or not cols: continue
            col_metas = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else 'VARCHAR') or 'VARCHAR'
                cd = (descs[i] if isinstance(descs, list) and i < len(descs) else '')
                sample_vals = []
                for r in samples[:5]:
                    if isinstance(r, dict) and cn in r:
                        v = r[cn]
                        if v is None: continue
                        s = str(v)[:60]
                        if s and s not in sample_vals: sample_vals.append(s)
                col_metas.append({'name': str(cn), 'type': str(dt),
                                    'description': str(cd)[:160],
                                    'samples': sample_vals})
            tables_d[tname] = {
                'fq_name': f'{db}.{schema_name}.{tname}',
                'database': db, 'schema': schema_name, 'table': tname,
                'description': str(d.get('description') or '')[:200],
                'columns': col_metas,
            }
            n += 1
            if n >= max_tables_per_schema: break
        if tables_d:
            schemas[schema_name] = {'tables': tables_d}
    return {'schemas': schemas}


def load_catalog(path: Path = CACHE_PATH) -> Catalog:
    if not path.exists():
        return Catalog()
    raw = json.loads(path.read_text(encoding='utf-8'))
    cat = Catalog(version=raw.get('version', 'v11'))
    for db, db_d in (raw.get('databases') or {}).items():
        sch_dict = {}
        for sch, sch_d in (db_d.get('schemas') or {}).items():
            tbl_dict = {}
            for tname, td in (sch_d.get('tables') or {}).items():
                cols = [Column(name=c['name'], type=c.get('type', ''),
                                  description=c.get('description', ''),
                                  samples=c.get('samples', []))
                          for c in td.get('columns', [])]
                tbl_dict[tname] = Table(
                    fq_name=td.get('fq_name', f'{db}.{sch}.{tname}'),
                    database=db, schema=sch, table=tname,
                    columns=cols, description=td.get('description', ''))
            sch_dict[sch] = tbl_dict
        cat.databases[db] = sch_dict
    return cat


def save_catalog_dict(cat_dict: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cat_dict, indent=2, ensure_ascii=False),
                       encoding='utf-8')


def add_db_to_catalog(db: str, db_dir: Path, *,
                          path: Path = CACHE_PATH) -> dict:
    """Builds DB sub-catalog from `db_dir` and merges into the persisted JSON."""
    raw = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            raw = {}
    raw.setdefault('version', 'v11')
    raw.setdefault('databases', {})
    sub = build_db_from_dir(db, db_dir)
    if sub:
        raw['databases'][db] = sub
        save_catalog_dict(raw, path)
    return raw
