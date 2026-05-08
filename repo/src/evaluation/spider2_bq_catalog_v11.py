"""spider2_bq_catalog_v11 — canonical BigQuery catalog for Spider2-Lite BQ lane.

Reads from Drive (or `/content/spider2_lite_extract`) at:
    `resource/databases/bigquery/<DB>/<DATASET>/<table>.json`

Each table JSON has `table_fullname` like `project.dataset.table` and
column metadata. We treat `project.dataset.table` as the canonical
3-part identifier for BQ.

Catalog shape (mirrors Snow v11 catalog):
    {
      "databases": {
        "<DB>": {
          "datasets": {
            "<DATASET>": {
              "tables": {
                "<TABLE>": {
                  "fq_name": "project.dataset.table",
                  "project": "...", "dataset": "...", "table": "...",
                  "columns": [{"name": "...", "type": "...",
                                  "description": "...", "samples": [...]}],
                  "description": "..."
                }
              }
            }
          }
        }
      }
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[3]
CACHE_PATH = REPO / 'outputs' / 'cache' / 'spider2_bq_catalog_v11.json'


@dataclass
class BqColumn:
    name: str
    type: str = ''
    description: str = ''
    samples: list = field(default_factory=list)


@dataclass
class BqTable:
    fq_name: str           # project.dataset.table
    project: str
    dataset: str
    table: str
    columns: list[BqColumn] = field(default_factory=list)
    description: str = ''


@dataclass
class BqCatalog:
    databases: dict[str, dict[str, dict[str, BqTable]]] = field(default_factory=dict)
    version: str = 'v11_bq'

    def all_tables(self, db: str) -> Iterable[BqTable]:
        d = self.databases.get(db.upper())
        if not d: return
        for ds in d.values():
            for t in ds.values():
                yield t

    def all_columns(self, db: str) -> Iterable[tuple[BqTable, BqColumn]]:
        for t in self.all_tables(db):
            for c in t.columns:
                yield t, c

    def find_table(self, db: str, table: str) -> BqTable | None:
        for t in self.all_tables(db):
            if t.table.upper() == table.upper(): return t
        return None


def build_db_from_dir(db: str, db_dir: Path,
                          *, max_tables_per_dataset: int = 80) -> dict:
    datasets: dict[str, dict[str, dict]] = {}
    if not db_dir.is_dir():
        return {'datasets': datasets}
    for ds_dir in sorted(db_dir.iterdir()):
        if not ds_dir.is_dir(): continue
        ds_name = ds_dir.name
        tables_d: dict[str, dict] = {}
        n = 0
        for jf in sorted(ds_dir.glob('*.json')):
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
            # project from table_fullname
            tfn = d.get('table_fullname', '')
            project = ''
            if tfn and '.' in tfn:
                parts = tfn.split('.')
                if len(parts) >= 3:
                    project = parts[0]
            col_metas = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else 'STRING') or 'STRING'
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
            fq = f'{project}.{ds_name}.{tname}' if project else f'{db}.{ds_name}.{tname}'
            tables_d[tname] = {
                'fq_name': fq, 'project': project,
                'dataset': ds_name, 'table': tname,
                'description': str(d.get('description') or '')[:200],
                'columns': col_metas,
            }
            n += 1
            if n >= max_tables_per_dataset: break
        if tables_d:
            datasets[ds_name] = {'tables': tables_d}
    return {'datasets': datasets}


def load_catalog(path: Path = CACHE_PATH) -> BqCatalog:
    if not path.exists():
        return BqCatalog()
    raw = json.loads(path.read_text(encoding='utf-8'))
    cat = BqCatalog(version=raw.get('version', 'v11_bq'))
    for db, db_d in (raw.get('databases') or {}).items():
        ds_dict = {}
        for ds, ds_d in (db_d.get('datasets') or {}).items():
            tbl_dict = {}
            for tname, td in (ds_d.get('tables') or {}).items():
                cols = [BqColumn(name=c['name'], type=c.get('type', ''),
                                    description=c.get('description', ''),
                                    samples=c.get('samples', []))
                          for c in td.get('columns', [])]
                tbl_dict[tname] = BqTable(
                    fq_name=td.get('fq_name', f'{db}.{ds}.{tname}'),
                    project=td.get('project', ''),
                    dataset=ds, table=tname, columns=cols,
                    description=td.get('description', ''))
            ds_dict[ds] = tbl_dict
        cat.databases[db] = ds_dict
    return cat


def save_catalog_dict(cat_dict: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cat_dict, indent=2, ensure_ascii=False),
                       encoding='utf-8')


def add_db_to_catalog(db: str, db_dir: Path, *,
                          path: Path = CACHE_PATH) -> dict:
    raw = {}
    if path.exists():
        try: raw = json.loads(path.read_text(encoding='utf-8'))
        except Exception: raw = {}
    raw.setdefault('version', 'v11_bq')
    raw.setdefault('databases', {})
    sub = build_db_from_dir(db, db_dir)
    if sub:
        raw['databases'][db] = sub
        save_catalog_dict(raw, path)
    return raw
