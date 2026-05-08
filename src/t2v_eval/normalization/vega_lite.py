"""Normalization helpers for Vega-Lite-like visualization specs.

The goal is not to implement the full Vega-Lite compiler. Stage 3 needs a
stable, dependency-light representation that lets evaluators compare chart type,
field choices, encodings, aggregations, transforms, and canonical JSON without
being sensitive to irrelevant key ordering or presentation-only properties.
"""

from __future__ import annotations

import json
from typing import Any, Iterable


ENCODING_CHANNELS = (
    "x",
    "y",
    "color",
    "size",
    "shape",
    "text",
    "tooltip",
    "detail",
    "opacity",
    "row",
    "column",
)

ENCODING_KEYS = (
    "field",
    "type",
    "aggregate",
    "bin",
    "timeUnit",
    "sort",
)

TRANSFORM_KEYS = (
    "aggregate",
    "bin",
    "calculate",
    "filter",
    "fold",
    "joinaggregate",
    "lookup",
    "timeUnit",
    "window",
)


class SpecNormalizationError(ValueError):
    """Raised when a spec cannot be interpreted as a Vega-Lite-like object."""


def canonical_json(value: Any) -> str:
    """Return deterministic compact JSON for exact normalized comparisons."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def mark_type(spec: dict[str, Any]) -> str | None:
    mark = spec.get("mark") or spec.get("chart_type") or spec.get("chartType")
    if isinstance(mark, str):
        return mark.lower()
    if isinstance(mark, dict):
        mark_value = mark.get("type") or mark.get("mark")
        if mark_value:
            return str(mark_value).lower()
    return None


def is_vega_lite_like(spec: Any) -> bool:
    if not isinstance(spec, dict):
        return False
    if not spec:
        return False
    if mark_type(spec) is None:
        return False
    encoding = spec.get("encoding")
    return encoding is None or isinstance(encoding, dict)


def normalize_spec(spec: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a Vega-Lite/Altair-like spec for metric computation.

    The returned object includes:
    - `valid`: bool;
    - `chart_type`: normalized mark type;
    - `encoding`: normalized channel mapping;
    - `transform`: normalized list of transform objects;
    - `canonical_json`: deterministic JSON string of the normalized core.
    """

    if spec is None:
        return _invalid("missing_spec")
    if not isinstance(spec, dict):
        return _invalid(f"expected_dict_got_{type(spec).__name__}")
    if not spec:
        return _invalid("empty_spec")

    chart = mark_type(spec)
    if chart is None:
        return _invalid("missing_mark")

    encoding_raw = spec.get("encoding") or {}
    if not isinstance(encoding_raw, dict):
        return _invalid("encoding_not_object")

    encoding = normalize_encoding(encoding_raw)
    transform = normalize_transforms(spec.get("transform") or [])

    normalized_core = {
        "chart_type": chart,
        "encoding": encoding,
        "transform": transform,
    }
    return {
        "valid": True,
        **normalized_core,
        "fields": sorted(fields_in_normalized(normalized_core)),
        "canonical_json": canonical_json(normalized_core),
    }


def normalize_encoding(encoding: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for channel in ENCODING_CHANNELS:
        if channel not in encoding:
            continue
        channel_value = normalize_channel(encoding[channel])
        if channel_value:
            normalized[channel] = channel_value
    return normalized


def normalize_channel(value: Any) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in (normalize_channel(item) for item in value) if item]
    if isinstance(value, str):
        return _normalize_shorthand(value)
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, Any] = {}
    for key in ENCODING_KEYS:
        if key not in value:
            continue
        normalized_value = _normalize_scalar(value[key])
        if normalized_value not in (None, "", [], {}):
            normalized[key] = normalized_value
    return normalized


def normalize_transforms(transforms: Any) -> list[dict[str, Any]]:
    if isinstance(transforms, dict):
        transforms = [transforms]
    if not isinstance(transforms, list):
        return []

    normalized: list[dict[str, Any]] = []
    for transform in transforms:
        if not isinstance(transform, dict):
            continue
        item: dict[str, Any] = {}
        for key in TRANSFORM_KEYS:
            if key not in transform:
                continue
            item[key] = _normalize_scalar(transform[key])
        if item:
            normalized.append(_deep_sort(item))
    return sorted(normalized, key=canonical_json)


def fields_in_normalized(normalized: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for channel_value in (normalized.get("encoding") or {}).values():
        for item in _as_channel_items(channel_value):
            field = item.get("field")
            if field:
                fields.add(str(field))
    for transform in normalized.get("transform") or []:
        _collect_fields(transform, fields)
    return fields


def aggregate_tokens(normalized: dict[str, Any]) -> set[tuple[str, str]]:
    tokens: set[tuple[str, str]] = set()
    for channel, channel_value in (normalized.get("encoding") or {}).items():
        for item in _as_channel_items(channel_value):
            aggregate = item.get("aggregate")
            field = item.get("field") or channel
            if aggregate:
                tokens.add((str(field), str(aggregate)))
    for transform in normalized.get("transform") or []:
        aggregates = transform.get("aggregate")
        if not isinstance(aggregates, list):
            continue
        for item in aggregates:
            if not isinstance(item, dict):
                continue
            field = item.get("field") or item.get("as")
            aggregate = item.get("op")
            if field and aggregate:
                tokens.add((str(field), str(aggregate)))
    return tokens


def encoding_tokens(normalized: dict[str, Any]) -> set[tuple[Any, ...]]:
    tokens: set[tuple[Any, ...]] = set()
    for channel, channel_value in (normalized.get("encoding") or {}).items():
        for item in _as_channel_items(channel_value):
            tokens.add(
                (
                    channel,
                    item.get("field"),
                    item.get("type"),
                    item.get("aggregate"),
                    canonical_json(item.get("bin")) if "bin" in item else None,
                    item.get("timeUnit"),
                    canonical_json(item.get("sort")) if "sort" in item else None,
                )
            )
    return tokens


def _invalid(reason: str) -> dict[str, Any]:
    normalized_core = {
        "chart_type": None,
        "encoding": {},
        "transform": [],
    }
    return {
        "valid": False,
        "error": reason,
        **normalized_core,
        "fields": [],
        "canonical_json": canonical_json(normalized_core),
    }


def _normalize_shorthand(value: str) -> dict[str, Any]:
    parts = value.split(":")
    if not parts:
        return {}
    normalized: dict[str, Any] = {"field": parts[0]}
    if len(parts) > 1 and parts[1]:
        normalized["type"] = parts[1]
    return normalized


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_normalize_scalar(item) for item in value]
    if isinstance(value, dict):
        return _deep_sort({key: _normalize_scalar(val) for key, val in value.items()})
    return str(value)


def _deep_sort(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deep_sort(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_deep_sort(item) for item in value]
    return value


def _as_channel_items(channel_value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(channel_value, dict):
        yield channel_value
    elif isinstance(channel_value, list):
        for item in channel_value:
            if isinstance(item, dict):
                yield item


def _collect_fields(value: Any, fields: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "field" and item:
                fields.add(str(item))
            else:
                _collect_fields(item, fields)
    elif isinstance(value, list):
        for item in value:
            _collect_fields(item, fields)
