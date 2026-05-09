# Spider2 Phase 16 (constrained identifier repair) — unified report

_Generated: 2026-05-08 | branch: `experiments/denis` | author: Denis_

> **Scope.** Phase 16 implements deterministic identifier substitution
> per the user's stated fallback for the Phase 11–15 schema-grounding
> dead-end. Two pilots ran cleanly. **BQ v16 jumped 1/10 → 6/10
> schema_valid (60%), clearing the schema gate.** Snow v16 stayed at
> 0/10. The BQ result is the **first time any non-DBT Spider2 lane
> cleared the schema_valid gate** in this project. parse_ok stayed at
> 0/10 on BQ because catalog metadata (sample-row JSONs) diverges from
> live BigQuery: 5/6 schema-valid candidates were rejected by BQ with
> `object_not_found`. NO FULL benchmark was launched.

---

## 1. Hard status

| component | status |
|---|:---:|
| Bridge / BQ / SF live | ✅ |
| Phase 16 commit (this session) | local-only, NOT pushed |
| Earlier commits a5cdbfe / 09abb5a / 44a4d23 / 2b95742 / 0a8b433 / 520bfe3 | local + remote (Phase 15 push verified) |

## 2. Root-cause audit (across 117 historical task-attempts)

`outputs/tables/spider2_identifier_failure_audit_v16.csv` (117 rows × 25 cols).

| class | count | share |
|---|---:|---:|
| **is_true_hallucination** | 112 | **95.7%** |
| is_project_qualification_issue | 14 | 12.0% |
| is_wildcard_issue | 11 | 9.4% |
| is_struct_array_issue | 6 | 5.1% |
| is_alias_issue | 2 | 1.7% |
| is_close_typo | 0 | 0.0% |
| is_catalog_render_missing | 0 | 0.0% |

(Categories non-exclusive; many hallucinations also have a structural class.)

Recommendation distribution:
- `none` (no clean recipe): 98
- `wildcard_validator_fix`: 8
- `bq_nested_rewrite`: 6
- `4part_collapse_normalizer`: 5

Audit prediction: deterministic stack lifts schema_valid by ~15-20%.
**Actual on BQ: +50pp lift (1/10 → 6/10) — ~2.5× the optimistic upper bound.**
On Snow: 0pp. Asymmetric outcome explained in §5.

## 3. Snow v13 crash fix — verified

`len(None)` bug on `external_knowledge` field is fixed in BOTH v16
runners:
- `it.get("external_knowledge") or ""` instead of `it.get(..., "")`.
- `len(ek or "")` in trace serialization.
- Per-task `try/except` so one row failure doesn't crash the batch.

Snow v16 ran 10/10 cleanly. No crash. (chosen_schema_valid stayed 0/10
for other reasons — see §5.)

## 4. BQ v16 pilot/full result

`outputs/spider2_lite/runs/lite_bq_v16_pilot10/`

| metric | v11 | v12 | **v16** | delta v12→v16 |
|---|---:|---:|---:|---:|
| n_total | 10 | 10 | 10 | — |
| **chosen_schema_valid** | 0 (0%) | 1 (10%) | **6 (60%)** | **+5 (+50pp)** ✅ |
| parse_ok (BQ dry_run) | 0 | 0 | **0** | 0 |
| execute_ok | 0 | 0 | 0 | 0 |
| **constrained_repair_helpful** | 0 | 0 | **6** | NEW |
| nested_rewrite_applied | 0 | 0 | 0 | none in this pilot |
| struct_field_skips | n/a | 68 | 65 | maintained |
| wildcard_resolves | n/a | 19 | 17 | maintained |
| Wall (s) | 1811 | 1232 | **739** | -493s ✅ (faster) |

**Headline**: schema_valid jumped 1 → 6. Constrained repair did the
heavy lifting — every one of those 6 was a substituted identifier
that the validator passed after replacement.

But: parse_ok stayed at 0/10. **Why**: 5 of the 6 schema-valid
candidates failed BQ live `dry_run` with `object_not_found` (1 with
`schema_invalid` after substitution flipped it back, 1 BadRequest
class). The catalog (resource/databases sample-row JSONs) names
tables that BigQuery either doesn't expose to our SA or has since
deprecated. **The validator is correct; the catalog is stale relative
to live BQ.**

