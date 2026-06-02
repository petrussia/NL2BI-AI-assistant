from __future__ import annotations

import re

from contracts.extraction import FieldMetadata


AXIS_TOKEN_RE = re.compile(r"\bпо\s+[xy]\b|\b[xy]\s*[- ]?axis\b", re.IGNORECASE)


def _asks_for_xy_axis(query: str) -> bool:
    return bool(AXIS_TOKEN_RE.search(query))


def _mentions_axis(query: str, axis: str) -> bool:
    axis_pattern = re.escape(axis.casefold())
    return bool(
        re.search(
            rf"\bпо\s+{axis_pattern}\b|\bпо\s+оси\s+{axis_pattern}\b|\bось\s+{axis_pattern}\b|\b{axis_pattern}\s*[- ]?axis\b",
            query,
            re.IGNORECASE,
        )
    )


def _is_heatmap_query(query: str) -> bool:
    return any(token in query for token in ("теплов", "тепров", "heatmap", "heat map", "матриц")) or (
        any(token in query for token in ("цвет", "color", "окрас", "закрас"))
        and _mentions_axis(query, "x")
        and _mentions_axis(query, "y")
    )


def detect_intent(user_query: str) -> str:
    query = user_query.casefold()
    if _is_heatmap_query(query):
        return "heatmap"
    if _asks_for_xy_axis(query) or any(
        token in query
        for token in (
            "коррел",
            "correlation",
            "scatter",
            "dot plot",
            "point chart",
            "точеч",
            "точк",
            "рассеян",
            "рассеив",
        )
    ):
        return "correlation"
    if any(token in query for token in ("boxplot", "box plot", "ящик", "ус", "выброс")):
        return "boxplot"
    if any(token in query for token in ("гистограмм", "histogram")):
        return "histogram"
    if any(token in query for token in ("кругов", "pie", "donut", "сектор", "доля", "доли", "share", "part-to-whole")):
        return "part_to_whole"
    if any(token in query for token in ("stacked", "накоплен", "разбив", "вклад", "состав")):
        return "composition"
    if any(token in query for token in ("area chart", "area graph", "област", "площадн")):
        return "area"
    if any(
        token in query
        for token in (
            "динамик",
            "тренд",
            "trend",
            "month",
            "monthly",
            "месяц",
            "месяч",
            "помесяч",
            "ежемесяч",
            "по дня",
            "по год",
            "decade",
            "десятилет",
        )
    ):
        return "trend"
    if any(token in query for token in ("топ", "top", "лучшие", "лидер")):
        return "top_n"
    if any(token in query for token in ("сравн", "category", "категор", "по сегмент")):
        return "comparison"
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
