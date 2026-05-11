from __future__ import annotations

from contracts.extraction import DataType, SemanticRole


def _looks_time(name: str) -> bool:
    lowered = name.casefold()
    return any(
        lowered == token
        or lowered.endswith(f"_{token}")
        or lowered.startswith(f"{token}_")
        or token in lowered
        for token in (
            "date",
            "time",
            "month",
            "year",
            "day",
            "week",
            "quarter",
            "decade",
            "дата",
            "время",
            "месяц",
            "год",
            "день",
            "недел",
            "квартал",
            "десятилет",
        )
    )


def infer_semantic_role(name: str, data_type: DataType) -> SemanticRole:
    lowered = name.casefold()
    if lowered in {"id", "uuid"} or lowered.endswith("_id") or lowered.endswith(" id"):
        return "id"
    if _looks_time(name):
        return "time"
    if data_type in {"date", "datetime"}:
        return "time"
    if data_type == "number":
        return "measure"
    if data_type == "boolean":
        return "dimension"
    if any(token in lowered for token in ("description", "comment", "note", "описан", "коммент")):
        return "text"
    if data_type == "string":
        return "dimension"
    return "unknown"
