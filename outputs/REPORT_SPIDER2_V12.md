# Spider2 Phase 14 (v11/v12 schema-grounding) — unified report

_Generated: 2026-05-08 | branch: `experiments/denis` | author: Denis_

> **Scope.** This phase backports schema-grounding to Lite-BQ (v11) and
> sharpens the Snow pipeline with strict compact render + 3-round
> repair (v12). Both pilots ran cleanly; **both gate-failed**. The
> aggregate evidence across v11 BQ, v11 Snow, and v12 Snow is now
> strong enough to call **"schema-grounding alone insufficient"** —
> the next blocker is model quality, not engineering. NO FULL
> benchmark was launched. Spider2-DBT FULL 68 (13.2%) from Phase 11
> remains the only publishable Spider2 number.

---

## 1. Hard status

| component | status |
|---|:---:|
| Bridge | ✅ |
| BigQuery / Snowflake live | ✅ |
| Catalog availability (Snow + BQ on Drive) | ✅ |
| Phase 14 commit (this session) | local-only, NOT pushed |
| Phase 10/11/12/13 commits | local-only, NOT pushed |

## 2. BQ pilot/full result

**Spider2-Lite-BQ v11 pilot10** (real BQ live execute, schema-grounding):

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 0 | 0.0% |
| parse_ok (BQ dry_run) | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| repair_helpful | 0 | — |

Error taxonomy: `schema_invalid` 10/10. Source breakdown: C0_direct 9, C2_cte 1. Wall ~1232s (~123s/task).

**Comparison to v10**:
- v10 BQ pilot10: 10/10 `object_not_found` AT BIGQUERY (model invented `project.dataset.table` and `column` names; BQ rejected them).
- v11 BQ pilot10: 10/10 `schema_invalid` AT VALIDATOR (caught BEFORE BQ; **0 bytes billed on hopeless SQL**).
- The validator gate works as designed, but the model's identifier hallucination rate is too high for any candidate (in 3 candidates × 10 tasks × 30 candidate slots) to be schema-valid. 2 repair rounds with explicit nearest-match suggestions did not lift any task over the gate.

**Gate decision**: `chosen_schema_valid 0% << 30%` → Spider2-Lite BQ FULL 205 NOT launched.

## 3. Snow pilot/full result

**Spider2-Snow v12 pilot10** (canonical 547 dataset, strict compact render + 3-round repair):

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 0 | 0.0% |
| parse_ok (SF dry_run) | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| repair_helpful | 0 (all 3 rounds) | — |

Error taxonomy: `schema_invalid` 10/10. Source breakdown: C0_direct 5, C1_retrieval 4, C2_cte 1. Wall ~1573s (~157s/task).

**Comparison to v10/v11 (same 10-task slice)**:

| metric | v10 (pilot10) | v11 (pilot10) | **v12 (pilot10)** |
|---|---:|---:|---:|
| n | 10 | 10 | 10 |
| chosen_schema_valid | 0 | **1 (10%)** | **0 (0%)** |
| parse_ok | 0 | 0 | 0 |
| execute_ok | 0 | 0 | 0 |
| `wrong_dialect` | 0 | 0 | 0 |
| 4-part identifier collapses | 58 across cands | (collapsed) | (collapsed) |
| `object_not_found` AT engine | 7 | 0 | 0 |
| `schema_invalid` (validator gate) | n/a | 9 | 10 |
| `syntax` | 4 | 1 | 0 |
| repair_helpful | 0 | 0 | 0 |

**v12 regressed slightly vs v11** (1/10 → 0/10 schema_valid). The
stricter compact render likely dropped context that the v11 render
provided through descriptions and samples — context that occasionally
helped the model land on a correct column name. The 3-round repair
(unknown-id fix → syntax fix → regenerate-from-scratch) did not pull
any task over the gate; round 3 (full regenerate) had the same
hallucination problem.

**Gate decision**: `chosen_schema_valid 0% << 30%` → Spider2-Snow FULL 547 NOT launched.

## 4. Lite-SF pilot/full result

**Skipped this session** — gate policy says only run Lite-SF pilot if
Snow v12 cleared the schema_valid ≥ 30% gate. Snow v12 returned 0%, so
Lite-SF v12 was not piloted.

## 5. Gates passed/failed

| benchmark | gate | result |
|---|---|:---:|
| DBT FULL 68 (Phase 11) | "any-real-FULL" | ✅ PASSED — 13.2% |
| BQ v11 FULL 205 | parse_ok ≥ 30% | ❌ FAIL (0%) |
| Snow v11 FULL 547 | schema_valid ≥ 30% | ❌ FAIL (10%) |
| Snow v12 FULL 547 | schema_valid ≥ 30% | ❌ FAIL (0%) |
| Lite-SF v12 FULL 207 | not run (Snow gate failed) | — |

## 6. v10 → v11 → v12 — what improved, what didn't

**Engineering wins (validated by Phase 14 numbers):**
- ✅ Validator gate prevents engine-level `object_not_found` entirely.
  Before v11: every invalid identifier hit Snowflake/BigQuery and
  burned credits/bytes. After v11/v12: 0 bytes billed on hopeless SQL.
- ✅ Async batch pattern (start_*_bg + Drive _DONE marker) eliminated
  Cloudflare 100s edge timeouts. All 3 Phase 14 pilots ran > 1000s
  through the tunnel without HTTP errors.
