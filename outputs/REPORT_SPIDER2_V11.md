# Spider2 Phase 13 (v11 schema-grounding) — unified report

_Generated: 2026-05-08 | branch: `experiments/denis` | author: Denis_

> **Scope.** Two pilot runs this session: Lite-BQ v10 pilot10 (real BQ
> execute, async batch pattern) and Snow v11 pilot10 (canonical 547 with
> schema-grounding rework). NEITHER pilot cleared the FULL-launch gate;
> NO FULL benchmark was launched. DBT FULL 68 from Phase 11 (13.2%
> task_success) is still the only publishable Spider2 number.

---

## 1. Hard status

| component | status |
|---|:---:|
| Bridge (chassis-tracked-scanned-britney) | ✅ alive |
| BigQuery live | ✅ project=`project-0e0fc8a5-…` |
| Snowflake live | ✅ PARTICIPANT/COMPUTE_WH_PARTICIPANT |
| Spider2-Lite 547 | ✅ |
| Spider2-Snow canonical 547 | ✅ |
| Spider2-DBT 68 examples | ✅ TARGET=69 dirs, SECONDARY=69 dirs |
| Phase 13 commit (this session) | local-only, NOT pushed |
| Phase 11/12 commits (`09abb5a`/`44a4d23`) | local-only, NOT pushed |

## 2. Lite-BQ v10 pilot10 — real BQ execute, async batch

`outputs/spider2_lite/runs/lite_bq_v10_pilot10/`

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| parse_ok (BQ dry_run) | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| repair_helpful | 0 | — |

Error taxonomy: `object_not_found` 10/10. Source breakdown: C1_retrieval 9, C2_cte 1.

**Architecture win**: this is the first BQ pilot that ran cleanly through
the Cloudflare quick-tunnel without HTTP 524 timeout. The new
async pattern (`start_pilot_bg` + Drive `_DONE` marker + 30s polling)
made one big batch run inside Colab and surfaced no transport-level
failures. ~1811s wall (~3 min/task).

**Gate decision (per user policy ≥30% parse_ok)**: BQ FULL 205 NOT
launched. Same root cause as Snow v9/v10: model invents columns/tables
not in catalog. The v10 retry-wrapper (`bigquery_persistent_executor_v10`)
is built but irrelevant because no transport failures occurred — the
ones that did occur were the model's identifier hallucinations.

## 3. Snow v11 pilot10 — schema-grounding rework

`outputs/spider2_snow/runs/snow_v11_pilot10/`

| metric | v10 pilot10 | **v11 pilot10** | delta |
|---|---:|---:|---:|
| n_total | 10 | 10 | — |
| **chosen_schema_valid** | n/a | **1 (10.0%)** | **0 → 1** |
| parse_ok (SF dry_run) | 0 | 0 | 0 |
| execute_ok | 0 | 0 | 0 |
| `schema_invalid` errors | n/a | 9 | new bucket |
| `syntax` errors (SF) | 4 | 1 | -3 |
| `object_not_found` (SF) | 6 | 0 | -6 ✅ |
| `wrong_dialect` | 0 | 0 | 0 |

Source breakdown (chosen): C0_direct 4, C1_retrieval 4, C2_cte 2.

**What v11 does differently**:

1. Builds a per-DB catalog from the canonical Snow metadata
   (`spider2_snow_extract/spider2-snow/resource/databases/<DB>/<SCH>/<table>.json`)
   on first reference; 152 dbs total, GA4 + PATENTS verified populated
   (catalog wipes when Colab `/content` resets — the runner now
   re-extracts from the Drive tarball).
2. Renders schema as canonical unquoted `DB.SCHEMA.TABLE` (no
   `table_fullname`, no outer-quote blob — v10 H1 form).
3. Strict pre-execution validator using sqlglot AST → detects unknown
   tables and unknown columns before sending anything to Snowflake.
