"""Post-processing + analytics handoff layer for the NL2SQL pipeline.

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
