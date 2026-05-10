from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import httpx


OUTPUT_DIR = Path(os.getenv("SMOKE_OUTPUT_DIR", "docs/e2e_results/final_integration"))
BAD_EXTRACTION_CODES = {
    "invalid_extraction_response",
    "colab_unavailable",
    "extraction_timeout",
}


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fail(message: str, summary: dict[str, object]) -> int:
    summary["ok"] = False
    summary["failure"] = message
    _write_json(OUTPUT_DIR / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1


def main() -> int:
    server_url = os.getenv("SERVER_URL", "http://127.0.0.1:8100").rstrip("/")
    payload = {
        "user_query": os.getenv("SMOKE_QUERY", "Покажи динамику продаж по месяцам"),
        "data_source_id": os.getenv("SMOKE_DATA_SOURCE_ID", "demo_concert_singer"),
    }
    smoke_id = uuid.uuid4().hex[:8]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    runtime: dict[str, object] = {}
    response: dict[str, object] = {}
    http_statuses: dict[str, int] = {}
    with httpx.Client(timeout=90) as client:
        health_response = client.get(f"{server_url}/api/health")
        health_response.raise_for_status()
        ready_response = client.get(f"{server_url}/api/ready")
        ready_response.raise_for_status()
        runtime_response = client.get(f"{server_url}/api/runtime")
        runtime_response.raise_for_status()
        runtime = runtime_response.json()
        _write_json(OUTPUT_DIR / "runtime.json", runtime)
        http_statuses = {
            "/api/health": health_response.status_code,
            "/api/ready": ready_response.status_code,
            "/api/runtime": runtime_response.status_code,
        }

        summary: dict[str, object] = {
            "server_url": server_url,
            "query": payload["user_query"],
            "data_source_id": payload["data_source_id"],
            "http": http_statuses,
            "runtime_path": str(OUTPUT_DIR / "runtime.json"),
        }
        if runtime.get("extraction_mode") != "colab":
            return _fail("Expected /api/runtime extraction_mode=colab.", summary)
        if runtime.get("colab_available") is not True:
            return _fail("Expected /api/runtime colab_available=true.", summary)

        nl2chart_response = client.post(f"{server_url}/api/nl2chart", json=payload)
        nl2chart_response.raise_for_status()
        response = nl2chart_response.json()

    request_id = response.get("request_id", smoke_id)
    selected_view = response.get("selected_view") or {}
    artifacts = response.get("artifacts") or []
    _write_json(OUTPUT_DIR / "nl2chart_response.json", response)
    _write_json(OUTPUT_DIR / "selected_view.json", selected_view)
    _write_json(OUTPUT_DIR / "artifacts.json", artifacts)

    error_codes = [
        error.get("code")
        for error in response.get("errors", [])
        if isinstance(error, dict) and error.get("code")
    ]
    table_artifact_count = sum(
        1 for artifact in artifacts if isinstance(artifact, dict) and artifact.get("artifact_type") == "table"
    )
    chart_spec_artifact_count = sum(
        1 for artifact in artifacts if isinstance(artifact, dict) and artifact.get("artifact_type") == "chart_spec"
    )
    artifact_types = [
        artifact.get("artifact_type")
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("artifact_type")
    ]
    y_encoding = (((selected_view.get("spec") or {}).get("encoding") or {}).get("y") or {})
    summary = {
        "request_id": request_id,
        "status": response.get("status"),
        "server_url": server_url,
        "query": payload["user_query"],
        "data_source_id": payload["data_source_id"],
        "http": http_statuses,
        "runtime_path": str(OUTPUT_DIR / "runtime.json"),
        "response_path": str(OUTPUT_DIR / "nl2chart_response.json"),
        "selected_view_path": str(OUTPUT_DIR / "selected_view.json"),
        "artifacts_path": str(OUTPUT_DIR / "artifacts.json"),
        "table_artifact_count": table_artifact_count,
        "chart_spec_artifact_count": chart_spec_artifact_count,
        "artifact_types": artifact_types,
        "selected_view_type": selected_view.get("type"),
        "chart_type": selected_view.get("chart_type"),
        "y_field": y_encoding.get("field"),
        "y_aggregate_present": "aggregate" in y_encoding,
        "error_codes": error_codes,
    }
    if any(code in BAD_EXTRACTION_CODES for code in error_codes):
        return _fail("Live Colab response contains a blocker extraction error.", summary)
    if response.get("status") not in {"success", "partial_success"}:
        return _fail("Expected nl2chart status success or partial_success.", summary)
    if table_artifact_count < 1:
        return _fail("Expected at least one table artifact.", summary)
    if chart_spec_artifact_count < 1:
        return _fail("Expected at least one chart_spec artifact.", summary)
    if (
        payload["data_source_id"] == "demo_concert_singer"
        and payload["user_query"] == "Сравни количество певцов по странам"
    ):
        if selected_view.get("type") != "chart":
            return _fail("Expected selected_view.type=chart.", summary)
        if selected_view.get("chart_type") != "bar":
            return _fail("Expected selected_view.chart_type=bar.", summary)
        if y_encoding.get("field") != "NumberOfSingers":
            return _fail("Expected y.field=NumberOfSingers.", summary)
        if "aggregate" in y_encoding:
            return _fail("Expected no y.aggregate for already aggregated COUNT alias.", summary)

    summary["ok"] = True
    _write_json(OUTPUT_DIR / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