- ✅ Self-recovery for Colab `/content` wipe: Snow v12 runner
  re-extracts the Drive tarball if the local schema dir is missing.

**Engineering deltas that did NOT translate to gate-clears:**
- ❌ Strict compact render (top-K + sorted, top-N columns/table, no
  marketing text) lost ground vs v11 render (1/10 → 0/10).
- ❌ 3-round repair (r1 unknown-id, r2 syntax, r3 regenerate) did not
  improve schema_valid in any of the 10 tasks. Each round added
  ~30-50s wall.
- ❌ BQ schema-grounding (v11) gave 0/10 schema_valid — even worse
  than Snow v11 because BQ table identifiers (`project.dataset.table`
  with dashes / lowercase) are harder for the model.

**Aggregate conclusion**: schema-grounding **necessary but not
sufficient**. The remaining bottleneck is **model-side schema linking**
— Coder-7B cannot reliably produce identifiers from a catalog the size
of `bigquery-public-data` or canonical Snow even with explicit
nearest-match hints.

## 7. What's deferred and why

| benchmark | status | reason |
|---|---|---|
| Spider2-Lite BQ FULL 205 | DEFERRED | Pilot10 0/10 schema_valid; gate ≥ 30% failed. |
| Spider2-Lite SF FULL 207 | DEFERRED | Snow v12 gate failed; same root cause expected. |
| Spider2-Snow FULL 547 | DEFERRED | Pilot10 v12 0/10 schema_valid. |
| Spider2-Lite SQLite | NON-COMPARABLE | By design (sample-rows stub). |
| Spider2-DBT FULL 68 | DONE Phase 11 | task_success 9/68 = 13.2%. |
| INT4 Coder-32B sanity | DEFERRED | Per user spec: only if schema works first. Schema gate didn't pass. |

## 8. Cost / runtime

| pilot | n | wall (s) | s/task | engine cost |
|---|---:|---:|---:|---|
| BQ v11 pilot10 | 10 | ~1232 | ~123 | 0 BQ bytes billed |
| Snow v12 pilot10 | 10 | ~1573 | ~157 | 0 SF credits (no-execute mode) |

Validator-gating saved a non-trivial amount of cost: 30 candidate SQL
strings × 10 tasks per pilot all stopped before reaching the engine.

## 9. Exact artifact paths

Code (added/extended this session):
- `repo/src/evaluation/spider2_bq_catalog_v11.py`
- `repo/src/evaluation/spider2_bq_schema_grounding_v11.py`
- `repo/src/evaluation/spider2_lite_bq_v11_colab_runner.py`
- `repo/src/evaluation/spider2_snow_v12_colab_runner.py`
- `tools/run_spider2_lite_bq_v11_pilot.py`
- `tools/run_spider2_snow_v12_pilot.py`

Pilot artefacts:
- `outputs/spider2_lite/runs/lite_bq_v11_pilot10/{predictions,candidates,traces}.jsonl + metrics CSVs + readout.md + _DONE marker`
- `outputs/spider2_snow/runs/snow_v12_pilot10/` (same shape; no traces because runner-internal)
- `outputs/predictions/spider2_lite_bq_v11_lite_bq_v11_pilot10_predictions.jsonl`
- `outputs/predictions/spider2_snow_v12_snow_v12_pilot10_predictions.jsonl`

Phase 14 unified report: this file (`outputs/REPORT_SPIDER2_V12.md`),
plus `outputs/tables/spider2_full_master_matrix_v12.{csv,md}`,
`outputs/tables/spider2_full_lane_breakdown_v12.csv`,
`outputs/tables/spider2_full_error_taxonomy_v12.csv`,
`outputs/tables/spider2_full_cost_runtime_v12.csv`,
`outputs/logs/spider2_v12_scientific_findings.md`,
`outputs/logs/spider2_v12_production_recommendation.md`,
`outputs/logs/spider2_v12_bq_root_cause.md`,
`outputs/logs/spider2_v12_snow_root_cause.md`,
`outputs/logs/spider2_phase14_state_audit.md`.

## 10. Next-session recommendation

The schema-grounding direction has been validated as a correct gate
(no engine-level identifier errors anymore) but **does not, by itself,
clear pilot gates** with Coder-7B BF16 on this hardware. Two
non-engineering levers remain:

1. **INT4 Coder-32B** on Snow v12 pilot10 (~30-45 min including model
   load via bitsandbytes 4-bit). If `chosen_schema_valid` jumps to
   3+/10, the bottleneck is confirmed as model size; FULL becomes
   reachable on a stronger generator. If still 0-1/10, model is not
   the lever and the architecture itself needs rework.
2. **Constrained decoding restricted to catalog tokens**: heavier lift,
   but in principle would force the model to emit only allowed
   identifiers. This is a research-level experiment, not a quick fix.
3. **Hybrid retrieval**: include the *exact* gold-task column list
   when available (per Spider2-Snow per-task metadata), bypassing the
   guess-and-check loop. This would change the experimental scope
   (it's closer to "oracle retrieval") and should be marked clearly.

Push commits (`a5cdbfe`, `09abb5a`, `44a4d23`, `2b95742`, and the
incoming Phase 14 commit) only on explicit user approval. Rotate the
GCP SA test key before any external publish.
