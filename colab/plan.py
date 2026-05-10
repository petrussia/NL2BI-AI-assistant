from __future__ import annotations

import re
from typing import Any

from contracts.extraction import ExtractionPlan


_TABLE_RE = re.compile(r"\bfrom\s+\"?([a-zA-Z_][a-zA-Z0-9_]*)\"?", re.IGNORECASE)
_JOIN_RE = re.compile(r"\bjoin\s+\"?([a-zA-Z_][a-zA-Z0-9_]*)\"?", re.IGNORECASE)
_GROUP_RE = re.compile(r"\bgroup\s+by\s+(.+?)(?:\border\b|\blimit\b|\bhaving\b|$)", re.IGNORECASE | re.DOTALL)
_ORDER_RE = re.compile(r"\border\s+by\s+(.+?)(?:\blimit\b|$)", re.IGNORECASE | re.DOTALL)
_LIMIT_RE = re.compile(r"\blimit\s+(\d+)", re.IGNORECASE)
_AGG_RE = re.compile(
    r"\b(sum|avg|min|max|count)\s*\(\s*([^)]+)\)",
    re.IGNORECASE,
)


def build_plan(sql: str, columns: list[str]) -> ExtractionPlan:
    if not sql:
        return ExtractionPlan(validated=False)

    tables: list[str] = []
    for m in _TABLE_RE.finditer(sql):
        if m.group(1) not in tables:
            tables.append(m.group(1))
    for m in _JOIN_RE.finditer(sql):
        if m.group(1) not in tables:
            tables.append(m.group(1))

    aggregations: list[dict[str, Any]] = []
    for m in _AGG_RE.finditer(sql):
        aggregations.append({"field": m.group(2).strip(), "aggregation": m.group(1).lower()})

    group_by: list[str] = []
    gm = _GROUP_RE.search(sql)
    if gm:
        group_by = [
            g.strip().strip('"').split(".")[-1]
            for g in gm.group(1).split(",")
            if g.strip()
        ]

    order_by: list[dict[str, Any]] = []
    om = _ORDER_RE.search(sql)
    if om:
        for piece in om.group(1).split(","):
            piece = piece.strip()
            if not piece:
                continue
            parts = piece.split()
            field = parts[0].strip('"').split(".")[-1]
            direction = "desc" if len(parts) > 1 and parts[1].lower().startswith("desc") else "asc"
            order_by.append({"field": field, "direction": direction})

    limit_val: int | None = None
    lm = _LIMIT_RE.search(sql)
    if lm:
        try:
            limit_val = int(lm.group(1))
        except ValueError:
            limit_val = None

    intent: str | None = None
    lower = sql.lower()
    if any(t in lower for t in (" group by ", "group by ")) and any(
        f"{f}(" in lower for f in ("sum", "avg", "count", "min", "max")
    ):
        intent = "aggregation"
    if order_by and limit_val:
        intent = "top_n"
    if any(k in lower for k in ("date", "month", "year", "time")) and aggregations:
        intent = "trend"

    return ExtractionPlan(
        raw={},
        validated=True,
        intent=intent,
        tables=tables,
        columns=columns,
        filters=[],
        aggregations=aggregations,
        group_by=group_by,
        order_by=order_by,
        limit=limit_val,
        joins=[],
        assumptions=[],
    )
