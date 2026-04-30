# Stage 6: postprocess.py + analytics handoff design + examples.

import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
EVAL = REPO / 'src' / 'evaluation'
EVAL.mkdir(parents=True, exist_ok=True)
ts = dt.datetime.now(dt.timezone.utc).isoformat()

# ===== postprocess.py module =====
postprocess_src = '''"""Post-processing + analytics handoff layer for the NL2SQL pipeline.

Closes ТЗ items 2.2.5 (предварительная обработка и агрегация результатов)
and 2.2.6 (передача результатов в подсистему аналитического представления).

The full pipeline shape is:
  question -> (B0/B1/B2/B3/B4) -> generated SQL -> SQLite execution -> result rows
  -> normalize_rows (this module)
  -> compute_summary (this module)
  -> build_analytics_payload (this module)
  -> handoff to reporting subsystem (JSON or CSV file in a known location)

The handoff contract is intentionally simple and JSON-first so that any
analytical/reporting subsystem (BI dashboard, Jupyter notebook, downstream
script, etc.) can consume it without ad-hoc parsing.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from collections import Counter
from typing import Any, Sequence


def normalize_rows(rows: Sequence[Sequence[Any]], column_names: Sequence[str] | None = None) -> list[dict]:
    """Convert a row-tuple list to a list of dicts.

    - If `column_names` is provided, dict keys come from there.
    - Otherwise, keys are c0, c1, ... derived from positions.
    - Numeric strings are coerced to int/float when unambiguous.
    - None remains None.
    """
    if not rows:
        return []
    n_cols = max(len(r) for r in rows)
    if column_names is None:
        column_names = [f"c{i}" for i in range(n_cols)]
    elif len(column_names) < n_cols:
        column_names = list(column_names) + [f"c{i}" for i in range(len(column_names), n_cols)]

    def _coerce(v):
        if v is None or isinstance(v, (int, float, bool)):
            return v
        if isinstance(v, (bytes, bytearray)):
            try: return v.decode("utf-8", errors="replace")
            except Exception: return str(v)
        s = str(v).strip()
        if s == "": return s
        try: return int(s)
        except ValueError: pass
        try: return float(s)
        except ValueError: pass
        return s

    out = []
    for r in rows:
        d = {}
        for i in range(n_cols):
            d[column_names[i]] = _coerce(r[i]) if i < len(r) else None
        out.append(d)
    return out


def compute_summary(rows: list[dict]) -> dict:
    """Per-column descriptive summary (count / distinct / min / max / sum for numeric, top values for categorical)."""
    if not rows:
        return {"row_count": 0, "columns": {}}
    cols = {}
    sample_keys = list(rows[0].keys())
    for k in sample_keys:
        vals = [r.get(k) for r in rows]
        non_null = [v for v in vals if v is not None]
        nums = [v for v in non_null if isinstance(v, (int, float)) and not isinstance(v, bool)]
        col_summary = {
            "count": len(non_null),
            "null_count": sum(1 for v in vals if v is None),
            "distinct_count": len(set(non_null)),
        }
        if nums and len(nums) == len(non_null):
            col_summary["dtype"] = "numeric"
            col_summary["min"] = min(nums)
            col_summary["max"] = max(nums)
            col_summary["sum"] = sum(nums)
            col_summary["mean"] = sum(nums) / len(nums)
        else:
            col_summary["dtype"] = "categorical_or_mixed"
            col_summary["top"] = Counter(str(v) for v in non_null).most_common(5)
        cols[k] = col_summary
    return {"row_count": len(rows), "columns": cols}


def build_analytics_payload(
    *, question: str, db_id: str, generated_sql: str, gold_sql: str | None,
    rows: Sequence[Sequence[Any]], column_names: Sequence[str] | None = None,
    baseline: str = "", model: str = "", subset: str = "", idx: int | None = None,
) -> dict:
    """Build the analytics-handoff payload.

    Schema of the payload (handoff contract):
    {
      "schema_version": "v1",
      "produced_at": ISO8601 UTC,
      "source": {"baseline": str, "model": str, "subset": str, "idx": int|None,
                 "db_id": str, "question": str, "generated_sql": str,
                 "gold_sql_present": bool},
      "rows": [{...}, ...],          # normalized
      "summary": {"row_count": int, "columns": {col: {...}}},
      "n_rows": int,
      "is_executable": bool,
      "notes": []
    }
    """
    norm = normalize_rows(rows, column_names=column_names)
    summary = compute_summary(norm)
    return {
        "schema_version": "v1",
        "produced_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {
            "baseline": baseline, "model": model, "subset": subset, "idx": idx,
            "db_id": db_id, "question": question, "generated_sql": generated_sql,
            "gold_sql_present": gold_sql is not None,
        },
        "rows": norm,
        "summary": summary,
        "n_rows": summary["row_count"],
        "is_executable": True,
        "notes": [],
    }


def export_payload_json(payload: dict, target_dir, basename: str) -> str:
    from pathlib import Path as _P
    target_dir = _P(target_dir); target_dir.mkdir(parents=True, exist_ok=True)
    p = target_dir / f"{basename}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def export_payload_csv(payload: dict, target_dir, basename: str) -> str:
    from pathlib import Path as _P
    target_dir = _P(target_dir); target_dir.mkdir(parents=True, exist_ok=True)
    p = target_dir / f"{basename}.csv"
    rows = payload.get("rows", [])
    if not rows:
        p.write_text("", encoding="utf-8")
        return str(p)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows: w.writerow(r)
    return str(p)
'''

