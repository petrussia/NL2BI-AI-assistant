from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ColumnSchema:
    name: str
    sql_type: str
    nullable: bool
    primary_key: bool
    examples: list[Any] = field(default_factory=list)


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnSchema]


@dataclass
class DatabaseSchema:
    data_source_id: str
    sqlite_path: Path
    tables: list[TableSchema]
    schema_version: str | None = None

    def render_for_prompt(self) -> str:
        chunks: list[str] = []
        for table in self.tables:
            cols = ", ".join(f"{c.name} {c.sql_type}" for c in table.columns)
            chunks.append(f"TABLE {table.name}({cols})")
        return "\n".join(chunks)

    def column_lookup(self) -> dict[str, tuple[str, ColumnSchema]]:
        lookup: dict[str, tuple[str, ColumnSchema]] = {}
        for table in self.tables:
            for col in table.columns:
                lookup.setdefault(col.name.lower(), (table.name, col))
        return lookup


def load_schema(
    sqlite_path: Path,
    data_source_id: str,
    schema_version: str | None = None,
    sample_rows: int = 3,
) -> DatabaseSchema:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    tables: list[TableSchema] = []
    with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        names = [row["name"] for row in cur.fetchall()]
        for table_name in names:
            cols: list[ColumnSchema] = []
            info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            sample = []
            try:
                sample_cur = conn.execute(
                    f'SELECT * FROM "{table_name}" LIMIT ?', (sample_rows,)
                )
                sample = [dict(r) for r in sample_cur.fetchall()]
            except sqlite3.Error:
                sample = []
            for row in info:
                col_name = row["name"]
                examples = [r.get(col_name) for r in sample if r.get(col_name) is not None]
                cols.append(
                    ColumnSchema(
                        name=col_name,
                        sql_type=row["type"] or "",
                        nullable=row["notnull"] == 0,
                        primary_key=row["pk"] == 1,
                        examples=examples[:3],
                    )
                )
            tables.append(TableSchema(name=table_name, columns=cols))

    return DatabaseSchema(
        data_source_id=data_source_id,
        sqlite_path=sqlite_path,
        tables=tables,
        schema_version=schema_version,
    )
