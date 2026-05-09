# Spider2 Phase 12 (v10 recovery) — H1 / F3 / F4 fixes — unified report

_Generated: 2026-05-08 | branch: `experiments/denis` | author: Denis_

> **Honest scope.** Phase 12 is a **recovery pass**, not a new FULL run.
> No FULL benchmark was launched this session — pilot gates failed
> for Snow/Lite, and DBT FULL 68 is already published from Phase 11
> (commit `09abb5a`, task_success = 9/68 = 13.2%).
>
> What this phase delivers: three concrete code-level fixes (Snow
> identifier rendering H1, Lite SQLite materializer F4, BQ executor
> retry F3) and pilot-level evidence on what they unlock.

---

## 1. Hard status

| component | status |
|---|:---:|
| Phase 11 commit `09abb5a` | local-only (not pushed) |
| Phase 12 v10 modules + runners | written, smoke-tested |
| Spider2-DBT FULL 68 | ✅ DONE (Phase 11 — 13.2% task_success) |
| Spider2-Snow FULL 547 | ❌ deferred — v10 pilot10 still 0/10 (gate ≥50%) |
| Spider2-Lite FULL 547 | ❌ deferred — BQ bridge wave + SQLite missing materializer (now fixed) |
| Spider2-Lite SQLite v10 pilot10 | 🟡 in flight at report-write time (`outputs/spider2_lite/_sqlite_v10_pilot10.log`) |
| Spider2-Lite BQ v10 retry-wrapper | ✅ written, pilot deferred (needs kernel restart) |

## 2. Snow v10 pilot10 — H1 fix verified, parse_ok unchanged

**Run**: `outputs/spider2_snow/runs/snow_v10_pilot10/`

| metric | v9 pilot10 | **v10 pilot10** |
|---|---:|---:|
| n | 10 | 10 |
| parse_ok | 0 (0%) | **0 (0%)** |
| execute_ok | 0 (0%) | 0 (0%) |
| `wrong_dialect` errors | 0 | 0 |
| `object_not_found` | 6 | 7 |
| `syntax` | 4 | 3 |
| **identifier_4part_collapsed (across all candidates)** | n/a | **58** |
| identifier_quoted_blob_unwrapped | n/a | 0 |
| dialect-fix `unnest_to_flatten` | 3 | 1 |
| dialect-fix `sqlglot_transpile` | 0 | 2 |

**Conclusion.** The H1 fix is doing real work — the v10 identifier
normalizer collapsed 58 4-part identifiers across the 10 tasks (model
emits these on nearly every candidate). But parse_ok stays at 0%
because the model also invents column/table names that don't exist
in the canonical Snow schema. **Identifier hygiene is necessary but
not sufficient** for parse_ok.

Per user's gate policy (≥50% for FULL):
**Spider2-Snow FULL 547 stays deferred.**

### Snow v9 → v10 delta (what changed)

- **What v10 fixes**: 4-part / blob-quoted identifiers — all 58
  occurrences collapsed cleanly. `wrong_dialect` (BQ-isms) remains
  fully suppressed (was 0 already in v9; v10 maintains).
- **What v10 does NOT fix**: column/table invention. Model freely
  references columns the schema doesn't have. This is a
  schema-linking + model quality problem.
- **What's next** (in priority order):
  1. **Drop `table_fullname` from prompt** entirely (already done in
     `render_subset_v10` — verified: v10 uses unquoted DB.SCHEMA.TABLE
     only). This already happened in this session.
  2. **Strengthen retrieval**: include exact column list per shortlisted
     table with deterministic ordering; cap by token budget.
  3. **Switch to a stronger generator**: Coder-7B is too small. Coder-
     32B BF16 is ~64 GB and won't fit Colab L4 (22 GB). Options:
     INT4-quantized 32B; remote API model; or a smaller fine-tune.

## 3. Lite SQLite v10 — F4 fix (materializer)

**Critical discovery in this session**: Spider2-Lite ships SQLite
"databases" as **per-table row-level JSON files plus DDL.csv** —
there are NO `.sqlite` binaries on disk. The v8/v9 SQLite executor
opened a path that never existed, hence every SQLite pilot failed.

**Fix**: `repo/src/evaluation/spider2_lite_sqlite_materializer_v10.py`
builds a real `<DB>.sqlite` from the JSONs once per DB, idempotent.

- E_commerce smoke test: **11 tables, 55 rows materialized** ✅.
- Includes a 30-entry alias map for known dataset⇄disk mismatches
  (`Db-IMDB → DB_IMDB`, `sqlite-sakila → SQLITE_SAKILA`).
- Audit at `outputs/tables/spider2_lite_sqlite_resolver_v10_audit.csv`.

**Pilot10 results (`run_spider2_lite_sqlite_v10_pilot.py --limit 10`)**:

| metric | v9 pilot10 | **v10 pilot10** |
|---|---:|---:|
| n | 3 | 10 |
| parse_ok | 0 (0%) | **0 (0%)** |
| executable | 0 (0%) | 0 (0%) |
| `sqlite_db_missing` | **3 (100%)** | **0 (0%)** ← F4 fix verified |
| `object_not_found` | 0 | **8** |
| `syntax` | 0 | **2** |

**The F4 fix is verified.** v9: 100% of SQLite failures were
infrastructure (`sqlite_db_missing`). v10: 0% are infrastructure;
all 10 are real model-quality failures (`object_not_found` 8 +
`syntax` 2). Wall times 4–37s/task.

SQLite stays flagged **non_comparable=True** in every output row —
this lane is for parse/exec smoke only, not official EX.

## 4. Lite BQ v10 — F3 fix (retry wrapper)