(EVAL / 'postprocess.py').write_text(postprocess_src, encoding='utf-8')

# ===== Design doc =====
design = f'''# Postprocess and Handoff Design

Date: {ts}

## Purpose
Closes ТЗ items **2.2.5** (предварительная обработка и агрегация результатов) and
**2.2.6** (передача результатов в подсистему аналитического представления).

## Layer placement
Sits AFTER any baseline (B0..B4) executes its generated SQL. Takes the raw
SQLite row tuples and produces a structured analytics payload.

## API
- `normalize_rows(rows, column_names=None)` — coerce row-tuples to dicts; type-coerce numeric strings; preserve nulls.
- `compute_summary(rows)` — per-column descriptive summary (count / distinct / min / max / sum / mean for numeric, top values for categorical).
- `build_analytics_payload(...)` — assembles the canonical handoff JSON. Includes source metadata (baseline, model, subset, idx, db_id, question, generated_sql), normalized rows, and summary.
- `export_payload_json(payload, target_dir, basename)` and `export_payload_csv(...)` — persist the payload to disk in the analytics-friendly format.

## Handoff contract (`schema_version: v1`)

```json
{{
  "schema_version": "v1",
  "produced_at": "<ISO8601 UTC>",
  "source": {{
    "baseline": "B3",
    "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "subset": "smoke_10",
    "idx": 0,
    "db_id": "concert_singer",
    "question": "How many singers do we have?",
    "generated_sql": "SELECT COUNT(*) FROM singer;",
    "gold_sql_present": true
  }},
  "rows": [{{ "c0": 6 }}],
  "summary": {{
    "row_count": 1,
    "columns": {{"c0": {{"count": 1, "null_count": 0, "distinct_count": 1, "dtype": "numeric", "min": 6, "max": 6, "sum": 6, "mean": 6.0}}}}
  }},
  "n_rows": 1,
  "is_executable": true,
  "notes": []
}}
```

## Why this contract
- Reporting subsystem (the partner project) accepts JSON; it can also ingest the parallel CSV mirror.
- `source.*` block makes every payload self-describing — no need to look up which baseline produced it.
- `summary` is computed once at handoff so the BI side does not have to re-aggregate trivial stats.
- `schema_version` lets the contract evolve without silent breakage.

## What this module deliberately does NOT do
- Authentication / authorization (left to the consuming subsystem).
- Schema-aware semantic enrichment (e.g., resolving FK references) — would require schema metadata at handoff; deferred.
- Streaming for large result sets (current impl materialises everything in memory; OK for benchmark sizes ≤ 1000 rows).
- Schema-version migration (only v1 exists now).
'''
(OUTPUTS / 'logs' / 'postprocess_and_handoff_design.md').write_text(design, encoding='utf-8')