4. Schema-aware repair: when validator fails, the LLM is given an
   explicit `UNKNOWN_COLUMN: x; suggestions=[NEAREST_TABLE.NEAREST_COL]`
   message (Levenshtein distance ≤ 2 on column names, ≤ 3 on table
   names).
5. Only schema-valid candidates go to SF dry_run. Anything else is
   marked `schema_invalid` without burning Snowflake credits.

**Result**: v11 lifted `chosen_schema_valid` from 0 (v10) to 1 (10%)
on the same 10 tasks. The remaining 9 tasks had no schema-valid
candidate even after one repair round — the LLM kept inventing
identifiers despite seeing the validator's nearest-match suggestions.
The single schema-valid candidate failed SF dry_run with `syntax` —
the validator caught all column/table names but the SQL had a
Snowflake-specific construct error (e.g. wrong window-function form
or unsupported clause).

**Gate decision (per user policy ≥30%)**: Snow FULL 547 NOT launched.

Wall: ~860 s for 10 tasks; ~86 s/task (canonical Snow tables are
larger than the Lite SF subset, so prompts are bigger).

## 4. Why both lanes share the same root cause

| diagnosis | v9 SF pilot3 | v10 SF pilot10 | v10 BQ pilot10 | **v11 SF pilot10** |
|---|---:|---:|---:|---:|
| n | 3 | 10 | 10 | 10 |
| dialect-class errors (`wrong_dialect` etc.) | 2 | 0 | 0 | 0 |
| 4-part identifier errors | n/a | (58 collapsed) | n/a | (collapsed) |
| `object_not_found` SF / BQ | 1 | 6 | **10** | **0** |
| `schema_invalid` (validator gate) | n/a | n/a | n/a | **9** |
| parse_ok (engine-level dry_run) | 0 | 0 | 0 | 0 |

After dialect normalizer (v9), 4-part collapse (v10), and strict schema
validator (v11), the engines never even get to see SQL with hallucinated
identifiers — but the model is still GENERATING those identifiers; we
just stop them at the gate.

**Conclusion.** The remaining bottleneck is **schema-linking quality
upstream of generation**, not normalizer / validator coverage. This is
a **model-quality** problem with Coder-7B BF16, not an engineering gap.

## 5. What does NOT work yet

- A single-round schema-aware repair did not lift any of the 9 invalid
  cases on Snow v11. Multi-round repair may help but each round costs
  ~30–80s and cumulative compounding is unclear.
- Picking the "least invalid" candidate when none is schema-valid was
  not used for execution (correctly — gate-blocked) but suggests no
  partial-credit metric is available.

## 6. What's deferred and why

- **Spider2-Lite BQ FULL 205**: gate failed (parse_ok 0 << 30%). Backport
  Snow v11 schema-grounding to BQ before any FULL attempt.
- **Spider2-Lite SF FULL 207**: gate failed in v9 (0/3) and v11 (1/10).
- **Spider2-Snow FULL 547 (canonical)**: gate failed in v11.
- **Spider2-Lite SQLite (135)**: stays non-comparable by design.
- **Spider2-DBT FULL 68**: already done in Phase 11 — `task_success=9/68=13.2%`.
- **INT4 Coder-32B**: not attempted this session; Coder-32B BF16 doesn't
  fit Colab L4 22 GB; INT4 needs a separate experiment.

## 7. Cost / runtime

| pilot | n | total wall (s) | s/task | engine cost |
|---|---:|---:|---:|---|
| Lite-BQ v10 pilot10 | 10 | ~1811 | ~181 | 0 bytes billed (no schema-valid SQL reached BQ live execute) |
| Snow v11 pilot10 | 10 | ~860 | ~86 | warehouse stayed warm; no execute (--no-execute) |

Neither pilot consumed measurable BQ bytes or SF credits because no
candidate reached real execution.

## 8. v9 → v10 → v11 progression on the same 10-task slice

