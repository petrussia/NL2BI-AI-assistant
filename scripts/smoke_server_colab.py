from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import httpx


def main() -> int:
    server_url = os.getenv("SERVER_URL", "http://127.0.0.1:8100").rstrip("/")
    payload = {
        "user_query": os.getenv("SMOKE_QUERY", "Покажи динамику продаж по месяцам"),
        "data_source_id": os.getenv("SMOKE_DATA_SOURCE_ID", "demo_sales"),
    }
    smoke_id = uuid.uuid4().hex[:8]
    output_dir = Path("artifacts/smoke")
    output_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=70) as client:
        runtime = client.get(f"{server_url}/api/runtime").json()
        response = client.post(f"{server_url}/api/nl2chart", json=payload).json()

    request_id = response.get("request_id", smoke_id)
    output_path = output_dir / f"{request_id}.json"
    output_path.write_text(
        json.dumps({"runtime": runtime, "nl2chart": response}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "request_id": request_id,
        "status": response.get("status"),
        "output": str(output_path),
    }, ensure_ascii=False, indent=2))
    return 0 if response.get("status") in {"success", "partial_success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

