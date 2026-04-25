"""Dataclasses for the post-query Text-to-Visualization data contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


FieldRole = Literal["dimension", "measure", "time", "id", "unknown"]


@dataclass(slots=True)
class FieldMetadata:
    name: str
    dtype: str
    role: FieldRole = "unknown"
    description: str | None = None
    unit: str | None = None
    periodicity: str | None = None
    allowed_aggregations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldMetadata":
        return cls(
            name=str(data["name"]),
            dtype=str(data.get("dtype", "unknown")),
            role=data.get("role", "unknown"),
            description=data.get("description"),
            unit=data.get("unit"),
            periodicity=data.get("periodicity"),
            allowed_aggregations=list(data.get("allowed_aggregations") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class T2VSpec:
    raw_spec: dict[str, Any] = field(default_factory=dict)
    normalized_spec: dict[str, Any] | None = None
    spec_type: str = "vega_lite"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "T2VSpec":
        if data is None:
            return cls()
        return cls(
            raw_spec=dict(data.get("raw_spec") or data.get("spec") or data),
            normalized_spec=data.get("normalized_spec"),
            spec_type=str(data.get("spec_type", "vega_lite")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class T2VExample:
    example_id: str
    query: str
    table_path: str
    metadata: dict[str, Any]
    gold_spec: dict[str, Any] = field(default_factory=dict)
    gold_spec_normalized: dict[str, Any] | None = None
    benchmark: str | None = None

    @property
    def fields(self) -> list[FieldMetadata]:
        return [
            FieldMetadata.from_dict(field_data)
            for field_data in self.metadata.get("fields", [])
        ]

    @property
    def table(self) -> Path:
        return Path(self.table_path)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "T2VExample":
        return cls(
            example_id=str(data["example_id"]),
            query=str(data["query"]),
            table_path=str(data["table_path"]),
            metadata=dict(data.get("metadata") or {"fields": []}),
            gold_spec=dict(data.get("gold_spec") or {}),
            gold_spec_normalized=data.get("gold_spec_normalized"),
            benchmark=data.get("benchmark") or data.get("benchmark_source"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class T2VPrediction:
    run_id: str
    method: str
    example_id: str
    status: Literal["ok", "failed"] = "ok"
    raw_output: str | None = None
    raw_spec: dict[str, Any] | None = None
    normalized_spec: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float | None = None
    memory_peak_mb: float | None = None
    error: str | None = None

    @classmethod
    def failed(
        cls,
        *,
        run_id: str,
        method: str,
        example_id: str,
        error: str,
        raw_output: str | None = None,
        latency_ms: float | None = None,
    ) -> "T2VPrediction":
        return cls(
            run_id=run_id,
            method=method,
            example_id=example_id,
            status="failed",
            raw_output=raw_output,
            latency_ms=latency_ms,
            error=error,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "T2VPrediction":
        return cls(
            run_id=str(data["run_id"]),
            method=str(data["method"]),
            example_id=str(data["example_id"]),
            status=data.get("status", "ok"),
            raw_output=data.get("raw_output"),
            raw_spec=data.get("raw_spec"),
            normalized_spec=data.get("normalized_spec"),
            candidates=list(data.get("candidates") or []),
            latency_ms=data.get("latency_ms"),
            memory_peak_mb=data.get("memory_peak_mb"),
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
