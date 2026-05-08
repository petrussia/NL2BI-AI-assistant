# Spider2 Phase 12 — next steps (after v10 recovery)

_Generated: 2026-05-08 | branch experiments/denis_

## What this session shipped

1. **Snow H1 fix** (rendering + 4-part normalizer + strict prompt). v10
   pilot10 confirms the normalizer collapses 58 4-part identifiers
   across 10 tasks. Doesn't lift parse_ok above 0% — semantic invention
   is the next blocker.
2. **Lite SQLite F4 fix** (materializer that builds real `.sqlite`
   from row-level JSON stubs). Verified on E_commerce (11 tables,
   55 rows). Pilot10 in flight; first pilot where SQLite path is real.
3. **Lite BQ F3 fix** (retry wrapper around v8 BQ executor). Code
   ready; pilot deferred to next session because a fresh kernel
   restart is needed to clear the post-error state.
4. Phase 12 unified report `outputs/REPORT_SPIDER2_RECOVERY_V10.md` +
   master matrix v10 + error taxonomy v10 + identifier fix examples.

## What's blocked and why

| blocker | why | fix path |
|---|---|---|
| Snow FULL 547 | parse_ok 0% in pilot10 even after H1 | retrieval rework + INT4 Coder-32B |
| Lite BQ pilot | needs fresh kernel restart | restart Colab, then run pilot with retry wrapper |
| Lite FULL 547 | gates not met on any non-stub lane | depends on BQ pilot first |
| Push of `a5cdbfe` + Phase 12 commit | user policy: no push without explicit command | wait for user |
| GCP SA test key | rotation deferred to merge time per user | rotate before any external publish |

## Recommended next-session order (if user re-engages)

1. **Restart Colab kernel** cleanly. Verify `_BQ_CLIENT` rebuilds.
2. **Lite BQ v10 pilot10** with retry wrapper. Goal: parse_ok ≥ 30%.
3. If 2 succeeds: **Lite BQ pilot30**, then **Lite BQ FULL 205** if
   pilot30 ≥ 50%.
4. **Snow retrieval rework** (cap shortlisted tables, deterministic
   column ordering, drop redundant fields). Then **Snow pilot10 v11**.
5. If 4 still misses, sanity-check **INT4 Coder-32B** on the same 10.
6. SQLite stays in non-comparable mode forever (per design).

## Estimates

- Lite BQ pilot10: ~10 min wall.
- Lite BQ pilot30: ~30 min.
- Lite BQ FULL 205: ~3-4 h.
- Snow retrieval rework code: ~1 h.
- Snow pilot10 v11: ~15 min.
- INT4 Coder-32B load + pilot10: ~30-45 min (loading dominates).

## What is publishable now

- Spider2-DBT FULL 68 = **9/68 = 13.2% task_success** (Phase 11,
  commit `09abb5a`).
- Snow canonical 547 dataset acquisition with sha256 manifest.
- Three concrete code fixes (H1, F3, F4) with diagnostic evidence.

## What is NOT publishable

- Any Spider2-Snow score (no FULL run).
- Any Spider2-Lite FULL or per-lane production score (only pilots).
- Any "Spider2 average" — three benchmarks stay separate.
