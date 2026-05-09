# Spider2 Phase 18 — STEP 0 state audit

_Generated: 2026-05-09 | branch: `experiments/denis` | HEAD: `181352f` (Phase 17)_

## Hard status — preconditions

| precondition | status | note |
|---|:---:|---|
| Working tree clean (Phase 17 committed) | ✅ commit `181352f` landed; many unrelated dirty files from earlier sessions remain unstaged | NOT pushed |
| Phase 17 deliverables in place | ✅ | `outputs/REPORT_SPIDER2_V17.md`, `repo/src/evaluation/model_registry_v17.py`, `tools/run_spider2_v17_pilot.py`, all 6 v17 run dirs |
| Phase 16 audit artefacts in place | ✅ | `outputs/logs/spider2_v16_root_cause_audit.md`, `outputs/tables/spider2_identifier_failure_audit_v16.csv` (117 rows), `outputs/logs/spider2_v16_next_recommendation.md` |
| Bridge alive | ✅ | `https://maui-edges-cigarette-cycles.trycloudflare.com` |
| GPU | ✅ | A100-SXM4-80GB; **VRAM only 8.9 GB free** (Qwen3-Coder-30B still loaded from Phase 17) |
| Drive mount | ✅ | `/content/drive/MyDrive/diploma_plan_sql` mounted, write-probe path proven in Phases 16/17 |
| BQ credentials | ✅ | `GOOGLE_APPLICATION_CREDENTIALS=…/secrets/spider2_bq_sa.json`, `google-cloud-bigquery` importable |
| Snow credentials | ✅ | `secrets/snowflake.json` present, `snowflake-connector-python` importable |
| HF token | ✅ | env var present |
| Python env | torch 2.10.0+cu128 / transformers 5.0.0 / Python 3.12 | same as Phase 17 tail |
| Spider2 source data | ✅ | `spider2-lite.jsonl` (547), `spider2_snow_547.jsonl`, BQ resource dir = 74 dataset folders, Snow extracted at `/content/spider2_snow_extract/spider2-snow/` |

## Catalog layout we already have on disk (Spider2 snapshot)

- BQ: `…/resource/databases/bigquery/<alias>/<gcp_project.dataset>/*.json` — 74 aliases. Each subdir holds per-table JSON (sample rows + types) shipped by Spider2 authors.
- Snow: `/content/spider2_snow_extract/spider2-snow/resource/databases/<DB_NAME>/…` — DB list confirmed.

## Phase 18 scope decision (this session)

The plan as briefed (11 steps × multiple modules each) is multi-day. Honest cut for **this session** to land a substantive Phase 18 commit without producing dead code:

| step | this session | deferred to next session |
|---|:---:|:---:|
| 0 — audit | ✅ here | — |
| 1 — live catalog snapshots | ✅ BQ live (74 datasets via `INFORMATION_SCHEMA.COLUMNS` + `INFORMATION_SCHEMA.TABLES`) and Snow live (`SHOW SCHEMAS / TABLES / COLUMNS` on relevant DBs) | broader Snow (full account_usage harvest) if any DB is too large |
| 2 — extractive schema linking module | ✅ deterministic BM25 + synonym expansion + struct/wildcard awareness | dense retrieval (would need embedding model — defer) |
| 3 — ambiguity memory | ⏸ defer | yes, too large for one session, low marginal value before §1+§2 ship |
| 4 — structured planner | ✅ `structured_plan_v18.py` JSON-output Qwen3-Coder driver | iterative refinement based on failures |
| 5 — deterministic SQL renderer + 1 control candidate (Coder-7B direct) | ✅ BQ first; Snow after BQ pilot10 | full 4-family synthesis (defer C and D until A+B land) |
| 6 — validator + minimal probe | ✅ re-use v16 validator; ambiguity probe = stub returning "no probe" path for v18.0 | richer probing in v18.1 |
| 7 — model role experiment | ✅ planner-vs-direct comparison on the same n=10 | full 4-way matrix in v18.1 |
| 8 — BQ pilot10 (only) | ✅ if pipeline lands cleanly | Snow pilot10 in v18.1 |
| 9 — premium track | ⏸ skip | only if §8 shows clear lift |
| 10 — reports | ✅ `REPORT_SPIDER2_V18.md` + master matrix + lane breakdown + recall + plan stats + cost/runtime; skip ambiguity_probe_stats (§3 deferred) and skip the v18 master matrix's full v17 cross-merge | full report set in v18.1 |
| 11 — commit | ✅ single local commit | no push |

## Architectural intent (one sentence)

Move from "ask the model to emit identifiers in open vocabulary, then fix afterwards" to "retrieve a tight schema pack, force the model to plan in JSON over closed identifiers, render the SQL deterministically, then validate and probe before selecting." Qwen3-Coder-30B's job is **plan + judge**; Coder-7B's job is **emit-control**.

## Explicit constraints honored

- No FULL launches; pilot10 only this session.
- No git push.
- No DBT rerun.
- No SQLite stub touched.
- Phase 17 commit `181352f` left as is.

## What success looks like at session end

- `outputs/cache/spider2_bq_live_catalog_v18.jsonl` populated for all 74 aliases.
- `outputs/cache/spider2_snow_live_catalog_v18.jsonl` populated for all DBs covered by the canonical 547 task subset.
- `outputs/REPORT_SPIDER2_V18.md` with BQ pilot10 result on the new pipeline.
- A single local commit titled "Phase 18 Spider2 schema-first ambiguity-resolving agent (BQ pilot10)".
- Honest "next recommendation" log noting whether the lift is real or whether retrieval is still the gating factor.

If the BQ pilot10 of the new pipeline does NOT show a real lift over Phase 17's 6/10, the report says so plainly and recommends targeting retrieval/catalog/probe at root cause rather than further architectural surface.

## Reproducibility / pointers

- Bridge URL: `tools/.bridge_url`
- Model registry: `repo/src/evaluation/model_registry_v17.py` (extended with new code-paths if needed; no breaking changes)
- New Phase 18 modules will live in `repo/src/evaluation/*_v18.py` with no edits to v16/v17 modules.
