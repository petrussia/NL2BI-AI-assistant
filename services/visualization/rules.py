from __future__ import annotations

from contracts.extraction import FieldMetadata


def detect_intent(user_query: str) -> str:
    query = user_query.casefold()
    if any(token in query for token in ("динамик", "тренд", "trend", "month", "месяц", "по дня", "по год", "decade", "десятилет")):
        return "trend"
    if any(token in query for token in ("топ", "top", "лучшие", "лидер")):
        return "top_n"
    if any(token in query for token in ("сравн", "category", "категор", "по сегмент")):
        return "comparison"
    if any(token in query for token in ("коррел", "correlation", "scatter")):
        return "correlation"
    if any(token in query for token in ("распредел", "distribution", "histogram")):
        return "distribution"
    if any(token in query for token in ("таблиц", "table", "список", "list")):
        return "table"
    return "unknown"


def fields_by_role(metadata: list[FieldMetadata]) -> dict[str, list[FieldMetadata]]:
    result = {
        "time": [],
        "measure": [],
        "dimension": [],
        "text": [],
        "id": [],
        "unknown": [],
    }
    for item in metadata:
        result.setdefault(item.semantic_role, []).append(item)
    return result