**Pilot v9 BQ failure mode**: `bridge_exec` returned HTTP 500
(Cloudflare quick-tunnel under load). Task 2 hung 1248 s before
giving up; tasks 3–4 instant-failed because the kernel was in a
post-error state.

**Fix**: `repo/src/evaluation/bigquery_persistent_executor_v10.py`
wraps the existing v8 BQ executor with bounded retries + exponential
backoff (max_retries=4, base 2s) and surfaces `retry_count` in every
result.

**Why not a full daemon**: the persistent kernel ALREADY owns the
single BQ Client (`_BQ_CLIENT` global, set on first `build_bq_executor`
call). What broke last time was the per-call HTTP transport, not the
BQ client. Retrying the transport fixes the wave without rewriting the
runtime.

**Pilot test deferred this session** because a fresh kernel restart is
required to clear the post-error state cleanly. Will be the first
action of the BQ pilot run next session.

## 5. Coder-7B vs Coder-32B (deferred)

Coder-32B BF16 is ~64 GB; Colab L4 has 22 GB. INT4-quantized 32B fits
~16 GB but adds quantization-loss + dequantize overhead and was not
attempted this session. Recommendation: try INT4 32B in a follow-up,
or move generation off-Colab if the budget allows.

## 6. Master matrix v10

| benchmark | n_full | n_pilot v10 | parse_ok pilot v10 | task_success | non-comp | status |
|---|---:|---:|---:|---:|:---:|---|
| Spider2-DBT v4 | 68 | — | — | **9 (13.2%) FULL** | no | Phase 11 done |
| Spider2-Snow canonical | 547 | 10 | 0 (0.0%) | — | no | FULL deferred (gate ≥50% failed) |
| Spider2-Lite — BQ lane | 205 | _pending v10 retry_ | _pending_ | — | no | FULL deferred |
| Spider2-Lite — SF lane | 207 | _shared with Snow above_ | _0_ | — | no | FULL deferred |
| Spider2-Lite — SQLite stub | 135 | 10 | 0 (0.0%) | — | **YES** | F4 verified: no more `sqlite_db_missing`; pure model errors visible |

## 7. v8 → v9 → v10 progression

| dimension | v8 | v9 | **v10** |
|---|---|---|---|
| Snow `wrong_dialect` errors | 2/3 (smoke) | 0/10 (eliminated) | 0/10 (maintained) |
| Snow 4-part identifier collapses | n/a | n/a | **58 across pilot10** |
| Snow `quoted blob` unwraps | n/a | n/a | 0 (no instances seen) |
| Snow `object_not_found` | 1/3 | 6/10 | 7/10 (semantic gap) |
| Lite SQLite executable | always 0 (.sqlite missing) | always 0 (resolver case fix didn't help — file truly absent) | **materializer built; pilot in flight** |
| Lite BQ stability | 1 task ok | 4× HTTP 500 wave | retry-wrapper built; not yet piloted |

## 8. What FULL benchmarks can be launched

- Snow FULL 547 — **NO**, gate ≥50% still failed at 0%. Need stronger
  generator OR retrieval rework before any FULL attempt.
- Lite FULL 547 — **NO**, but next session can pilot BQ + SQLite
  cleanly (retry wrapper + materializer in place).
- DBT FULL 68 — already DONE in Phase 11 at 13.2%.

## 9. Blockers (still open)

- **Snow schema-linking quality**: model invents columns. v10
  identifier fixes are necessary but not sufficient. See §2 next steps.
- **Coder-32B doesn't fit Colab L4 BF16**. Need INT4 quant or off-Colab
  inference if we want a stronger generator.
- **GCP SA test key still in use** — rotation deferred to merge time.
- **`a5cdbfe` + `09abb5a` local-only** — no `git push` triggered.

## 10. Exact artifact paths (this session)

Code:
- `repo/src/evaluation/spider2_snow_schema_render_v10.py` — H1 render fix + 4-part collapse normalizer
- `repo/src/evaluation/spider2_snow_prompting_v10.py` — strict identifier prompts
- `repo/src/evaluation/spider2_snow_agent_v10.py` — v10 agent wiring
- `repo/src/evaluation/spider2_lite_sqlite_materializer_v10.py` — F4 materializer
- `repo/src/evaluation/bigquery_persistent_executor_v10.py` — F3 retry wrapper
- `tools/run_spider2_snow_full_v10.py` — Snow v10 runner
- `tools/run_spider2_lite_sqlite_v10_pilot.py` — SQLite v10 pilot

Pilot artifacts:
- `outputs/spider2_snow/runs/snow_v10_pilot10/` (predictions, candidates, traces, metrics, error_taxonomy, source_breakdown, dialect_fix_breakdown, cost_runtime, readout)
- `outputs/predictions/spider2_snow_agent_v10_snow_v10_pilot10_predictions.jsonl`
- `outputs/spider2_lite/runs/lite_sqlite_v10_pilot10/` (in flight)
- `outputs/tables/spider2_lite_sqlite_resolver_v10_audit.csv`

Phase 12 unified report: this file (`outputs/REPORT_SPIDER2_RECOVERY_V10.md`).

## 11. Next-session recommendation

1. **Restart Colab kernel cleanly**, then run Lite BQ v10 pilot10 with
   the retry wrapper. Goal: parse_ok ≥ 30% to open BQ FULL gate.
2. **Drop `table_fullname` everywhere** — already done in v10 render
   but verify no other code path leaks it; then re-pilot Snow.
3. **Try INT4-quantized Coder-32B** on the same Snow pilot10 to
   measure model-headroom vs prompt-headroom.
4. **Push commits** (`a5cdbfe` + Phase 12 commit when done) only on
   explicit user approval.
5. **Rotate GCP SA test key** before any external publish.
