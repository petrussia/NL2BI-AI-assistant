"""Multi-engine database abstraction.

Three engines supported:
  * sqlite  — default, used for Spider/BIRD/Moscow demo sets
  * duckdb  — embedded analytical engine (Spider2 asana_dbt)
  * postgres — real production-style DB (Northwind RU)

Each engine implements:
  * connect(spec) — opens a read-only connection
  * load_schema(spec, sample_rows) — returns DatabaseSchema (engine-agnostic)
  * execute_select(spec, sql, timeout_ms, row_limit, read_only) — returns
    SqlExecutionResult

The pipeline talks to this module via factory functions; concrete drivers
(sqlite3, duckdb, psycopg2) are imported lazily so absence of one doesn't
break the others.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# -----------------------------------------------------------------------
# Spec + result dataclasses (shared across engines)
# -----------------------------------------------------------------------

@dataclass(frozen=True)
class DataSourceSpec:
    """Everything the pipeline needs to address one data source."""
    id: str
    engine: str  # "sqlite" | "duckdb" | "postgres"
    # Embedded engines: filesystem path.
    path: Path | None = None
    # Remote engines: connection string.
    dsn: str | None = None
    # Human-readable name + schema version (prompt + UI metadata).
    name: str | None = None
    db_name: str | None = None
    schema_version: str | None = None
    # Optional Postgres-specific: limit schemas the loader scans
    # (defaults to ["public"]).
    pg_schemas: tuple[str, ...] = ("public",)


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
class ForeignKey:
    """One foreign-key edge between two tables.

    Stored on DatabaseSchema and surfaced to the prompt as a navigation
    graph so the model can write multi-hop joins (e.g. orders → customers
    → regions) without inventing a non-existent direct FK."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str


@dataclass
class DatabaseSchema:
    data_source_id: str
    engine: str
    tables: list[TableSchema]
    schema_version: str | None = None
    # Kept for backward compatibility with the SQLite-only era; older
    # callers still read this field.
    sqlite_path: Path | None = None
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    def render_for_prompt(self) -> str:
        chunks: list[str] = []
        for table in self.tables:
            cols_parts = []
            for c in table.columns:
                marker = " PK" if c.primary_key else ""
                cols_parts.append(f"{c.name} {c.sql_type}{marker}")
            chunks.append(f"TABLE {table.name}({', '.join(cols_parts)})")
        if self.foreign_keys:
            chunks.append("")
            chunks.append("FOREIGN KEYS:")
            for fk in self.foreign_keys:
                chunks.append(
                    f"  {fk.from_table}.{fk.from_column} -> {fk.to_table}.{fk.to_column}"
                )
        return "\n".join(chunks)

    def column_lookup(self) -> dict[str, tuple[str, "ColumnSchema"]]:
        lookup: dict[str, tuple[str, ColumnSchema]] = {}
        for table in self.tables:
            for col in table.columns:
                lookup.setdefault(col.name.lower(), (table.name, col))
        return lookup


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


# -----------------------------------------------------------------------
# Dialect hints — used by prompt.py to tell the model what SQL to write.
# -----------------------------------------------------------------------

DIALECT_PROMPT_HINT = {
    "sqlite": "SQLite",
    "duckdb": "DuckDB (PostgreSQL-compatible analytical SQL)",
    "postgres": "PostgreSQL 14+",
}


def dialect_label(engine: str) -> str:
    return DIALECT_PROMPT_HINT.get(engine, engine.upper())


# =======================================================================
# SQLite implementation (existing logic, lifted here verbatim).
# =======================================================================

def _sqlite_arm_interrupt(conn: sqlite3.Connection, timeout_ms: int) -> threading.Timer:
    timer = threading.Timer(timeout_ms / 1000.0, conn.interrupt)
    timer.daemon = True
    timer.start()
    return timer


