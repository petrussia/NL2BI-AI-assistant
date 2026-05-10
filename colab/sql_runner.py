from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SqlExecutionResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    column_sql_types: dict[str, str]
    row_count: int
    truncated: bool
    timed_out: bool
    latency_ms: int
    error: str | None = None


def _arm_interrupt(conn: sqlite3.Connection, timeout_ms: int) -> threading.Timer:
    """Schedule sqlite3 interrupt() after timeout_ms. Returns the Timer."""
    timer = threading.Timer(timeout_ms / 1000.0, conn.interrupt)
    timer.daemon = True
    timer.start()
    return timer


def execute_select(
    sqlite_path: Path,
    sql: str,
    *,
    timeout_ms: int,
    row_limit: int,
    read_only: bool = True,
) -> SqlExecutionResult:
    started = time.monotonic()
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    column_types: dict[str, str] = {}
    timed_out = False
    truncated = False
    error: str | None = None

    uri = f"file:{sqlite_path}?mode={'ro' if read_only else 'rw'}"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=max(0.1, timeout_ms / 1000.0))
    except sqlite3.Error as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return SqlExecutionResult(
            columns=[],
            rows=[],
            column_sql_types={},
            row_count=0,
            truncated=False,
            timed_out=False,
            latency_ms=latency_ms,
            error=str(exc),
        )

    timer: threading.Timer | None = None
    try:
        if read_only:
            try:
                conn.execute("PRAGMA query_only = 1")
            except sqlite3.Error:
                pass
        timer = _arm_interrupt(conn, timeout_ms)
        cur = conn.execute(sql)
        if cur.description is None:
            columns = []
        else:
            columns = [d[0] for d in cur.description]
            try:
                meta = conn.execute(f"SELECT * FROM ({sql}) LIMIT 0")
                column_types = {
                    d[0]: (d[1] or "")
                    for d in (meta.description or [])
                }
            except sqlite3.Error:
                column_types = {c: "" for c in columns}
        fetched = 0
        cap = row_limit + 1 if row_limit > 0 else None
        while True:
            row = cur.fetchone()
            if row is None:
                break
            rows.append({col: row[idx] for idx, col in enumerate(columns)})
            fetched += 1
            if cap is not None and fetched >= cap:
                break
        if cap is not None and fetched > row_limit:
            rows = rows[:row_limit]
            truncated = True
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            timed_out = True
        else:
            error = str(exc)
    except sqlite3.Error as exc:
        error = str(exc)
    finally:
        if timer is not None:
            timer.cancel()
        try:
            conn.close()
        except Exception:
            pass

    latency_ms = int((time.monotonic() - started) * 1000)
    return SqlExecutionResult(
        columns=columns,
        rows=rows,
        column_sql_types=column_types or {c: "" for c in columns},
        row_count=len(rows),
        truncated=truncated,
        timed_out=timed_out,
        latency_ms=latency_ms,
        error=error,
    )
