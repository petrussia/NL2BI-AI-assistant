#!/usr/bin/env python3
"""probe_duckdb.py — list tables/columns in all .duckdb files under a dir.
Usage: probe_duckdb.py <example_dir>"""
import json
import os
import sys
import glob


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: probe_duckdb.py <example_dir>'); return 2
    d = sys.argv[1]
    os.chdir(d)
    try:
        import duckdb
    except ImportError:
        print('{}'); return 0
    out = {}
    for db in sorted(glob.glob('*.duckdb') + glob.glob('*/*.duckdb')):
        try:
            con = duckdb.connect(db, read_only=True)
            tables = con.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema','pg_catalog') "
                "ORDER BY 1,2"
            ).fetchall()
            per = []
            for sch, t in tables:
                cols = con.execute(
                    f"SELECT column_name, data_type FROM information_schema.columns "
                    f"WHERE table_schema = '{sch}' AND table_name = '{t}' "
                    f"ORDER BY ordinal_position"
                ).fetchall()
                per.append({'schema': sch, 'table': t,
                              'columns': [{'name': c[0], 'type': c[1]} for c in cols]})
            out[db] = per
            con.close()
        except Exception as e:
            out[db] = {'error': f'{type(e).__name__}:{str(e)[:120]}'}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
