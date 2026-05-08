# Spider2 v9 — production recommendation

_Generated: 2026-05-08 | branch experiments/denis_

## TL;DR

- **Publishable now**: Spider2-DBT FULL 68, V4 variant,
  task_success = 9/68 = **13.2%**. This is the first FULL Spider2
  benchmark number for this project.
- **Not publishable**: Spider2-Snow canonical 547 and Spider2-Lite 547
  were gated out by pilot10 results; FULL runs were NOT launched.

## What can be put into ВКР right now

1. **Spider2-DBT v8/v4 FULL 68 = 13.2%** (matched > 0 by official_eval).
   - Cite the run dir, the predictions jsonl, and the official_eval
     return codes. Mention dbt_run_ok 39.7%, dbt_test_ok 38.2%.
   - Acknowledge that dbt code-gen is harder than text-to-SQL; the
     13.2% is achieved by a 7B Coder model with V4 (diff-form) prompt
     after a paired ablation against V1 / V2 (commit 8f57eea).
2. **Spider2-Snow canonical 547 dataset acquisition** with sha256
   manifest (commit 16345f9 → expanded this session). Demonstrates
   pipeline readiness; FULL number is queued.
3. **v9 dialect normalizer experiment** (Snow v8 pilot3 vs v9 pilot10):
   `wrong_dialect` errors went 2/3 → 0/10. Eliminates one class of
   failure entirely. Underlying generator quality remains the
   limitation.

## What MUST NOT go into ВКР

- Any Spider2-Snow FULL number — none was produced.
- Any Spider2-Lite FULL or "Spider2 average" — partial pilot data only.
- Any score from the SQLite stub lane as if it were comparable to
  official EX.

## Recommended next operational steps (priority order)

1. **Snow H1 fix** (cheapest, ~30 min code): drop `table_fullname` from
   `render_subset` so the model never sees the duplicate identifier.
   Sanity 10 → 100 → FULL.
2. **Lite F3 fix** (~1–2 h code): wrap BQ executor in a persistent
   Colab daemon to stop the HTTP 500 wave; or move to local BQ client
   once the SA key rotation is done.
3. **Lite F4 fix** (~30 min): one-shot sync of `resource/databases/sqlite`
   to local disk; case-insensitive resolver becomes purely local.
4. **Spider2-Snow Coder-32B sanity** on n=10 to bound the headroom
   before any structural agent change.
5. **Push commits** (current `a5cdbfe` + the next Phase 11 commit) only
   on explicit user approval. **Rotate the GCP service-account key**
   before any external publish.
