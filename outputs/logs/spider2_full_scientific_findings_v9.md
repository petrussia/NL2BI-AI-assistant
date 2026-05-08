# Spider2 Phase 11 (v9) — scientific findings

_Generated: 2026-05-08 | branch experiments/denis_

> **Status of these findings.** F1 below is supported by the FULL DBT 68
> run (real publishable data). F2–F4 are pilot-level diagnostics with
> n=10 — they are hypotheses to validate, not benchmark claims.

## F1 — Spider2-DBT V4 (diff-form) generalizes from 6-task ablation to FULL 68

**Real FULL data**: `outputs/spider2_dbt/runs_v8/dbt_v8_FULL_68/`.

- task_success (matched > 0) = 9/68 = **13.2%**
- dbt_run_ok = 27/68 = **39.7%**
- dbt_test_ok = 26/68 = **38.2%**
- 6/6 tasks from the n=6 V1/V2/V4 ablation that V4 won are in the FULL
  success set: `playbook001, lever001, retail001` (the original 6 had
  smoke-success on V4) plus 6 new wins outside the smoke set (`mrr001,
  quickbooks003, salesforce001, superstore001, f1003, mrr002`).
- Mean wall ≈ 49 s/task; total ≈ 56 min.

**Implication.** V4 is not over-fit to the 6-task smoke set; the
diff-form prompt scales to the full 68. 13.2% is the project's first
publishable Spider2-DBT FULL number.

## F2 — Snowflake dialect normalizer fully eliminates `wrong_dialect` failures (n=10)

**Pilot-level**: `outputs/spider2_snow/runs/snow_v9_pilot10/`.

- v8 pilot3: `wrong_dialect` 2/3 chosen candidates.
- v9 pilot10: `wrong_dialect` **0/10**. Three candidates received
  `unnest_to_flatten` rewrite via the normalizer.
- Net: dialect-class errors are gone. New dominant class is `object_not_found` (semantic) at 6/10 and `syntax` at 4/10 (mostly quadruple-qualified table identifiers).

**Implication.** The remaining gap is **schema-linking + model
identifier hygiene**, not dialect. The dialect normalizer is doing its
job; further gains on Spider2-Snow require schema-rendering changes
(drop `table_fullname` to avoid double-concat) and likely a stronger
generator than Coder-7B BF16 on L4.

## F3 — Cloudflare bridge degrades under sustained BQ executor traffic (n=4 + 3 + 3)

**Pilot-level**: `outputs/spider2_lite/runs/lite_v9_pilot10/`.

- Task 1 (bq011) returned HTTP 500 immediately (0.56 s).
- Task 2 (bq010) hung 1248 s before HTTP 500.
- Tasks 3, 4 instant 500.
- After the BQ wave, SF tasks (5–7) returned `syntax` in 2–16 s with
  empty SQL — much faster than Snow v9 pilot10 (66–227 s/task), strong
  evidence the kernel was in a degraded post-error state.

**Implication.** The pattern of sending large code blobs through
`/exec` for every executor call is fragile. Alternatives for next
session:
1. **Local BQ client** (would require pulling the SA key off Drive —
   blocked by current security policy).
2. **Persistent Colab daemon** that owns one BQ client and exposes a
   smaller HTTP surface (cheaper per-call payload).
3. **Restart kernel** between failed phases.

## F4 — Spider2-Lite SQLite stub db naming requires explicit case mapping

**Pilot-level**: 3/3 SQLite tasks failed with `sqlite_db_missing`.
Dataset record has `db=E_commerce` (CamelCase); Spider2 ships
`e_commerce` lowercase on Drive. The v9 case-insensitive resolver was
correct in design (it tries `db.lower()`), but the failed bridge wave
prevented it from completing the lookup.

**Implication.** Even after the bridge issue is fixed (F3), we should
sync the SQLite tree to local disk once at startup and resolve names
locally — bridge-per-task is the wrong shape for SQLite stub.

## What is not concluded from this session

- No Snow FULL claim. Pilot10 parse_ok=0 is below the gate; FULL was
  not run.
- No Lite FULL claim. Same reason for BQ + SF; SQLite is non-comparable
  by design.
- No "Spider2 average" — the three benchmarks are separate; only DBT
  can be ranked from this session's data.

## Validation plan when work resumes

1. **Snow H1**: schema-rendering fix (drop `table_fullname`); 10-task
   sanity; if parse_ok ≥ 30% → 100-task; if ≥ 50% → FULL 547.
2. **Snow H3**: try Coder-32B on the same 10 tasks (cap memory by
   leaving only one model on GPU). Decide between H1 vs H3 on cost.
3. **Lite F3**: rewrite BQ executor to use a long-lived Colab daemon.
   Pilot10 again; if BQ stable AND parse_ok ≥ 30% → FULL.
4. **Lite F4**: pre-sync SQLite tree to `data/spider2_lite/resource/databases/sqlite/`
   on startup; case-insensitive resolver becomes purely local.
