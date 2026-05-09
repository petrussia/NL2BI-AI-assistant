"""build_model_prompt_v2.py — improved-grounding + diff-friendly prompt
builder for Spider2-DBT (ablation study).

Variants supported:
  --variant v1   baseline (same as build_model_prompt.py; kept for parity)
  --variant v2   v2 grounding: include staging models + final-model column
                 lists + naming-convention hints
  --variant v4   diff-form: tells the model to extend an existing model
                 via unified diff if the question fits one of them

Saves to:
  data/spider2_dbt/tasks/<TASK_ID>/prompt_<variant>.txt

Does NOT leak gold SQL or gold table names: only enumerates files that
already exist in the upstream example dir.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'spider2_dbt_bridge'))

from ssh_utils import load_config, local_task_path


_DBT_RULES_BASE = textwrap.dedent('''
RULES:
- The dbt project runs on DuckDB 1.5 via dbt-duckdb 1.10.
- Use Standard SQL with DuckDB extensions (UNNEST works; LATERAL FLATTEN
  is NOT DuckDB syntax). Use `LIST_VALUE`, `STRUCT`, `JSON_EXTRACT`, etc.
  for nested types.
- Every dbt model is materialized as table by default.
- Reference upstream sources/models with `{{ ref('name') }}` or
  `{{ source('schema', 'table') }}`. Do not write raw schema-qualified
  table names unless dbt sources are not declared.
''').strip()


_OUTPUT_RULES_V1 = textwrap.dedent('''
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


_OUTPUT_RULES_V2 = textwrap.dedent('''
- The project already has models. Your goal is to MATCH THE PROJECT'S
  NAMING AND COLUMN CONVENTIONS — examine the existing model files in
  the SCHEMA to infer the right output identifier.
- Output: emit ONE answer in EITHER form, picking whichever fits:
    A) A SQL block for a NEW dbt model that matches the project's
       naming convention:
       ```sql path=models/<choose_a_name_consistent_with_existing_models>.sql
       SELECT ...
       ```
    B) A unified diff if your answer is best expressed as a small change
       to an existing model file shown in PROJECT FILES below:
       ```diff
       --- a/models/<existing_file>.sql
       +++ b/models/<existing_file>.sql
       @@ ...
       ```
- Use ONLY columns that appear in the PROJECT FILES. Do not invent
  column names.
- DO NOT explain. ONE fenced block, nothing else.
''').strip()


_OUTPUT_RULES_V4 = textwrap.dedent('''
- The dbt project already has models that may partially solve the task.
  Prefer **extending an existing model** via a unified diff over creating
  a brand-new file.
- Output: emit ONE answer in this priority order:
    1) FIRST CHOICE — unified diff that extends an existing model file
       listed in PROJECT FILES:
       ```diff
       --- a/models/<existing_file>.sql
       +++ b/models/<existing_file>.sql
       @@ ...
       ```
    2) Only if no existing model fits, write a new SQL file:
       ```sql path=models/<name>.sql
       SELECT ...
       ```
- Use ONLY columns visible in the PROJECT FILES. Do not invent names.
- DO NOT explain. ONE fenced block, nothing else.
''').strip()


def _render_schema(duck_tables: dict, *, max_chars: int = 5000) -> str:
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


def _classify_model_path(rel: str) -> str:
    p = rel.lower()
    if '/staging/' in p or '/stg_' in p or rel.lower().startswith('models/staging/'):
        return 'staging'
    if '/intermediate/' in p or '/int_' in p:
        return 'intermediate'
    if rel.endswith('.yml') or rel.endswith('.yaml'):
        return 'config'
    return 'final'


def _render_project_files_v1(task_files_dir: Path, *, max_chars: int = 6000) -> str:
    """Baseline: paths + first lines."""
    if not task_files_dir.exists():
        return '(no project files snapshotted)'
    paths = sorted(p for p in task_files_dir.rglob('*') if p.is_file())
    out = ['PROJECT FILES (paths + first lines):']
    used = 0
    for p in paths:
        rel = p.relative_to(task_files_dir).as_posix()
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        if rel.endswith('dbt_project.yml') or rel.endswith('schema.yml') or \
                rel.startswith('models/'):
            block = f'\n--- {rel} ---\n{text[:1200]}\n'
        else:
            head = '\n'.join(text.splitlines()[:6])
            block = f'\n--- {rel} ---\n{head}\n'
        if used + len(block) > max_chars: break
        out.append(block); used += len(block)
    return '\n'.join(out)


def _render_project_files_v2(task_files_dir: Path, *, max_chars: int = 9000) -> str:
    """Improved: group models by class (staging/intermediate/final), list
    column names from each model SQL via simple regex.
    """
    if not task_files_dir.exists():
        return '(no project files snapshotted)'

    paths = sorted(p for p in task_files_dir.rglob('*') if p.is_file())
    by_class: dict[str, list[tuple[str, str]]] = {
        'staging': [], 'intermediate': [], 'final': [], 'config': [], 'other': []
    }
    project_yml = ''
    for p in paths:
        rel = p.relative_to(task_files_dir).as_posix()
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        cls = _classify_model_path(rel) if rel.endswith('.sql') else (
            'config' if rel.endswith(('.yml', '.yaml')) else 'other')
        by_class[cls].append((rel, text))
        if rel.endswith('dbt_project.yml'):
            project_yml = text

    out: list[str] = ['PROJECT FILES (grouped by class):']
    used = 0

    if project_yml:
        block = f'\n[dbt_project.yml]\n{project_yml[:600]}\n'
        out.append(block); used += len(block)

    for cls in ('staging', 'intermediate', 'final'):
        items = by_class.get(cls, [])
        if not items: continue
        out.append(f'\n=== {cls.upper()} models ({len(items)}) ===')
        for rel, text in items:
            # Extract column names from final SELECT or CTEs
            col_names = _extract_column_names(text)
            head_5 = '\n'.join(text.splitlines()[:5])
            block = f'  - {rel}'
            if col_names:
                block += f'\n    cols: {", ".join(col_names[:18])}'
                if len(col_names) > 18:
                    block += f', ...({len(col_names)} total)'
            if cls == 'final':
                # Show full body (capped) for final models — these are most
                # likely to be reused / extended
                trimmed = text[:900]
                block += f'\n    --- body (first 900 chars):\n    ' + trimmed.replace(
                    '\n', '\n    ')
            else:
                block += f'\n    --- head:\n    ' + head_5.replace('\n', '\n    ')
            if used + len(block) > max_chars: break
            out.append(block); used += len(block)
        if used > max_chars: break

    # Configs (yml schema files) — show only the model_name → column_name pairs
    if 'config' in by_class:
        for rel, text in by_class['config']:
            if 'columns:' in text or 'name:' in text:
                head = text[:500]
                block = f'\n--- {rel} (head) ---\n{head}\n'
                if used + len(block) > max_chars: break
                out.append(block); used += len(block)

    return '\n'.join(out)


_COL_RE = re.compile(r'(?im)^\s*(?:select|,)?\s*([a-zA-Z_][\w]*)\s*(?:as\s+([a-zA-Z_][\w]*))?')
_AS_RE = re.compile(r'(?i)\bas\s+([a-zA-Z_][\w]*)\b')


def _extract_column_names(sql: str) -> list[str]:
    """Best-effort: pull column aliases / final SELECT names. Lossy but
    useful for grounding."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _AS_RE.finditer(sql):
        nm = m.group(1)
        if nm.lower() in ('select', 'from', 'where', 'group', 'order',
                            'having', 'limit', 'true', 'false', 'null'):
            continue
        if nm not in seen:
            seen.add(nm); out.append(nm)
    return out[:30]


