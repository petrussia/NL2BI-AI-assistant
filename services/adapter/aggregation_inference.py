from __future__ import annotations

from contracts.extraction import Aggregation, SemanticRole


def infer_allowed_aggregations(role: SemanticRole) -> list[Aggregation]:
    if role == "measure":
        return ["sum", "avg", "min", "max"]
    if role in {"dimension", "time", "id", "text"}:
        return ["none"]
    return ["none"]


def infer_default_aggregation(role: SemanticRole) -> Aggregation:
    if role == "measure":
        return "sum"
    return "none"

