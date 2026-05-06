"""Dataset quality helpers for post-query Text-to-Visualization examples."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from random import Random
from typing import Any

import pandas as pd

from t2v_eval.normalization.vega_lite import mark_type


EXPLICIT_CHART_PATTERN = re.compile(
    r"\b(stacked\s+bar|bar(?:s)?|pie|scatter|line|histogram|area\s+chart|heatmap|map)\b",
    flags=re.IGNORECASE,
)
PROPORTION_PATTERN = re.compile(
    r"\b(proportion|proportions|percentage|percent|share|shares|ratio|composition)\b",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class QualityCheck:
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    duplicate_row_count: int = 0
    table_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_chart_type_signal(query: str) -> dict[str, Any]:
    """Classify whether a query explicitly names the intended chart type."""

    match = EXPLICIT_CHART_PATTERN.search(query)
    if match:
        mentioned = _canonical_chart_name(match.group(1))
        return {
            "chart_type_mentioned": True,
            "chart_type_signal": f"explicit_{mentioned}",
            "mentioned_chart_type": mentioned,
        }
    if PROPORTION_PATTERN.search(query):
        return {
            "chart_type_mentioned": False,
            "chart_type_signal": "proportion",
            "mentioned_chart_type": None,
        }
    return {
        "chart_type_mentioned": False,
        "chart_type_signal": "none",
        "mentioned_chart_type": None,
    }


def _canonical_chart_name(value: str) -> str:
    lowered = value.lower().strip()
    if "stacked" in lowered and "bar" in lowered:
        return "stacked_bar"
    if "bar" in lowered:
        return "bar"
    if "pie" in lowered:
        return "pie"
    if "scatter" in lowered:
        return "scatter"
    if "line" in lowered:
        return "line"
    return lowered.replace(" ", "_")


def infer_table_shape(metadata: dict[str, Any]) -> str:
    roles = [str(field.get("role", "unknown")) for field in metadata.get("fields", [])]
    counts = Counter(roles)
    dimensions = counts["dimension"] + counts["time"] + counts["id"]
    measures = counts["measure"]
    unknown = counts["unknown"]
    parts = [
        f"{dimensions}_dimension" + ("" if dimensions == 1 else "s"),
        f"{measures}_measure" + ("" if measures == 1 else "s"),
    ]
    if unknown:
        parts.append(f"{unknown}_unknown")
    return "_".join(parts)


def acceptable_marks(primary_mark: str | None, chart_signal: str) -> list[str]:
    """Return strict gold mark plus relaxed alternatives for known ambiguous cases."""

    mark = (primary_mark or "bar").lower()
    marks = [mark]
    if mark == "arc" and chart_signal == "proportion":
        marks.append("bar")
    return marks


def spec_field_names(spec: dict[str, Any]) -> set[str]:
    fields: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            field_value = value.get("field")
            if field_value is not None:
                fields.add(str(field_value))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(spec)
    return fields


def dataframe_fingerprint(df: pd.DataFrame) -> str:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha1(csv_bytes).hexdigest()


def validate_table_quality(
    *,
    df: pd.DataFrame,
    metadata: dict[str, Any],
    gold_spec: dict[str, Any],
    table_path: Path,
) -> QualityCheck:
    errors: list[str] = []
    warnings: list[str] = []

    if df.empty:
        errors.append("empty_table")
    if len(df.columns) == 0:
        errors.append("no_columns")
    if not table_path.exists():
        errors.append("table_file_missing")

    table_columns = {str(column) for column in df.columns}
    metadata_fields = {str(field.get("name")) for field in metadata.get("fields", [])}
    if not metadata_fields:
        errors.append("missing_metadata_fields")
    for field_name in sorted(metadata_fields - table_columns):
        errors.append(f"metadata_field_missing_in_table:{field_name}")
    for column in sorted(table_columns - metadata_fields):
        warnings.append(f"table_column_missing_in_metadata:{column}")

    for field_name in sorted(spec_field_names(gold_spec) - table_columns):
        errors.append(f"gold_field_missing_in_table:{field_name}")

    duplicate_count = int(df.duplicated().sum())
    if duplicate_count:
        warnings.append("duplicate_rows_present")

    return QualityCheck(
        status="ok" if not errors else "failed",
        errors=errors,
        warnings=warnings,
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
        duplicate_row_count=duplicate_count,
        table_fingerprint=dataframe_fingerprint(df),
    )


def build_quality_metadata(
    *,
    query: str,
    metadata: dict[str, Any],
    gold_spec: dict[str, Any],
    df: pd.DataFrame,
    table_path: Path,
) -> dict[str, Any]:
    signal = detect_chart_type_signal(query)
    primary_mark = mark_type(gold_spec)
    quality = validate_table_quality(
        df=df,
        metadata=metadata,
        gold_spec=gold_spec,
        table_path=table_path,
    )
    return {
        **signal,
        "primary_mark": primary_mark,
        "acceptable_marks": acceptable_marks(primary_mark, str(signal["chart_type_signal"])),
        "table_shape": infer_table_shape(metadata),
        "quality": quality.to_dict(),
    }


def stratification_key(example: dict[str, Any]) -> tuple[str, str, str]:
    metadata = example.get("metadata") or {}
    mark = str(metadata.get("primary_mark") or mark_type(example.get("gold_spec") or {}) or "unknown")
    explicit = "explicit" if metadata.get("chart_type_mentioned") else "implicit"
    db_id = str(metadata.get("db_id") or "unknown")
    return mark, explicit, db_id


def select_examples(
    examples: list[dict[str, Any]],
    *,
    sample_size: int | None,
    strategy: str = "first",
    seed: int = 42,
) -> list[dict[str, Any]]:
    if sample_size is None or len(examples) <= sample_size:
        return list(examples)
    if strategy == "first":
        return examples[:sample_size]
    if strategy != "stratified":
        raise ValueError(f"Unsupported sampling strategy: {strategy}")
    return stratified_sample(examples, sample_size=sample_size, seed=seed)


def stratified_sample(
    examples: list[dict[str, Any]],
    *,
    sample_size: int,
    seed: int = 42,
) -> list[dict[str, Any]]:
    rng = Random(seed)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for example in examples:
        groups[stratification_key(example)].append(example)
    for items in groups.values():
        rng.shuffle(items)

    group_keys = sorted(groups)
    selected: list[dict[str, Any]] = []
    while len(selected) < sample_size and group_keys:
        rng.shuffle(group_keys)
        next_keys: list[tuple[str, str, str]] = []
        for key in group_keys:
            items = groups[key]
            if items and len(selected) < sample_size:
                selected.append(items.pop(0))
            if items:
                next_keys.append(key)
        group_keys = next_keys
    return selected


def summarize_dataset_quality(examples: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_rows = [example.get("metadata") or {} for example in examples]
    table_fingerprints = [
        str((metadata.get("quality") or {}).get("table_fingerprint"))
        for metadata in metadata_rows
        if (metadata.get("quality") or {}).get("table_fingerprint")
    ]
    return {
        "total_examples": len(examples),
        "unique_tables_by_fingerprint": len(set(table_fingerprints)),
        "primary_mark_distribution": _count_values(metadata_rows, "primary_mark"),
        "db_id_distribution": _count_values(metadata_rows, "db_id"),
        "chart_type_signal_distribution": _count_values(metadata_rows, "chart_type_signal"),
        "chart_type_mentioned_distribution": _count_values(metadata_rows, "chart_type_mentioned"),
        "materialization_source_distribution": _count_values(metadata_rows, "materialization_source"),
        "table_shape_distribution": _count_values(metadata_rows, "table_shape"),
        "validation_status_distribution": Counter(
            str((metadata.get("quality") or {}).get("status", "unknown"))
            for metadata in metadata_rows
        ),
        "validation_errors": _count_quality_items(metadata_rows, "errors"),
        "validation_warnings": _count_quality_items(metadata_rows, "warnings"),
    }


def table_groups(examples: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for example in examples:
        metadata = example.get("metadata") or {}
        fingerprint = (metadata.get("quality") or {}).get("table_fingerprint")
        if fingerprint:
            groups[str(fingerprint)].append(str(example.get("example_id")))
    return dict(sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])))


def _count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(row.get(key, "unknown")) for row in rows)
    return dict(sorted(counter.items()))


def _count_quality_items(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for item in (row.get("quality") or {}).get(key) or []:
            counter[str(item)] += 1
    return dict(sorted(counter.items()))