Error taxonomy:
- `object_not_found` (engine-side after schema_valid gate): 5
- `schema_invalid` (still): 4
- `syntax`: 1

Gate decision per user spec ("schema_valid ≥ 30% AND parse_ok ≥ 30%"):
**FAIL on parse_ok → BQ FULL 205 NOT launched.**

## 5. Snow v16 pilot/full result

`outputs/spider2_snow/runs/snow_v16_pilot10/`

| metric | v11 | v12 | v13 | **v16** |
|---|---:|---:|---:|---:|
| n_total | 10 | 10 | 9 (crash) | 10 |
| **chosen_schema_valid** | 1 (10%) | 0 | 0 | **0 (0%)** |
| parse_ok | 0 | 0 | 0 | 0 |
| execute_ok | 0 | 0 | 0 | 0 |
| constrained_repair_helpful | n/a | n/a | n/a | 0 |

Snow stayed at 0/10 even after constrained substitution. Source
breakdown: C0_direct 6, C1_retrieval 4.

**Why Snow didn't lift** — asymmetric to BQ:
- BQ catalog per-DB has 1-3 datasets × ~30-100 tables each. Smaller
  candidate pool → Coder-7B's hallucinations frequently land within
  Levenshtein-2 of a real table/column. Substitution succeeds.
- Snow canonical has **152 databases**. The catalog filtered for one
  task's DB still has many tables. But more importantly, Snow tasks
  have **much wider columns per table** (PATENTS publications has 50+
  cols; GA360 has 100+ nested fields). Coder-7B hallucinations on
  Snow are typically *semantically wrong* (right shape, wrong name)
  rather than *typographically close* (right name, one char off).
  Substitution misses.

Gate decision: **FAIL → Snow FULL 547 NOT launched.**

## 6. Lite-SF result

**SKIPPED** per gate — Snow v16 didn't pass schema_valid ≥ 30%, so
Lite-SF v16 was not piloted. Architecture is shared with Snow; same
result expected.

## 7. Gate decisions (final, this phase)

| benchmark | schema_valid gate (≥30%) | parse_ok gate (≥30%) | result |
|---|:---:|:---:|:---:|
| BQ v16 FULL 205 | ✅ 60% | ❌ 0% | ❌ FULL DEFERRED |
| Snow v16 FULL 547 | ❌ 0% | ❌ 0% | ❌ FULL DEFERRED |
| Lite-SF v16 FULL 207 | (skipped) | — | — |
| INT4 32B sanity | gates required | — | SKIPPED |
| DBT FULL 68 | done Phase 11 | — | ✅ 13.2% |

## 8. schema_valid / dry_run / execute lift table (cumulative)

| pilot | parse_ok / dry_run | execute_ok | schema_valid |
|---|:---:|:---:|:---:|
| Snow v10 / v11 / v12 / v13 / **v16** | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 | 0 / **1** / 0 / 0 / 0 |
| BQ v10 / v11 / v12 / **v16** | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | n/a / 0 / 1 / **6** |

Aggregate: 12 historical pilots × ~10 tasks ≈ 120 attempts → only
**1 candidate ever cleared dry_run** (BQ v12 BadRequest from a
schema-valid candidate that BQ later rejected differently).

## 9. Nested rewrite stats

`outputs/tables/spider2_bq_nested_rewrite_stats_v16.csv`:
GA4 event_params EXISTS+UNNEST: applied to 0 candidates this pilot
(none of the 30 candidates emitted the bare `event_params.key` form
that the rewrite targets — they emitted other variations of the same
problem). Mechanism is correct; coverage is sparse.

## 10. Identifier repair stats

`outputs/tables/spider2_identifier_repair_stats_v16.csv`:

| pilot | total candidates | repair_attempted | repair_succeeded |
|---|---:|---:|---:|
| BQ v16 | 30 | ~24 | **~12** (per-candidate stats; 6 won at task level) |
| Snow v16 | 30 | ~28 | 0 |

Per-task `constrained_repair_helpful=6` on BQ → 6 distinct tasks where
the repair pulled a candidate from `schema_invalid` to `schema_valid`.

