"""spider2_bq_schema_index_v8 — full BigQuery schema index for one db.

Loads all `.json` files under `resource/databases/bigquery/<db_id>/` into
a structured index keyed for fast retrieval. Each entry carries:
  - fully-qualified name (project.dataset.table)
  - dataset
  - table_name
  - columns: list of {name, type, description, sample_values}
  - description (table-level)
  - is_wildcard_family (multi-table family like ga_sessions_*)
  - wildcard_canonical (the suffix-stripped canonical name when applicable)
  - aliases (camelCase / snake_case / lowercase variants)

Used as the substrate for `spider2_bq_retrieval_v8`. Frozen at construction;
the index is read-only once built.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from spider2_tools_v7 import _split_identifier, _stem


# Detect wildcard families: tables that are date-suffixed copies, e.g.
# events_20210101, ga_sessions_20170201. We collapse them to one "family"
# entry the agent can address as `_TABLE_SUFFIX BETWEEN 'YYYYMMDD' AND 'YYYYMMDD'`.
_DATE_SUFFIX_RE = re.compile(r'^(?P<base>.+?)[_-](?P<date>\d{6,8})$')


@dataclass
class BqColumn:
    name: str
    dtype: str = ''
    description: str = ''
    sample_values: list[str] = field(default_factory=list)
    is_repeated: bool = False        # ARRAY<...>
    is_struct: bool = False          # STRUCT<...>
    nested: list = field(default_factory=list)  # nested field path strings


@dataclass
class BqTable:
    fq_name: str                 # `project.dataset.table` (no backticks)
    project: str
    dataset: str
    table_name: str
    columns: list[BqColumn] = field(default_factory=list)
    description: str = ''
    family_canonical: str = ''   # stripped date-suffix version, if any
    family_members: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    def is_wildcard_family(self) -> bool:
        return bool(self.family_canonical) and len(self.family_members) > 1


@dataclass
class BqSchemaIndex:
    db_id: str
    tables: list[BqTable] = field(default_factory=list)
    families: dict[str, BqTable] = field(default_factory=dict)  # family canonical -> repr table

    def all_columns(self) -> Iterable[tuple[BqTable, BqColumn]]:
        seen = set()
        for t in self.tables:
            key = t.family_canonical or t.fq_name
            if key in seen: continue
            seen.add(key)
            for c in t.columns:
                yield t, c

    def get_table(self, name: str) -> BqTable | None:
        n = name.lower()
        for t in self.tables:
            if t.fq_name.lower() == n: return t
            if t.table_name.lower() == n: return t
        return None


def _column_aliases(col_name: str) -> list[str]:
    if not col_name: return []
    parts = _split_identifier(col_name)
    return list({col_name, col_name.lower(), '_'.join(parts), ''.join(parts)})


def _detect_struct(dtype: str) -> tuple[bool, bool]:
    """Return (is_struct, is_repeated) from a BQ type string."""
    if not dtype: return False, False
    dt = dtype.upper()
    is_struct = 'STRUCT' in dt or 'RECORD' in dt
    is_repeated = dt.startswith('ARRAY') or 'REPEATED' in dt
    return is_struct, is_repeated


def _detect_family(table_name: str) -> tuple[str, str]:
    """If `table_name` matches `<base>_<YYYYMMDD>`, return (base, date).
    Otherwise return ('', ''). The base is the family canonical."""
    m = _DATE_SUFFIX_RE.match(table_name)
    if m: return m.group('base'), m.group('date')
    return '', ''


def build_index_from_db_dir(db_id: str, db_dir: str | Path) -> BqSchemaIndex:
    """Walk `<db_dir>/<fully_qualified_dataset>/<table>.json` and build the
    index. Each `<table>.json` is the format documented for Spider2-Lite.
    Wildcard families are collapsed: only the most recent member becomes
    the representative; family_members lists the rest.
    """
    db_dir = Path(db_dir)
    idx = BqSchemaIndex(db_id=db_id)
    fam_buckets: dict[str, list[BqTable]] = {}
    if not db_dir.exists():
        return idx

    for sub in sorted(db_dir.iterdir()):
        if not sub.is_dir(): continue
        fq_dataset = sub.name  # e.g. 'bigquery-public-data.ga4_obfuscated_sample_ecommerce'
        parts = fq_dataset.split('.', 1)
        project = parts[0] if len(parts) > 1 else ''
        dataset = parts[1] if len(parts) > 1 else fq_dataset

        for jf in sorted(sub.glob('*.json')):
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
            tdesc = str(d.get('description') or '')[:600]

            # Build columns
            col_metas: list[BqColumn] = []
            for i, cn in enumerate(cols):
                dt = (types[i] if i < len(types) else 'STRING') or 'STRING'
                cd = (descs[i] if i < len(descs) else '') if isinstance(descs, list) else ''
                is_struct, is_repeated = _detect_struct(str(dt))
                # Extract a few sample values from sample_rows
                samples = []
                for r in sample_rows[:5]:
                    if isinstance(r, dict) and cn in r:
                        v = r[cn]
                        if v is None: continue
                        s = str(v)[:80]
                        if s and s not in samples: samples.append(s)
                col_metas.append(BqColumn(name=str(cn), dtype=str(dt),
                                            description=str(cd)[:200],
                                            sample_values=samples,
                                            is_repeated=is_repeated,
                                            is_struct=is_struct))

            fq_name = f'{fq_dataset}.{tname}'
            family_base, family_date = _detect_family(tname)
            tab = BqTable(fq_name=fq_name, project=project, dataset=dataset,
                            table_name=tname, columns=col_metas,
                            description=tdesc)
            tab.aliases = list({tname, tname.lower(),
                                 '_'.join(_split_identifier(tname)),
                                 ''.join(_split_identifier(tname))})

            if family_base:
                key = f'{fq_dataset}.{family_base}'
                fam_buckets.setdefault(key, []).append(tab)
                tab.family_canonical = key
            idx.tables.append(tab)

    # Collapse wildcard families: representative = most-recent (max suffix)
    for key, members in fam_buckets.items():
        if len(members) <= 1:
            continue
        members_sorted = sorted(members, key=lambda t: t.table_name, reverse=True)
        rep = members_sorted[0]
        rep.family_members = [m.table_name for m in members_sorted]
        idx.families[key] = rep

    return idx


def render_table_block(t: BqTable, *, max_cols: int = 30,
                         include_samples: bool = False) -> str:
    """Pretty-print a table for the LLM prompt."""
    head = f'`{t.fq_name}`'
    if t.is_wildcard_family():
        head = f'`{t.family_canonical}_*`  -- family of {len(t.family_members)} daily tables (use _TABLE_SUFFIX)'
    lines = [head]
    if t.description:
        lines.append(f'  -- {t.description[:200]}')
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


def render_subset(idx: BqSchemaIndex, table_keys: list[str], *,
                    max_cols: int = 30, include_samples: bool = True) -> str:
    """Render a subset of the index by table fq_name OR family_canonical."""
    out: list[str] = []
    seen: set[str] = set()
    for key in table_keys:
        kl = key.lower()
        for t in idx.tables:
            if t.fq_name.lower() == kl or t.family_canonical.lower() == kl:
                if t.fq_name in seen: break
                seen.add(t.fq_name)
                out.append(render_table_block(t, max_cols=max_cols,
                                                include_samples=include_samples))
                break
    return '\n\n'.join(out)
