# Spider2 v8 — production recommendation

_Generated: 2026-05-08 | branch experiments/denis_

## TL;DR

The v8 architecture (Snow / Lite / DBT) is **wired and validated** at
PILOT level. **Do NOT publish or use any score below as a final
benchmark number** — those require FULL runs (≤§4 of the unified report).

## What is safe to use right now

- The lane router (`spider2_lite_router_v8.classify`) — deterministic,
  no model involvement.
- The Snowflake EXPLAIN-based dry_run (`spider2_sf_executor_v8`) —
  catches `wrong_dialect`, `object_not_found`, `database_missing`,
  `permission_denied`, `warehouse_error`, `auth_error`, `timeout`,
  `syntax`. Tested live against PARTICIPANT/COMPUTE_WH_PARTICIPANT.
- The BQ executor through bridge (`spider2_lite_bq_tools_v8`) —
  tested live, returns real BQ error messages.
- The Spider2-DBT bridge pipeline + V4 variant — validated end-to-end
  on `playbook001` with score 1/1 in this session, consistent with
  prior n=6 ablation.

## What is NOT safe to publish

- Any execute_ok / EX number from the PILOT runs. n=1–3 is too small.
- Any cross-benchmark comparison. The three benchmarks are separate.
- Any "Spider2" score that mixes BQ / SF / SQLite. Lanes are
  intentionally split.

## Recommended next operational steps

1. **Run Spider2-DBT FULL 68 with V4** (cheapest, ~1.5h, on remote
   server). This gives us the first publishable Spider2 number.
2. **Apply the backtick→doublequote post-processor** before running
   Spider2-Snow FULL — H1 in the scientific findings predicts a free
   parse-rate lift.
3. **Acquire `spider2-snow.jsonl` (547)** from the Spider2 GitHub
   release; until then Phase 1 FULL is on the 207 SF subset of
   Spider2-Lite.
4. **Add `tools/.bridge_url` and `snowflake_setup/.env` to `.gitignore`**
   before pushing any further commit.
5. **Rotate the GCP service-account key at merge time.** User has
   approved continued use of the test key during exploration; this is
   a merge-gate, not an exploration-gate.