# ===== Worked examples (analytics handoff demo) =====
import sys
mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None) or globals().get(name)
db_paths = _from_main('db_paths')
execute_sql = _from_main('execute_sql')

sys.path.insert(0, str(EVAL))
for mod in ['postprocess']:
    if mod in sys.modules: del sys.modules[mod]
import postprocess as pp

EXPORTS_DIR = OUTPUTS / 'analytics_handoff'
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Pick 3 demo predictions: one from B0, one from B1, one from B2_v1
demos = []
for prefix, label, model in [
    ('b0_spider_smoke10', 'B0', 'Qwen/Qwen2.5-Coder-7B-Instruct'),
    ('b1_spider_smoke10', 'B1', 'Qwen/Qwen2.5-Coder-7B-Instruct'),
    ('b2_v1_spider_smoke10', 'B2_v1', 'Qwen/Qwen2.5-Coder-7B-Instruct'),
]:
    pred_p = OUTPUTS / 'predictions' / f'{prefix}_predictions.jsonl'
    if not pred_p.exists(): continue
    rec = json.loads(next(open(pred_p, encoding='utf-8')))  # first item
    if not rec.get('execution_match'): continue
    try:
        rows = execute_sql(db_paths[rec['db_id']], rec['generated_sql'])
    except Exception:
        continue
    payload = pp.build_analytics_payload(
        question=rec['question'], db_id=rec['db_id'],
        generated_sql=rec['generated_sql'], gold_sql=rec.get('gold_sql'),
        rows=rows, baseline=label, model=model, subset='smoke_10', idx=rec['idx'])
    json_p = pp.export_payload_json(payload, EXPORTS_DIR, f'{label}_smoke10_idx{rec["idx"]}')
    csv_p = pp.export_payload_csv(payload, EXPORTS_DIR, f'{label}_smoke10_idx{rec["idx"]}')
    demos.append({'baseline': label, 'idx': rec['idx'], 'db_id': rec['db_id'],
                  'question': rec['question'], 'sql': rec['generated_sql'],
                  'n_rows': payload['n_rows'], 'json_path': json_p, 'csv_path': csv_p,
                  'summary_preview': json.dumps(payload['summary'], ensure_ascii=False)[:400]})

# Examples MD
ex_lines = ['# Analytics Handoff Examples\n', '',
            f'Generated at: {ts}',
            'Demonstrates the postprocess → analytics-handoff layer for one item per baseline.',
            'Files saved to `outputs/analytics_handoff/`.', '',
            '| baseline | idx | db_id | n_rows | question | generated_sql | json_path | csv_path |',
            '|---|---|---|---|---|---|---|---|']
for d in demos:
    ex_lines.append(f"| {d['baseline']} | {d['idx']} | `{d['db_id']}` | {d['n_rows']} | {d['question'][:80]} | `{d['sql']}` | `{d['json_path'].replace(str(PROJECT_ROOT)+'/','')}` | `{d['csv_path'].replace(str(PROJECT_ROOT)+'/','')}` |")
ex_lines += ['', '## Per-demo summary previews', '']
for d in demos:
    ex_lines.append(f"### {d['baseline']} idx={d['idx']}")
    ex_lines.append(f'```json\n{d["summary_preview"]}\n```')
    ex_lines.append('')

(OUTPUTS / 'tables' / 'analytics_handoff_examples.md').write_text('\n'.join(ex_lines), encoding='utf-8')

print(f'WROTE {EVAL / "postprocess.py"} ({(EVAL / "postprocess.py").stat().st_size} B)')
print(f'WROTE {OUTPUTS / "logs" / "postprocess_and_handoff_design.md"}')
print(f'WROTE {OUTPUTS / "tables" / "analytics_handoff_examples.md"}')
print(f'demos written: {len(demos)} (in {EXPORTS_DIR})')
print('STATUS=DONE')
