"""System-level evaluation metrics."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterator

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - dependency is in requirements.
    psutil = None  # type: ignore[assignment]


@dataclass(slots=True)
class ResourceMeasurement:
    latency_ms: float
    memory_peak_mb: float | None


@contextmanager
def measure_resources() -> Iterator[ResourceMeasurement]:
    process = psutil.Process() if psutil is not None else None
    start_rss = process.memory_info().rss if process is not None else None
    start = perf_counter()
    measurement = ResourceMeasurement(latency_ms=0.0, memory_peak_mb=None)
    try:
        yield measurement
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        measurement.latency_ms = elapsed_ms
        if process is not None and start_rss is not None:
            end_rss = process.memory_info().rss
            measurement.memory_peak_mb = max(start_rss, end_rss) / (1024 * 1024)


def summarize_system_metrics(predictions: list[dict[str, Any]]) -> dict[str, float]:
    if not predictions:
        return {
            "latency_ms": 0.0,
            "memory_peak_mb": 0.0,
            "failure_rate": 0.0,
        }

    latency_values = [
        float(row["latency_ms"])
        for row in predictions
        if row.get("latency_ms") is not None and row.get("latency_ms") != ""
    ]
    memory_values = [
        float(row["memory_peak_mb"])
        for row in predictions
        if row.get("memory_peak_mb") is not None and row.get("memory_peak_mb") != ""
    ]
    failures = sum(1 for row in predictions if row.get("status") != "ok")

    return {
        "latency_ms": sum(latency_values) / len(latency_values) if latency_values else 0.0,
        "memory_peak_mb": max(memory_values) if memory_values else 0.0,
        "failure_rate": failures / len(predictions),
    }
