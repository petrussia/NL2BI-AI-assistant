"""Thin compatibility shim over colab.db_engine.

Legacy signature: load_schema(sqlite_path, data_source_id=..., schema_version=...)
New signature:    load_schema(DataSourceSpec, sample_rows=...)
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from colab.db_engine import (
    ColumnSchema,
    DatabaseSchema,
    DataSourceSpec,
    TableSchema,
    load_schema as _engine_load_schema,
)


def load_schema(
    target: Union[Path, str, DataSourceSpec],
    data_source_id: str | None = None,
    schema_version: str | None = None,
    sample_rows: int = 3,
) -> DatabaseSchema:
    if isinstance(target, DataSourceSpec):
        spec = target
        if schema_version and not spec.schema_version:
            spec = DataSourceSpec(
                id=spec.id, engine=spec.engine, path=spec.path, dsn=spec.dsn,
                name=spec.name, db_name=spec.db_name,
                schema_version=schema_version, pg_schemas=spec.pg_schemas,
            )
    else:
        spec = DataSourceSpec(
            id=data_source_id or "legacy",
            engine="sqlite",
            path=Path(target),
            name=str(target),
            schema_version=schema_version,
        )
    return _engine_load_schema(spec, sample_rows=sample_rows)


__all__ = ["load_schema", "DatabaseSchema", "TableSchema", "ColumnSchema"]
