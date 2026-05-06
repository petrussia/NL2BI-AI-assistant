"""spider2_sf_schema_index_v8 — Snowflake schema index for one db.

Walks `resource/databases/snowflake/<DB>/<SCHEMA>/<table>.json` and
produces a structured index analogous to `spider2_bq_schema_index_v8`
but with Snowflake-specific identifier rules:

  - `original_name` is `DB.SCHEMA.TABLE` (no backticks)
  - identifiers are uppercase by default (Snowflake unquoted-identifier
    behaviour), but the index keeps the original case from the JSON

Used by the SF agent's retrieval + prompting layer.

Cache file: `outputs/cache/spider2_sf_schema_index_v8/<DB>.json`
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from spider2_tools_v7 import _split_identifier, _stem


@dataclass
class SfColumn:
    name: str
    dtype: str = ''
    description: str = ''
    sample_values: list[str] = field(default_factory=list)


@dataclass
class SfTable:
    fq_name: str            # 'DB.SCHEMA.TABLE'
    database: str
    schema: str
    table_name: str
    columns: list[SfColumn] = field(default_factory=list)
    description: str = ''


@dataclass
class SfSchemaIndex:
    db_id: str              # logical Spider2 db name (e.g. 'PATENTS')
    tables: list[SfTable] = field(default_factory=list)

    def all_columns(self) -> Iterable[tuple[SfTable, SfColumn]]:
        for t in self.tables:
            for c in t.columns:
                yield t, c

    def by_table(self, name: str) -> SfTable | None:
        n = name.upper()
        for t in self.tables:
            if t.fq_name.upper() == n: return t
            if t.table_name.upper() == n: return t
        return None


def build_index_from_db_dir(db_id: str, db_dir: str | Path,
                              *, max_tables: int = 100) -> SfSchemaIndex:
    """Walk the local Spider2 metadata for one Snowflake database.

    Layout expected:
        <db_dir>/<SCHEMA>/<table>.json
    Each `<table>.json` follows the Spider2 BQ format
    (`table_name`, `column_names`, `column_types`, `sample_rows`,
    `description`).
    """
    db_dir = Path(db_dir)
    idx = SfSchemaIndex(db_id=db_id)
    if not db_dir.exists() or not db_dir.is_dir():
        return idx

    for schema_dir in sorted(db_dir.iterdir()):
        if not schema_dir.is_dir(): continue
        schema = schema_dir.name  # usually 'PUBLIC'
        for jf in sorted(schema_dir.glob('*.json')):
            try:
                d = json.loads(jf.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(d, dict): continue
            tname = (d.get('table_name') or jf.stem).strip()
            cols = d.get('column_names') or []
            types = d.get('column_types') or []
            descs = d.get('column_descriptions') or [''] * len(cols)
            sample_rows = d.get('sample_rows') or []
            if not tname or not cols: continue
            col_metas: list[SfColumn] = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else 'VARCHAR') or 'VARCHAR'
                cd = (descs[i] if i < len(descs) else '') if isinstance(descs, list) else ''
                samples = []
                for r in sample_rows[:5]:
                    if isinstance(r, dict) and cn in r:
                        v = r[cn]
                        if v is None: continue
                        s = str(v)[:80]
                        if s and s not in samples: samples.append(s)
                col_metas.append(SfColumn(name=str(cn), dtype=str(dt),
                                            description=str(cd)[:200],
                                            sample_values=samples))
            fq = f'{db_id}.{schema}.{tname}'
            idx.tables.append(SfTable(
                fq_name=fq, database=db_id, schema=schema,
                table_name=tname, columns=col_metas,
                description=str(d.get('description') or '')[:300],
            ))
            if len(idx.tables) >= max_tables: return idx
    return idx


def build_index_via_executor(db_id: str, executor, *,
                                schemas_limit: int = 20,
                                tables_limit: int = 100,
                                rows_per_table: int = 0) -> SfSchemaIndex:
    """Fallback: use a Snowflake executor to introspect via SHOW commands.

    Used only when local metadata is unavailable. Costs nothing
    (SHOW + DESCRIBE TABLE are metadata operations; no warehouse usage).
    """
    idx = SfSchemaIndex(db_id=db_id)
    rs = executor(f'SHOW SCHEMAS IN DATABASE "{db_id}"', dry_run=False,
                    max_rows_override=schemas_limit)
    if not rs['ok']: return idx
    schemas = [str(r[1]) for r in (rs.get('rows') or [])]
    for schema in schemas:
        if schema.upper() == 'INFORMATION_SCHEMA': continue
        rs = executor(f'SHOW TABLES IN SCHEMA "{db_id}"."{schema}"',
                        dry_run=False, max_rows_override=tables_limit)
        if not rs['ok']: continue
        tables = [str(r[1]) for r in (rs.get('rows') or [])]
        for tname in tables:
            rs2 = executor(f'DESCRIBE TABLE "{db_id}"."{schema}"."{tname}"',
                            dry_run=False, max_rows_override=200)
            if not rs2['ok']: continue
            cols = []
            for r in (rs2.get('rows') or []):
                cols.append(SfColumn(name=str(r[0]), dtype=str(r[1])))
            fq = f'{db_id}.{schema}.{tname}'
            idx.tables.append(SfTable(
                fq_name=fq, database=db_id, schema=schema,
                table_name=tname, columns=cols))
            if len(idx.tables) >= tables_limit:
                return idx
    return idx


def render_table_block(t: SfTable, *, max_cols: int = 30,
                         include_samples: bool = True) -> str:
    head = f'"{t.fq_name}"'
    lines = [head]
    if t.description: lines.append(f'  -- {t.description[:200]}')
    cols = t.columns[:max_cols]
    truncated = len(t.columns) > max_cols
    for c in cols:
        line = f'  {c.name} {c.dtype}'
        if c.description: line += f'  -- {c.description[:120]}'
        if include_samples and c.sample_values:
            line += f'  /* eg. {", ".join(c.sample_values[:3])} */'
        lines.append(line)
    if truncated:
        lines.append(f'  -- ...{len(t.columns) - max_cols} more columns')
    return '\n'.join(lines)


def render_subset(idx: SfSchemaIndex, table_keys: list[str], *,
                    max_cols: int = 25, include_samples: bool = True) -> str:
    if not idx.tables: return f'(empty index for {idx.db_id})'
    out: list[str] = [f'-- DB: {idx.db_id} (snowflake)']
    seen: set[str] = set()
    for key in table_keys:
        kU = key.upper()
        for t in idx.tables:
            if t.fq_name.upper() == kU or t.table_name.upper() == kU:
                if t.fq_name in seen: break
                seen.add(t.fq_name)
                out.append(render_table_block(t, max_cols=max_cols,
                                                include_samples=include_samples))
                break
    if not seen:
        # Fallback: render the first 5 tables so the prompt isn't empty
        for t in idx.tables[:5]:
            out.append(render_table_block(t, max_cols=max_cols,
                                            include_samples=include_samples))
    return '\n\n'.join(out)


def cache_path(repo_root: Path | str, db_id: str) -> Path:
    return Path(repo_root) / 'outputs' / 'cache' / 'spider2_sf_schema_index_v8' / f'{db_id}.json'


def save_to_cache(idx: SfSchemaIndex, repo_root: Path | str) -> Path:
    p = cache_path(repo_root, idx.db_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'db_id': idx.db_id,
        'tables': [
            {'fq_name': t.fq_name, 'database': t.database, 'schema': t.schema,
              'table_name': t.table_name, 'description': t.description,
              'columns': [{'name': c.name, 'type': c.dtype,
                            'description': c.description,
                            'sample_values': c.sample_values}
                            for c in t.columns]}
            for t in idx.tables
        ],
    }
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return p
