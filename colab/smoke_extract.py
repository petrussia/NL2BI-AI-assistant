"""Smoke client for the Colab Text-to-SQL service.

Examples
--------

# Hit a remote tunnel:
python -m colab.smoke_extract --base-url https://abc123.ngrok-free.app

# With Bearer auth:
python -m colab.smoke_extract --base-url https://... --token "$COLAB_API_TOKEN"

# Run a single fixture:
python -m colab.smoke_extract --base-url http://127.0.0.1:8000 \
    --request-file demo_data/extraction_requests/top_n.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUESTS_DIR = REPO_ROOT / "demo_data" / "extraction_requests"


def _http_get(url: str, timeout: float = 10.0, headers: dict | None = None) -> tuple[int, dict]:
    req = request.Request(url, method="GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, json.loads(body.decode("utf-8")) if body else {}
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"_raw": "<unreadable>"}
        return exc.code, payload


def _http_post_json(
    url: str, payload: dict, timeout: float = 60.0, headers: dict | None = None
) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, method="POST", data=body)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return resp.status, json.loads(data.decode("utf-8")) if data else {}
    except error.HTTPError as exc:
        try:
            payload_err = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload_err = {"_raw": "<unreadable>"}
        return exc.code, payload_err


def _summarize_response(resp: dict) -> dict:
    if not isinstance(resp, dict):
        return {"_invalid": True}
    return {
        "request_id": resp.get("request_id"),
        "status": resp.get("status"),
        "sql": (resp.get("sql") or {}).get("query"),
        "row_count": (resp.get("result_table") or {}).get("row_count"),
        "truncated": (resp.get("result_table") or {}).get("truncated"),
        "columns": (resp.get("result_table") or {}).get("columns"),
        "errors": [e.get("code") for e in (resp.get("errors") or [])],
        "warnings": [w.get("code") for w in (resp.get("warnings") or [])],
        "latency_ms": (resp.get("execution") or {}).get("latency_ms"),
    }


def _check_derived_aggregation(resp: dict) -> tuple[bool, str]:
    """For every field with provenance.derived=True or .aggregation set,
    default_aggregation MUST be 'none' (downstream must not re-aggregate)."""
    if not isinstance(resp, dict):
        return True, "no response"
    failures: list[str] = []
    for fm in resp.get("field_metadata") or []:
        prov = fm.get("provenance") or {}
        derived = bool(prov.get("derived"))
        agg = prov.get("aggregation")
        default = fm.get("default_aggregation")
        if (derived or agg) and default != "none":
            failures.append(
                f"{fm.get('name')!r}: derived={derived} agg={agg!r} "
                f"but default_aggregation={default!r}"
            )
    if failures:
        return False, "; ".join(failures)
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Colab /extract smoke client")
    parser.add_argument("--base-url", required=True, help="e.g. https://<tunnel> or http://127.0.0.1:8000")
    parser.add_argument(
        "--request-file",
        action="append",
        help="Specific request JSON. May repeat. Default: all files in demo_data/extraction_requests/",
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--token",
        default=os.environ.get("COLAB_API_TOKEN"),
        help="Bearer token for /extract. Defaults to $COLAB_API_TOKEN.",
    )
    parser.add_argument(
        "--expect-unauthorized",
        action="store_true",
        help="Send NO token and require 401 from /extract.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print the full extract response, not a summary.",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    auth_headers: dict = {}
    if args.token and not args.expect_unauthorized:
        auth_headers["Authorization"] = f"Bearer {args.token}"

    print(f"== /health @ {base} ==")
    code, health_payload = _http_get(f"{base}/health", timeout=10.0)
    print(f"http {code}")
    print(json.dumps(health_payload, ensure_ascii=False, indent=2))

    if args.request_file:
        files = [Path(p) for p in args.request_file]
    else:
        files = sorted(DEFAULT_REQUESTS_DIR.glob("*.json"))

    if not files:
        print("No request fixtures found.", file=sys.stderr)
        return 2

    print()
    failures = 0
    for path in files:
        print(f"== /extract @ {path.name} ==")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"invalid JSON in {path}: {exc}", file=sys.stderr)
            failures += 1
            continue
        started = time.monotonic()
        code, resp = _http_post_json(
            f"{base}/extract",
            payload,
            timeout=args.timeout,
            headers=auth_headers,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        print(f"http {code} (round-trip {elapsed_ms} ms)")
        if args.expect_unauthorized:
            if code == 401:
                print("PASS: /extract correctly returned 401 without Bearer token")
            else:
                print(f"FAIL: expected 401, got {code} body={resp}")
                failures += 1
            print()
            continue

        if args.full:
            print(json.dumps(resp, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(_summarize_response(resp), ensure_ascii=False, indent=2))

        if code != 200 or (resp.get("status") if isinstance(resp, dict) else None) == "failed":
            failures += 1
            print()
            continue

        ok, detail = _check_derived_aggregation(resp)
        if not ok:
            failures += 1
            print(f"FAIL: derived aggregation rule violated: {detail}")
        print()

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
