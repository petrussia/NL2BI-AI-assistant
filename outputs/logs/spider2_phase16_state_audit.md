# Spider2 Phase 16 — state audit

_Generated: 2026-05-08 | branch: `experiments/denis`_

## Git
- HEAD = `520bfe3` (Phase 15 Snow v13 + BQ v12)
- Remote (origin/experiments/denis): same `520bfe3` (user pushed Phase 15) — verified via `git pull --ff-only` returning "Already up to date."
- Last 5 commits: `520bfe3` / `0a8b433` / `2b95742` / `44a4d23` / `09abb5a`

## Live infra
- Bridge `chassis-tracked-scanned-britney.trycloudflare.com` → pid 6135 ✅
- BigQuery / Snowflake live ✅ (rechecked Phase 14/15)
- HF token set on Colab ✅

## Phase 15 carry-over
- Spider2-DBT FULL 68 = 9/68 = 13.2% (Phase 11 commit 09abb5a) — only publishable.
- Snow v11 = 1/10 schema_valid (best-ever Snow pilot).
- Snow v12 = 0/10, Snow v13 = 0/9 (crash on task 10, len(None) bug).
- BQ v11 = 0/10. BQ v12 = 1/10 (struct/wildcard validator fixes).

## Phase 16 plan (this session)
1. **Root-cause audit** across all 8 historical pilots → CSV + memo.
2. **Fix Snow crash** (`len(None)` on external_knowledge).
3. **BQ nested rewrite v16** (GA4 event_params, GA360 hits, wildcard, project-doubled).
4. **Identifier mapper v16** (multi-signal scoring; alias-aware; quoted-identifier-aware).
5. **Catalog-constrained repair v16** (deterministic substitution → re-validate → dry_run; structured-selection fallback).
6. **BQ v16 pilot10** (gate ≥30%).
7. **Snow v16 pilot10** (gate ≥30%).
8. **Lite-SF v16** only if Snow improves materially.
9. **INT4 32B sanity** only if v16 lifts schema_valid ≥ 2/10.
10. Reports + tables + logs (REPORT_SPIDER2_V16.md + master_matrix_v16 + breakdowns).
11. Commit Phase 16 (no push).

## Constraints
- No FULL without gate (≥30% pilot10, ≥50% pilot30).
- No mixing Snow/Lite/DBT.
- No SQLite stub in any official score.
- No secrets / no git push.