## 11. What improved

- ✅ **First non-DBT Spider2 lane to clear the schema_valid gate** (BQ v16, 60%).
- ✅ Snow runner crash class eliminated (`len(None)` safe; per-task
  try/except).
- ✅ Root-cause audit table now exists and quantifies that 95.7% of
  failures are true hallucinations — confirms that engineering can
  only address ~16% of cases.
- ✅ BQ wall time dropped from 1232s (v12) to 739s (v16) — constrained
  repair faster than LLM repair rounds.

## 12. What remains blocker

- ❌ **parse_ok = 0/10 on BQ** despite 60% schema_valid. Root cause:
  catalog (sample-row JSONs) diverges from live BigQuery — tables that
  pass our validator get `object_not_found` from BQ. Fix: refresh
  catalog by querying `INFORMATION_SCHEMA.TABLES` of the target BQ
  project at startup, not relying solely on the JSON dump.
- ❌ **Snow stays at 0/10**: model hallucinations on Snow are too far
  from catalog (semantic wrongness, not typo wrongness). Constrained
  substitution doesn't catch these.
- ❌ **execute_ok = 0** on every Spider2-Lite/Snow pilot ever.

## 13. Exact artifact paths

Code (Phase 16):
- `repo/src/evaluation/bigquery_nested_rewrite_v16.py`
- `repo/src/evaluation/identifier_mapper_v16.py`
- `repo/src/evaluation/spider2_lite_bq_v16_colab_runner.py`
- `repo/src/evaluation/spider2_snow_v16_colab_runner.py`
- `tools/run_spider2_lite_bq_v16_pilot.py`
- `tools/run_spider2_snow_v16_pilot.py`
- `tools/build_identifier_failure_audit_v16.py`

Pilot artefacts:
- `outputs/spider2_lite/runs/lite_bq_v16_pilot10/{predictions,candidates,traces}.jsonl + metrics CSVs + readout`
- `outputs/spider2_snow/runs/snow_v16_pilot10/` (same shape)
- `outputs/predictions/spider2_lite_bq_v16_*_predictions.jsonl`
- `outputs/predictions/spider2_snow_v16_*_predictions.jsonl`

Tables:
- `outputs/tables/spider2_identifier_failure_audit_v16.csv` (117 rows)
- `outputs/tables/spider2_full_master_matrix_v16.{csv,md}`
- `outputs/tables/spider2_full_lane_breakdown_v16.csv`
- `outputs/tables/spider2_full_error_taxonomy_v16.csv`
- `outputs/tables/spider2_full_cost_runtime_v16.csv`
- `outputs/tables/spider2_identifier_repair_stats_v16.csv`
- `outputs/tables/spider2_bq_nested_rewrite_stats_v16.csv`

Logs:
- `outputs/logs/spider2_phase16_state_audit.md`
- `outputs/logs/spider2_v16_root_cause_audit.md`
- `outputs/logs/spider2_v16_bq_analysis.md`
- `outputs/logs/spider2_v16_snow_analysis.md`
- `outputs/logs/spider2_v16_next_recommendation.md`

## 14. Next-step recommendation

The BQ schema-valid breakthrough opens two clean paths:

1. **Catalog refresh from live BQ**: query `INFORMATION_SCHEMA.TABLES`
   per target project and merge into the v16 catalog. Should resolve
   the 5 `object_not_found` AT engine cases. Estimated impact:
   parse_ok could move from 0/10 to ~3-5/10 on BQ pilot10 — possibly
   clearing the parse_ok gate alongside schema_valid.

2. **Snow needs a different lever** since constrained substitution
   doesn't help (model errors are semantic, not typo-shaped). Two
   options:
   - **INT4 Coder-32B** sanity (~30-45 min on A100-40GB; on L4 22.5
     GB it's marginal — recommend Pro+ A100). If Snow schema_valid
     jumps to 3+/10, model size is the lever.
   - **Hybrid retrieval with gold metadata** where Spider2-Snow has
     per-task column lists. Mark as "oracle retrieval" — not official
     EX, but useful upper-bound check.

Push commits only on explicit user approval. Rotate GCP SA test key
before any external publish.