def build_v1_prompt(question: str, schema_block: str, files_block: str) -> str:
    return textwrap.dedent(f'''
        You are a senior analytics engineer. You will modify or create a
        dbt model so that running `dbt run` and `dbt test` in the project
        directory produces the answer to the user's question.

        TASK:
        QUESTION:
        {question.strip()}

        {_DBT_RULES_BASE}

        {_OUTPUT_RULES_V1}

        {schema_block}

        {files_block}

        Now emit ONE fenced block (SQL or diff) that solves the task.
        SQL or DIFF:
    ''').strip()


def build_v2_prompt(question: str, schema_block: str, files_block: str) -> str:
    return textwrap.dedent(f'''
        You are a senior analytics engineer. You will modify or create one
        or more dbt models so that running `dbt run` produces the answer.

        QUESTION:
        {question.strip()}

        {_DBT_RULES_BASE}

        {_OUTPUT_RULES_V2}

        {schema_block}

        {files_block}

        Examine the PROJECT FILES carefully — the existing models reveal
        the project's naming convention (e.g. `<source>__<entity>` final
        models, `stg_<source>__<table>` staging models). Use a name that
        fits this pattern and reuse the staging models with `{{{{ ref(...) }}}}`.

        SQL or DIFF (one fenced block, nothing else):
    ''').strip()


def build_v4_prompt(question: str, schema_block: str, files_block: str) -> str:
    return textwrap.dedent(f'''
        You are a senior analytics engineer extending a dbt project so that
        running `dbt run` produces the answer to the user's question.

        QUESTION:
        {question.strip()}

        {_DBT_RULES_BASE}

        {_OUTPUT_RULES_V4}

        {schema_block}

        {files_block}

        REMEMBER: prefer extending an existing final model via a unified
        diff over writing a new file. Keep changes minimal — small,
        focused additions are easier to validate.

        DIFF (or SQL fallback) — one fenced block, nothing else:
    ''').strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--variant', default='v2', choices=['v1', 'v2', 'v4'])
    ap.add_argument('--config', default=None)
    ap.add_argument('--max-prompt-chars', type=int, default=14000)
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    ctx_dir = local_task_path(cfg, iid) / 'context'
    ctx_path = ctx_dir / 'context.json'
    if not ctx_path.exists():
        print(f'FAIL: missing {ctx_path}. Run export_task_context.py first.'); return 2
    ctx = json.loads(ctx_path.read_text(encoding='utf-8'))
    duck = {}
    if (ctx_dir / 'duckdb_tables.json').exists():
        duck = json.loads((ctx_dir / 'duckdb_tables.json').read_text(encoding='utf-8'))

    schema_block = _render_schema(duck)
    if args.variant == 'v1':
        files_block = _render_project_files_v1(ctx_dir / 'task_files')
        prompt = build_v1_prompt(ctx.get('instruction', ''), schema_block, files_block)
    elif args.variant == 'v2':
        files_block = _render_project_files_v2(ctx_dir / 'task_files')
        prompt = build_v2_prompt(ctx.get('instruction', ''), schema_block, files_block)
    else:  # v4
        files_block = _render_project_files_v2(ctx_dir / 'task_files')
        prompt = build_v4_prompt(ctx.get('instruction', ''), schema_block, files_block)

    if len(prompt) > args.max_prompt_chars:
        prompt = prompt[: args.max_prompt_chars] + '\n... (truncated)'

    out_path = local_task_path(cfg, iid) / f'prompt_{args.variant}.txt'
    out_path.write_text(prompt, encoding='utf-8')
    print(f'WROTE {out_path} ({len(prompt)} chars, variant={args.variant})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
