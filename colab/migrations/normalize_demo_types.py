"""Rebuild Spider demo SQLite tables with proper INTEGER types where the
original Spider corpus declared year/FK columns as TEXT.

Idempotent: skips tables already at the target type. Runs inside Colab via
the agent bridge; can also be run locally pointing at any spider DB tree.
"""
import sqlite3, sys
from pathlib import Path

# Map of (db_name, table, column) -> target SQL type.
# Year columns: TEXT '2014' -> INTEGER 2014.
# FK columns that reference INT PKs but are themselves TEXT.
MIGRATIONS = [
    ("concert_singer", "concert",            "Year",        "INTEGER"),
    ("concert_singer", "concert",            "Stadium_ID",  "INTEGER"),
    ("concert_singer", "singer",             "Song_release_year", "INTEGER"),
    ("concert_singer", "singer_in_concert",  "Singer_ID",   "INTEGER"),
    ("wrestler",       "Elimination",        "Wrestler_ID", "INTEGER"),
]


def _table_ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row:
        raise RuntimeError(f"table {table!r} not found")
    return row[0]


def _patch_column_type(ddl: str, column: str, new_type: str) -> str:
    """Replace the type for a single column in a CREATE TABLE statement.

    We deliberately avoid sqlparse — Spider DDL is simple enough that a
    line-by-line rewrite is reliable and visible in diffs.
    """
    out_lines = []
    matched = False
    for line in ddl.splitlines():
        stripped = line.strip().rstrip(",")
        # column declarations look like:  "Year"  TEXT,   or:  Year TEXT NOT NULL,
        for quoted in (f'"{column}"', f"`{column}`", f"[{column}]", column):
            head = stripped.split(maxsplit=1)
            if head and head[0].strip('"`[]') == column:
                # Replace the first whitespace-token after the name with new_type.
                rest = head[1] if len(head) > 1 else ""
                rest_parts = rest.split(maxsplit=1)
                tail = rest_parts[1] if len(rest_parts) > 1 else ""
                rebuilt = f"{head[0]} {new_type} {tail}".rstrip()
                indent = line[: len(line) - len(line.lstrip())]
                end = "," if line.rstrip().endswith(",") else ""
                out_lines.append(f"{indent}{rebuilt}{end}")
                matched = True
                break
        else:
            out_lines.append(line)
            continue
    if not matched:
        raise RuntimeError(f"column {column!r} not found in DDL: {ddl!r}")
    return "\n".join(out_lines)


def _column_type(conn: sqlite3.Connection, table: str, column: str) -> str:
    for _, name, typ, *_ in conn.execute(f"PRAGMA table_info({table})"):
        if name == column:
            return (typ or "").upper()
    raise RuntimeError(f"column {column!r} not on {table!r}")


def migrate_db(db_path: Path, items: list[tuple[str, str, str]]) -> dict[str, str]:
    """items = [(table, column, new_type)]. Returns a status report per item."""
    report: dict[str, str] = {}
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for table, column, new_type in items:
            key = f"{table}.{column}"
            current = _column_type(conn, table, column)
            if current == new_type.upper():
                report[key] = f"skip (already {current})"
                continue
            old_ddl = _table_ddl(conn, table)
            new_ddl = _patch_column_type(old_ddl, column, new_type)
            tmp_table = f"_migrate_{table}"
            new_ddl = new_ddl.replace(
                f"CREATE TABLE {table}", f"CREATE TABLE {tmp_table}", 1
            ).replace(
                f'CREATE TABLE "{table}"', f'CREATE TABLE "{tmp_table}"', 1
            )
            cur = conn.cursor()
            cur.execute("BEGIN")
            cur.execute(new_ddl)
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            select_exprs = [
                f"CAST({c} AS {new_type})" if c == column else c for c in cols
            ]
            col_list = ", ".join(cols)
            cur.execute(
                f"INSERT INTO {tmp_table} ({col_list}) SELECT {', '.join(select_exprs)} FROM {table}"
            )
            cur.execute(f"DROP TABLE {table}")
            cur.execute(f"ALTER TABLE {tmp_table} RENAME TO {table}")
            cur.execute("COMMIT")
            report[key] = f"migrated {current} -> {new_type}"
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()
    return report


def run(root: str) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for db, t, c, ty in MIGRATIONS:
        grouped.setdefault(db, []).append((t, c, ty))
    out: dict[str, dict[str, str]] = {}
    for db, items in grouped.items():
        path = Path(root) / db / f"{db}.sqlite"
        if not path.exists():
            out[db] = {"_error": f"missing {path}"}
            continue
        out[db] = migrate_db(path, items)
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/content/spider_db/spider_data/database"
    import json
    print(json.dumps(run(root), ensure_ascii=False, indent=2))
