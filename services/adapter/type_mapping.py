from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from contracts.extraction import DataType


_DATE_RE = re.compile(r"^\d{4}(-\d{2}){0,2}$")


def infer_data_type(name: str, values: list[Any]) -> DataType:
    non_null = [value for value in values if value is not None]
    if not non_null:
        lowered = name.casefold()
        if any(
            token in lowered
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
                "месяц",
                "год",
                "десятилет",
            )
        ):
            return "date"
        return "unknown"

    if all(isinstance(value, bool) for value in non_null):
        return "boolean"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_null):
        return "number"
    if all(isinstance(value, (date, datetime)) for value in non_null):
        return "datetime" if any(isinstance(value, datetime) for value in non_null) else "date"
    if all(isinstance(value, str) and _DATE_RE.match(value.strip()) for value in non_null):
        return "date"
    return "string"