def _sqlite_execute(spec: DataSourceSpec, sql: str, *, timeout_ms: int,
                   row_limit: int, read_only: bool) -> SqlExecutionResult:
    started = time.monotonic()
    if spec.path is None:
        return _empty_result(started, error="sqlite spec missing path")
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    column_types: dict[str, str] = {}
    timed_out = False
    truncated = False
    error: str | None = None

    uri = f"file:{spec.path}?mode={'ro' if read_only else 'rw'}"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=max(0.1, timeout_ms / 1000.0))
    except sqlite3.Error as exc:
        return _empty_result(started, error=str(exc))

    timer: threading.Timer | None = None
    try:
        if read_only:
            try:
                conn.execute("PRAGMA query_only = 1")
            except sqlite3.Error:
                pass
        timer = _sqlite_arm_interrupt(conn, timeout_ms)
        cur = conn.execute(sql)
        if cur.description is None:
            columns = []
        else:
            columns = [d[0] for d in cur.description]
            try:
                meta = conn.execute(f"SELECT * FROM ({sql}) LIMIT 0")
                column_types = {d[0]: (d[1] or "") for d in (meta.description or [])}
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

    return SqlExecutionResult(
        columns=columns,
        rows=rows,
        column_sql_types=column_types or {c: "" for c in columns},
        row_count=len(rows),
        truncated=truncated,
        timed_out=timed_out,
        latency_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


def _sqlite_schema(spec: DataSourceSpec, sample_rows: int) -> DatabaseSchema:
    if spec.path is None or not spec.path.exists():
        raise FileNotFoundError(f"SQLite db missing: {spec.path}")
    tables: list[TableSchema] = []
    with sqlite3.connect(f"file:{spec.path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        names = [row["name"] for row in cur.fetchall()]
        for table_name in names:
            cols: list[ColumnSchema] = []
            info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            sample: list[dict[str, Any]] = []
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
    # Collect foreign keys via PRAGMA foreign_key_list per table.
    fks: list[ForeignKey] = []
    with sqlite3.connect(f"file:{spec.path}?mode=ro", uri=True) as conn:
        for t in tables:
            try:
                for row in conn.execute(f'PRAGMA foreign_key_list("{t.name}")').fetchall():
                    # PRAGMA returns: id, seq, table, from, to, on_update, on_delete, match
                    fks.append(ForeignKey(
                        from_table=t.name,
                        from_column=row[3],
                        to_table=row[2],
                        to_column=row[4] or row[3],
                    ))
            except sqlite3.Error:
                pass
    return DatabaseSchema(
        data_source_id=spec.id,
        engine="sqlite",
        tables=tables,
        schema_version=spec.schema_version,
        sqlite_path=spec.path,
        foreign_keys=fks,
    )


# =======================================================================
# DuckDB implementation (lazy-imported; only loaded if engine == duckdb).
# =======================================================================

def _duckdb_execute(spec: DataSourceSpec, sql: str, *, timeout_ms: int,
                    row_limit: int, read_only: bool) -> SqlExecutionResult:
    started = time.monotonic()
    if spec.path is None:
        return _empty_result(started, error="duckdb spec missing path")
    try:
        import duckdb  # type: ignore
    except ImportError as exc:
        return _empty_result(started, error=f"duckdb driver missing: {exc}")
    try:
        # read_only flag tells DuckDB to open the file without locks.
        conn = duckdb.connect(str(spec.path), read_only=read_only)
    except Exception as exc:
        return _empty_result(started, error=f"duckdb open failed: {exc}")
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    column_types: dict[str, str] = {}
    timed_out = False
    truncated = False
    error: str | None = None
    try:
        # DuckDB doesn't have per-statement interrupt; rely on its own
        # interrupt() called from a Timer thread.
        timer = threading.Timer(timeout_ms / 1000.0, conn.interrupt)
        timer.daemon = True
        timer.start()
        try:
            cur = conn.execute(sql)
            if cur.description is None:
                columns = []
            else:
                columns = [d[0] for d in cur.description]
                column_types = {d[0]: str(d[1]) if d[1] else "" for d in cur.description}
            cap = row_limit + 1 if row_limit > 0 else None
            fetched = cur.fetchmany(cap) if cap else cur.fetchall()
            for raw in fetched:
                rows.append({col: _pg_coerce(raw[idx]) for idx, col in enumerate(columns)})
            if cap is not None and len(rows) > row_limit:
                rows = rows[:row_limit]
                truncated = True
        finally:
            timer.cancel()
    except Exception as exc:
        msg = str(exc)
        if "interrupted" in msg.lower() or "INTERRUPT" in msg:
            timed_out = True
        else:
            error = msg
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return SqlExecutionResult(
        columns=columns,
        rows=rows,
        column_sql_types=column_types or {c: "" for c in columns},
        row_count=len(rows),
        truncated=truncated,
        timed_out=timed_out,
        latency_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


def _duckdb_schema(spec: DataSourceSpec, sample_rows: int) -> DatabaseSchema:
    if spec.path is None or not spec.path.exists():
        raise FileNotFoundError(f"DuckDB file missing: {spec.path}")
    import duckdb  # type: ignore
    tables: list[TableSchema] = []
    conn = duckdb.connect(str(spec.path), read_only=True)
    try:
        # Restrict to schema 'main' — DuckDB's default search_path resolves
        # unqualified names there, and dbt staging schemas (main_stg_*,
        # main_int_*) are pollution we don't want to expose to the model.
        rows = conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' "
            "ORDER BY table_name"
        ).fetchall()
        def _is_demo_table(sch: str, tbl: str) -> bool:
            low = tbl.lower()
            if low.endswith("_tmp"):
                return False
            if low.startswith("stg_") or low.startswith("int_"):
                return False
            if "bridge_smoke" in low:
                return False
            return True
        rows = [(s, t) for s, t in rows if _is_demo_table(s, t)]
        for sch, table_name in rows:
            # Unqualified — DuckDB resolves "main" from default search_path.
            # If we render "main.table_name" the model double-quotes the
            # whole thing and DuckDB treats it as a single identifier.
            qualified = f'"{table_name}"'
            try:
                info = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            except Exception:
                try:
                    info = conn.execute(f"DESCRIBE {qualified}").fetchall()
                except Exception:
                    info = []
            sample: list[dict[str, Any]] = []
            try:
                desc = conn.execute(f"SELECT * FROM {qualified} LIMIT {sample_rows}")
                cols_desc = [d[0] for d in desc.description]
                sample = [dict(zip(cols_desc, r)) for r in desc.fetchall()]
            except Exception:
                sample = []
            cols: list[ColumnSchema] = []
            # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
            # DESCRIBE: column_name, column_type, null, key, default, extra
            for row in info:
                if len(row) >= 6 and isinstance(row[3], int):
                    # Looks like PRAGMA table_info layout
                    col_name = row[1]
                    sql_type = row[2] or ""
                    nullable = not row[3]
                    primary_key = bool(row[5])
                else:
                    col_name = row[0]
                    sql_type = row[1] or ""
                    nullable = (row[2] != "NO" and str(row[2]).upper() != "FALSE")
                    primary_key = False
                examples = [r.get(col_name) for r in sample if r.get(col_name) is not None]
                cols.append(
                    ColumnSchema(
                        name=col_name,
                        sql_type=sql_type,
                        nullable=nullable,
                        primary_key=primary_key,
                        examples=examples[:3],
                    )
                )
            # Bare table name — schema is implicit via DuckDB search_path.
            tables.append(TableSchema(name=table_name, columns=cols))
    finally:
        conn.close()
    # DuckDB (and dbt-built DBs) rarely declare FK constraints. Infer
    # them heuristically: any column named "<X>_id" is assumed to point
    # at table X.id (or X_data.id, X_table.id common dbt suffixes).
    table_pk_by_name: dict[str, tuple[str, str]] = {}
    for t in tables:
        # treat any column named "id" as the PK of t for FK-target purposes
        if any(c.name.lower() == "id" for c in t.columns):
            # multiple keys: foo_data → foo, foo_table → foo, raw → raw
            base = t.name.lower()
            for suffix in ("_data", "_table"):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
                    break
            table_pk_by_name[base] = (t.name, "id")
    fks: list[ForeignKey] = []
    for t in tables:
        for c in t.columns:
            cn = c.name.lower()
            if not cn.endswith("_id") or cn == "id":
                continue
            target_base = cn[:-3]
            if target_base in table_pk_by_name:
                tt, tc = table_pk_by_name[target_base]
                if tt != t.name:  # don't self-FK
                    fks.append(ForeignKey(
                        from_table=t.name, from_column=c.name,
                        to_table=tt, to_column=tc,
                    ))
    return DatabaseSchema(
        data_source_id=spec.id,
        engine="duckdb",
        tables=tables,
        schema_version=spec.schema_version,
        foreign_keys=fks,
    )


# =======================================================================
# PostgreSQL implementation.
# =======================================================================

def _pg_execute(spec: DataSourceSpec, sql: str, *, timeout_ms: int,
                row_limit: int, read_only: bool) -> SqlExecutionResult:
    started = time.monotonic()
    if not spec.dsn:
        return _empty_result(started, error="postgres spec missing dsn")
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError as exc:
        return _empty_result(started, error=f"psycopg2 driver missing: {exc}")
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    column_types: dict[str, str] = {}
    timed_out = False
    truncated = False
    error: str | None = None
    try:
        conn = psycopg2.connect(spec.dsn, connect_timeout=max(1, int(timeout_ms / 1000)))
    except Exception as exc:
        return _empty_result(started, error=f"pg connect failed: {exc}")
    try:
        if read_only:
            conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
            cur.execute(sql)
            if cur.description is None:
                columns = []
            else:
                columns = [d.name for d in cur.description]
                # Map oid -> type name via pg_type for nicer column_sql_types.
                # Cheap heuristic: use string of type_code (int oid). Frontend
                # mostly needs INTEGER/TEXT/REAL bucketing — psycopg2's
                # type code OIDs map well enough.
                column_types = {d.name: _pg_oid_to_name(d.type_code) for d in cur.description}
            cap = row_limit + 1 if row_limit > 0 else None
            fetched = cur.fetchmany(cap) if cap else cur.fetchall()
            for raw in fetched:
                rows.append({col: _pg_coerce(raw[idx]) for idx, col in enumerate(columns)})
            if cap is not None and len(rows) > row_limit:
                rows = rows[:row_limit]
                truncated = True
    except Exception as exc:
        msg = str(exc)
        if "statement timeout" in msg.lower() or "canceling statement" in msg.lower():
            timed_out = True
        else:
            error = msg
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return SqlExecutionResult(
        columns=columns,
        rows=rows,
        column_sql_types=column_types or {c: "" for c in columns},
        row_count=len(rows),
        truncated=truncated,
        timed_out=timed_out,
        latency_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


def _pg_coerce(v: Any) -> Any:
    """Postgres types that don't JSON-serialize out of the box."""
    if v is None:
        return None
    # decimal.Decimal — common for NUMERIC columns
    try:
        import decimal
        if isinstance(v, decimal.Decimal):
            # Preserve precision-friendly float; UI's NumberFormat handles it.
            return float(v)
    except ImportError:
        pass
    # date / datetime → ISO string (UI's table formatter handles strings).
    try:
        import datetime as _dt
        if isinstance(v, (_dt.date, _dt.datetime, _dt.time)):
            return v.isoformat()
    except ImportError:
        pass
    return v


_PG_OID_NAMES = {
    16: "BOOLEAN",
    20: "BIGINT",
    21: "SMALLINT",
    23: "INTEGER",
    25: "TEXT",
    700: "REAL",
    701: "DOUBLE PRECISION",
    1042: "CHARACTER",
    1043: "VARCHAR",
    1082: "DATE",
    1114: "TIMESTAMP",
    1184: "TIMESTAMPTZ",
    1700: "NUMERIC",
}


def _pg_oid_to_name(oid: int) -> str:
    return _PG_OID_NAMES.get(oid, f"oid_{oid}")


def _pg_schema(spec: DataSourceSpec, sample_rows: int) -> DatabaseSchema:
    if not spec.dsn:
        raise FileNotFoundError(f"postgres dsn missing for {spec.id}")
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore
    conn = psycopg2.connect(spec.dsn, connect_timeout=5)
    tables: list[TableSchema] = []
    try:
        conn.set_session(readonly=True, autocommit=True)
        schemas_list = list(spec.pg_schemas or ("public",))
        placeholders = ",".join(["%s"] * len(schemas_list))
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema IN ({placeholders})
                  AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name
                """,
                schemas_list,
            )
            table_rows = cur.fetchall()
        for sch, tbl in table_rows:
            cols: list[ColumnSchema] = []
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (sch, tbl),
                )
                col_rows = cur.fetchall()
            # Primary keys
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = (%s || '.' || %s)::regclass AND i.indisprimary
                    """,
                    (sch, tbl),
                )
                pk_names = {r[0] for r in cur.fetchall()}
            sample_data: list[dict[str, Any]] = []
            try:
                with conn.cursor() as cur:
                    cur.execute(f'SELECT * FROM "{sch}"."{tbl}" LIMIT %s', (sample_rows,))
                    col_names = [d.name for d in cur.description]
                    sample_data = [dict(zip(col_names, r)) for r in cur.fetchall()]
            except Exception:
                sample_data = []
            for col_name, data_type, is_nullable in col_rows:
                examples = [r.get(col_name) for r in sample_data if r.get(col_name) is not None]
                cols.append(
                    ColumnSchema(
                        name=col_name,
                        sql_type=(data_type or "").upper(),
                        nullable=(is_nullable == "YES"),
                        primary_key=col_name in pk_names,
                        examples=examples[:3],
                    )
                )
            # Use plain table name (no schema prefix) for prompt simplicity.
            tables.append(TableSchema(name=tbl, columns=cols))
        # FK collection — use pg_catalog (information_schema's
        # constraint_column_usage is GRANT-gated; a read-only role sees
        # empty results even when constraints exist).
        fks: list[ForeignKey] = []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ns.nspname || '.' || cls_from.relname AS from_qualified,
                    cls_from.relname AS from_table,
                    a_from.attname AS from_column,
                    cls_to.relname AS to_table,
                    a_to.attname AS to_column
                FROM pg_constraint c
                JOIN pg_class cls_from ON cls_from.oid = c.conrelid
                JOIN pg_class cls_to   ON cls_to.oid   = c.confrelid
                JOIN pg_namespace ns   ON ns.oid       = cls_from.relnamespace
                JOIN unnest(c.conkey)  WITH ORDINALITY AS f(attnum, ord) ON true
                JOIN unnest(c.confkey) WITH ORDINALITY AS t(attnum, ord) ON t.ord = f.ord
                JOIN pg_attribute a_from ON a_from.attrelid = c.conrelid  AND a_from.attnum = f.attnum
                JOIN pg_attribute a_to   ON a_to.attrelid   = c.confrelid AND a_to.attnum   = t.attnum
                WHERE c.contype = 'f'
                  AND ns.nspname = ANY(%s)
                ORDER BY cls_from.relname, a_from.attname
                """,
                [list(schemas_list)],
            )
            for _, ft, fc, tt, tc in cur.fetchall():
                fks.append(ForeignKey(
                    from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                ))
    finally:
        conn.close()
    return DatabaseSchema(
        data_source_id=spec.id,
        engine="postgres",
        tables=tables,
        schema_version=spec.schema_version,
        foreign_keys=fks,
    )


# =======================================================================
# Dispatch
# =======================================================================

def _empty_result(started: float, *, error: str) -> SqlExecutionResult:
    return SqlExecutionResult(
        columns=[],
        rows=[],
        column_sql_types={},
        row_count=0,
        truncated=False,
        timed_out=False,
        latency_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


def execute_select(spec: DataSourceSpec, sql: str, *, timeout_ms: int,
                   row_limit: int, read_only: bool = True) -> SqlExecutionResult:
    engine = spec.engine or "sqlite"
    if engine == "sqlite":
        return _sqlite_execute(spec, sql, timeout_ms=timeout_ms,
                               row_limit=row_limit, read_only=read_only)
    if engine == "duckdb":
        return _duckdb_execute(spec, sql, timeout_ms=timeout_ms,
                               row_limit=row_limit, read_only=read_only)
    if engine == "postgres":
        return _pg_execute(spec, sql, timeout_ms=timeout_ms,
                           row_limit=row_limit, read_only=read_only)
    return _empty_result(time.monotonic(), error=f"unknown engine: {engine}")


def load_schema(spec: DataSourceSpec, sample_rows: int = 3) -> DatabaseSchema:
    engine = spec.engine or "sqlite"
    if engine == "sqlite":
        return _sqlite_schema(spec, sample_rows)
    if engine == "duckdb":
        return _duckdb_schema(spec, sample_rows)
    if engine == "postgres":
        return _pg_schema(spec, sample_rows)
    raise ValueError(f"unknown engine: {engine}")
