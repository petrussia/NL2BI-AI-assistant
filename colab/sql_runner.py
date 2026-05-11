"""Thin compatibility shim over colab.db_engine.

Legacy signature accepts a sqlite path; the new engine-aware signature
accepts a DataSourceSpec. extract_pipeline.py uses the new form; older
test fixtures keep working via the path overload.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from colab.db_engine import (
    DataSourceSpec,
    SqlExecutionResult,
    execute_select as _engine_execute_select,
)


def execute_select(
    target: Union[Path, str, DataSourceSpec],
    sql: str,
    *,
    timeout_ms: int,
    row_limit: int,
    read_only: bool = True,
) -> SqlExecutionResult:
    """Run a SELECT against any supported engine.

    `target` is either a DataSourceSpec (new path) or a sqlite Path/str
    (legacy callers — wrapped as a sqlite spec automatically).
    """
    if isinstance(target, DataSourceSpec):
        spec = target
    else:
        spec = DataSourceSpec(
            id="legacy", engine="sqlite", path=Path(target), name=str(target),
        )
    return _engine_execute_select(
        spec, sql, timeout_ms=timeout_ms, row_limit=row_limit, read_only=read_only,
    )


__all__ = ["execute_select", "SqlExecutionResult"]