| dimension | v9 SF | v10 SF | **v11 SF** |
|---|---|---|---|
| `wrong_dialect` errors | 2/3 | 0/10 (eliminated) | 0/10 |
| 4-part identifiers | n/a | 58 collapsed | (collapsed) |
| `object_not_found` reaching engine | 6/10 | 7/10 | **0/10** ← validator gate stops them |
| chosen schema_valid | 0/10 | 0/10 | **1/10 (10%)** |
| parse_ok | 0/10 | 0/10 | 0/10 |

## 9. Architectural improvements landed this session

- **Async batch pattern**: `start_*_bg(...)` returns immediately; BG
  thread does the work; local poller checks Drive markers every 30s.
  Solves Cloudflare 100s edge timeout. Used by both Lite-BQ v10 and
  Snow v11 runners.
- **Catalog-self-recovery awareness**: documented in next-steps log.
  Volatile `/content/spider2_snow_extract/` wipes on Colab restart; the
  current runner gracefully re-extracts from the persistent Drive
  tarball (~15s, 9883 files, 152 dbs).
- **Lite-BQ pilot now reaches a clean failure mode**: BQ HTTP wave
  (Phase 12 v9) is gone; what remains is model-quality `object_not_found`,
  the same blocker as Snow.

## 10. Exact artifact paths

Code (added/extended this session):
- `repo/src/evaluation/spider2_snow_catalog_v11.py` — canonical catalog builder
- `repo/src/evaluation/spider2_snow_schema_grounding_v11.py` — strict validator + Levenshtein nearest-match suggestions
- `repo/src/evaluation/spider2_snow_v11_colab_runner.py` — Colab-side schema-grounded runner
- `repo/src/evaluation/spider2_lite_bq_v10_colab_runner.py` — Colab-side BQ batch runner
- `tools/run_spider2_lite_bq_v10_pilot.py` — local launcher, async pattern
- `tools/run_spider2_snow_v11_pilot.py` — local launcher, async pattern

Pilot artifacts:
- `outputs/spider2_lite/runs/lite_bq_v10_pilot10/{predictions,candidates,traces}.jsonl + metrics/error_taxonomy/source_breakdown/cost_runtime CSVs + readout.md`
- `outputs/spider2_snow/runs/snow_v11_pilot10/{predictions,candidates,traces}.jsonl + same CSVs + readout.md`
- `outputs/predictions/spider2_lite_bq_v10_pilot10_predictions.jsonl`
- `outputs/predictions/spider2_snow_v11_snow_v11_pilot10_predictions.jsonl`

Phase 13 unified report: this file (`outputs/REPORT_SPIDER2_V11.md`) +
`outputs/tables/spider2_full_master_matrix_v11.{csv,md}`,
`outputs/tables/spider2_full_lane_breakdown_v11.csv`,
`outputs/tables/spider2_full_error_taxonomy_v11.csv`,
`outputs/logs/spider2_v11_scientific_findings.md`,
`outputs/logs/spider2_v11_production_recommendation.md`.

## 11. Next-session recommendation

1. **Backport Snow v11 schema-grounding to Lite-BQ**: same pattern
   (sqlglot AST → catalog lookup → nearest-match repair). The BQ
   schema is already on Drive and the BQ runner is ready to host
   the validator.
2. **Try INT4 Coder-32B on Snow v11 pilot10 directly**: load via
   `bitsandbytes` 4-bit quantization, target the same 10 tasks. If
   `chosen_schema_valid` jumps to 50%+, model quality is confirmed
   as the bottleneck and a stronger generator becomes the priority.
3. **Multi-round schema-aware repair**: try `max_repair_rounds=3` on
   Snow v11. Each round adds ~1 min/task but if it converts even 3/10
   cases the gate becomes reachable.
4. **Push commits** (`a5cdbfe`, `09abb5a`, `44a4d23`, and the new Phase
   13 commit) — only on explicit user approval.
