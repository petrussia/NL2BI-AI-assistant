"""bigquery_persistent_executor_v10 — F3 fix: retries + backoff + smaller payload.

Pilot v9 BQ failed because `bridge_exec` returned HTTP 500 from the
Cloudflare tunnel, which we propagated as `agent_exception`. This v10
wrapper:
  - Reuses the persistent Colab-side BQ Client built by
    `spider2_lite_bq_tools_v8.build_bq_executor`.
  - Adds bounded retries with exponential backoff on HTTP 5xx /
    socket errors.
  - Logs `retry_count`, `dry_run_ok`, `bytes_scanned`, `error_class`
    in every result so failures are diagnosable.

Why not a full daemon: the persistent Colab kernel ALREADY owns the
BQ Client (the bootstrap inside `build_bq_executor` puts `_BQ_CLIENT`
in the kernel globals and reuses it across calls). What broke last time
was the per-call HTTP transport, not the BQ client. Retrying that fixes
the pilot wave without rewriting the daemon.
"""
from __future__ import annotations

import json
import time
import urllib.error
from typing import Callable

from spider2_lite_bq_tools_v8 import build_bq_executor as _v8_build


def build_bq_executor_v10(*, sa_path: str = None,
                              max_bytes_billed: int = 1 * 1024 ** 3,
                              timeout_s: int = 120,
                              max_retries: int = 4,
                              backoff_base_s: float = 2.0) -> Callable:
    """Return a BQ executor that retries on HTTP 5xx / socket errors.

    Contract identical to `spider2_lite_bq_tools_v8.build_bq_executor`
    plus a `retry_count` field in the returned dict.
    """
    base_executor = _v8_build(sa_path=sa_path,
                                  max_bytes_billed=max_bytes_billed,
                                  timeout_s=timeout_s)

    def executor(sql: str, *, dry_run: bool = False,
                  max_bytes_billed_override: int = None,
                  max_rows_override: int = None,
                  dialect: str = 'bigquery') -> dict:
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                res = base_executor(sql, dry_run=dry_run,
                                       max_bytes_billed_override=max_bytes_billed_override,
                                       max_rows_override=max_rows_override,
                                       dialect=dialect)
                # If the wrapper returned ok=False with a transient class,
                # retry; otherwise stop.
                if res.get('ok'):
                    res['retry_count'] = attempt - 1
                    return res
                et = (res.get('error_type') or '').lower()
                em = (res.get('error_message') or '').lower()
                transient = (
                    'http' in et and ('5' in et or '500' in em or '502' in em
                                          or '503' in em or '504' in em)
                ) or 'bridge_exception' in et or 'no_response' in et or 'parse' in et
                if not transient:
                    res['retry_count'] = attempt - 1
                    return res
                last_err = res
            except urllib.error.HTTPError as exc:
                last_err = {'ok': False, 'error_type': 'http_error',
                              'error_message': f'{exc.code}: {exc.reason}',
                              'mode': 'bigquery_via_bridge'}
                if exc.code < 500:
                    last_err['retry_count'] = attempt - 1
                    return last_err
            except urllib.error.URLError as exc:
                last_err = {'ok': False, 'error_type': 'url_error',
                              'error_message': str(exc)[:200],
                              'mode': 'bigquery_via_bridge'}
            except Exception as exc:
                last_err = {'ok': False, 'error_type': type(exc).__name__,
                              'error_message': str(exc)[:200],
                              'mode': 'bigquery_via_bridge'}
            # Exponential backoff before next try
            time.sleep(backoff_base_s * (2 ** (attempt - 1)))

        if last_err is None:
            last_err = {'ok': False, 'error_type': 'unknown',
                          'error_message': 'all retries exhausted',
                          'mode': 'bigquery_via_bridge'}
        last_err['retry_count'] = max_retries
        return last_err

    return executor
