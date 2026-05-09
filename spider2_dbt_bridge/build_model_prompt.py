"""build_model_prompt.py — assemble a model-ready prompt for one task.

Input: data/spider2_dbt/tasks/<TASK_ID>/context/{context.json,duckdb_tables.json,task_files/}
Output: data/spider2_dbt/tasks/<TASK_ID>/prompt.txt

The prompt format:
  - HEADER with task instruction + work-dir hint + dbt rules
  - SCHEMA section listing all DuckDB tables/columns (truncated to budget)
  - PROJECT section listing relevant existing dbt files (paths + first lines)
  - TASK directive: explicit single-shot instructions ('emit one fenced
    block with the SQL for the *expected output model*' OR 'emit a unified
    diff against the listed files')

No gold SQL or expected-result rows are exposed.
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from ssh_utils import load_config, local_task_path


_DBT_RULES = textwrap.dedent('''
RULES:
- The dbt project runs on DuckDB 1.5 via dbt-duckdb 1.10.
- Use Standard SQL with DuckDB extensions (UNNEST works; LATERAL FLATTEN
  is NOT DuckDB syntax). Use `LIST_VALUE`, `STRUCT`, `JSON_EXTRACT`, etc.
  for nested types.
- Every dbt model is materialized as table by default.
- Reference upstream sources/models with `{{ ref('name') }}` or
  `{{ source('schema', 'table') }}`. Do not write raw schema-qualified
  table names unless dbt sources are not declared.
- Output: emit ONE answer in either of two forms (pick the simpler that
  solves the task):
    A) A complete SQL block intended as a new dbt model file. Wrap with
       a fenced code block and the path comment, e.g.:
       ```sql path=models/output.sql
       SELECT ...
       ```
    B) A unified diff against existing files in the snapshot. Wrap with:
       ```diff
       --- a/models/x.sql
       +++ b/models/x.sql
       @@ ...
       ...
       ```
- DO NOT explain. DO NOT include extra prose. ONE fenced block.
''').strip()


def _render_schema(duck_tables: dict, *, max_chars: int = 6000) -> str:
    if not duck_tables: return '(no DuckDB schema available)'
    out: list[str] = ['SCHEMA (DuckDB tables visible to the dbt project):']
    used = 0
    for db_path, tables in duck_tables.items():
        if isinstance(tables, dict) and 'error' in tables:
            line = f'- `{db_path}`: ERROR ({tables["error"]})'
            if used + len(line) > max_chars: break
            out.append(line); used += len(line); continue
        out.append(f'- `{db_path}`')
        for t in tables[:30]:
            cols = ', '.join(f'{c["name"]} {c["type"]}' for c in t.get('columns', [])[:30])
            line = f'    {t["schema"]}.{t["table"]}({cols})'
            if used + len(line) > max_chars: break
            out.append(line); used += len(line)
        if used > max_chars: break
    return '\n'.join(out)


def _render_project_files(task_files_dir: Path, *,
                            include_full: list[str] | None = None,
                            max_chars: int = 6000) -> str:
    if not task_files_dir.exists():
        return '(no project files snapshotted)'
    paths = sorted(p for p in task_files_dir.rglob('*') if p.is_file())
    out = ['PROJECT FILES (paths + first lines):']
    used = 0
    include = set(include_full or [])
    for p in paths:
        rel = p.relative_to(task_files_dir).as_posix()
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        if rel in include or rel.endswith('dbt_project.yml') or \
                rel.endswith('schema.yml') or rel.startswith('models/'):
            block = f'\n--- {rel} ---\n{text[:1200]}\n'
        else:
            head = '\n'.join(text.splitlines()[:6])
            block = f'\n--- {rel} ---\n{head}\n'
        if used + len(block) > max_chars: break
        out.append(block); used += len(block)
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--config', default=None)
    ap.add_argument('--max-prompt-chars', type=int, default=14000)
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    ctx_dir = local_task_path(cfg, iid) / 'context'
    if not (ctx_dir / 'context.json').exists():
        print(f'FAIL: missing context. Run export_task_context.py first.')
        return 2

    ctx = json.loads((ctx_dir / 'context.json').read_text(encoding='utf-8'))
    duck = {}
    if (ctx_dir / 'duckdb_tables.json').exists():
        duck = json.loads((ctx_dir / 'duckdb_tables.json').read_text(encoding='utf-8'))

    schema_block = _render_schema(duck)
    files_block = _render_project_files(ctx_dir / 'task_files')

    prompt = textwrap.dedent(f'''
        You are a senior analytics engineer. You will modify or create a
        dbt model so that running `dbt run` and `dbt test` in the project
        directory produces the answer to the user's question.

        TASK ID: {iid}
        QUESTION:
        {ctx.get('instruction', '').strip()}

        {_DBT_RULES}

        {schema_block}

        {files_block}

        Now emit ONE fenced block (SQL or diff form) that solves the task.
        SQL or DIFF:
    ''').strip()

    if len(prompt) > args.max_prompt_chars:
        prompt = prompt[: args.max_prompt_chars] + '\n... (truncated for prompt budget)'

    out_path = local_task_path(cfg, iid) / 'prompt.txt'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt, encoding='utf-8')
    print(f'WROTE: {out_path} ({len(prompt)} chars)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
