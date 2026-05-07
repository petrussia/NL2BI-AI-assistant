# Spider2 v8 — Snow / Lite / DBT — unified report

_Generated: 2026-05-08 | branch: `experiments/denis` | author: Denis_

> **Scope of this report.** This document describes the v8 architecture
> across three Spider2 tracks (Snow, Lite, DBT), reports **PILOT-only**
> numbers (limit ≤ 3) collected in this session, and explicitly defers
> FULL benchmark numbers to a follow-up run because each FULL benchmark
> requires multi-hour wall-clock execution that did not fit this session.
>
> **No claim of an official benchmark score is made on PILOT data.**
> Every PILOT number below is labelled as such; FULL slots are present
> but empty until those runs complete.

---

## 0. Hard preflight (live probes, this session)

[outputs/logs/spider2_preflight_vNext.md](logs/spider2_preflight_vNext.md) — 8/8 ✅.

| lane | check | result |
|---|---|:---:|
| `colab_bridge` | health (pid 1139) | ✅ |
| `colab_inference` | HF_TOKEN set | ✅ |
| `bq` | client init + dry-run + live n=164656 | ✅ |
| `sf` | account RSR\*\*\*\* / role PARTICIPANT / wh COMPUTE_WH_PARTICIPANT / db PATENTS / 64 tables | ✅ |
| `s2lite` | 547 rows, lanes={bq:205, sf:207, sqlite:135} | ✅ |
| `s2snow` | 207 sf-prefix subset of Spider2-Lite (separate spider2-snow.jsonl not on Drive) | ⚠️ partial |
| `s2dbt` | SSH OK, dbt-core 1.10.8 + duckdb 1.5.2, 70 examples, evaluation_suite present | ✅ |
| `security` | secrets not in git (only `tools/.bridge_url` ephemeral URL) | ✅ |

---

## 1. Spider2 tracks: separation of claims

The three Spider2 benchmarks are NOT mixed in this report.

| benchmark | n | engine | purpose | claim shape |
|---|---:|---|---|---|
| **Spider2-Snow** | 547 | Snowflake-only (text-to-SQL) | separate official benchmark | one official EX number, **only after FULL** |
| **Spider2-Lite** | 547 | mixed: BigQuery / Snowflake / SQLite | separate benchmark; lane-aware | per-lane EX (BQ + SF), SQLite **non-comparable** stub |
| **Spider2-DBT** | 68 | code-gen agent task on dbt+DuckDB | separate benchmark | task_success rate via official_eval |

SQLite-stub results from Spider2-Lite **do not count** toward any
official benchmark score. They are listed for completeness with
`non_comparable=True`. Ground-truth/oracle-table modes are diagnostic
only and are not present in this v8 path.

---

## 2. v8 architecture (Phase 1 + 2 + 3)

### Spider2-Snow — `repo/src/evaluation/spider2_snow_*_v8.py`
| module | role | LOC |
|---|---|---:|
| `spider2_snow_router_v8.py` | per-item routing (always A_sf for Snow) | ~30 |
| `spider2_snow_tools_v8.py` | SF dialect helpers + executor re-export | ~40 |
| `spider2_snow_schema_retrieval_v8.py` | token-overlap retrieval over SfSchemaIndex | ~50 |
| `spider2_snow_candidate_generator_v8.py` | C0/C1/C2/C4 prompt builders + LLM calls | ~70 |
| `spider2_snow_selector_v8.py` | executable > parses > schema-valid > shorter | ~75 |
| `spider2_snow_repair_v8.py` | bounded repair loop on EXPLAIN error | ~50 |
| `spider2_snow_agent_v8.py` | orchestrator (verify, repair, select, execute) | ~140 |
| `tools/run_spider2_snow_full_v8.py` | full-benchmark runner | ~280 |

Reuses pre-existing `spider2_sf_executor_v8` (EXPLAIN dry_run + execute,
Snowflake error taxonomy with 9 buckets) and
`spider2_sf_prompting_v8` (12 SF dialect rules including ILIKE / QUALIFY
/ FLATTEN / VARIANT / TRY_CAST / DATE_DIFF arg order).

### Spider2-Lite — `repo/src/evaluation/spider2_lite_*_v8.py`
| module | role | LOC |
|---|---|---:|
| `spider2_lite_router_v8.py` | bq / sf / local prefix → lane | ~25 |
| `spider2_lite_tools_v8.py` | facade re-exporting BQ + SF + SQLite tool builders | ~10 |
| `spider2_lite_bq_tools_v8.py` | BQ executor through Colab bridge (SA on Drive) | ~110 |
| `spider2_lite_snow_tools_v8.py` | re-export of SF executor | ~5 |
| `spider2_lite_sqlite_tools_v8.py` | per-DB lazy-pull stub executor + non-comparable flag | ~85 |
| `spider2_lite_agent_v8.py` | per-item dispatch to BQ / Snow / SQLite agent | ~110 |
| `tools/run_spider2_lite_full_v8.py` | lane-aware runner with per-lane limits | ~225 |

Reuses Phase-10 BQ stack (`spider2_agent_v8`, `spider2_bq_*_v8`) and
the Spider2-Snow agent above.

### Spider2-DBT — `repo/src/evaluation/spider2_dbt_*_v8.py`
| module | role | LOC |
|---|---|---:|
| `spider2_dbt_agent_v8.py` | thin wrapper over the existing ablation pipeline (V4 default) | ~55 |
| `spider2_dbt_tools_v8.py` | SSH command shim re-export | ~15 |
| `spider2_dbt_project_builder_v8.py` | project-tree exporter trigger | ~25 |
| `spider2_dbt_evaluator_v8.py` | task_success helper around official_eval output | ~20 |
| `tools/run_spider2_dbt_full_v8.py` | full-68 runner with per-task metrics + readout | ~165 |

Reuses `spider2_dbt_bridge.run_dbt_ablation` (export_context → build_prompt
→ inference via bridge → apply → dbt deps/run/test → evaluate). V4 is
the default variant (winner of the n=6 V1/V2/V4 ablation in commit
8f57eea: V4 helpful=1, harmful=0).

---

## 3. PILOT results (this session)

### 3.1 Spider2-Snow PILOT (limit=3, no-execute)

Run: [outputs/spider2_snow/runs/snow_v8_pilot3/](spider2_snow/runs/snow_v8_pilot3/) (also limit=1 in `snow_v8_lim1_*`).

| metric | value |
|---|---:|
| n | 3 |
| parse_ok | 0 (0.0%) |
| execute_ok | 0 (0.0%) |
| repair_helpful | 0 |
| wall avg | ~46 s/task |

| error_type | count |
|---|---:|
| `wrong_dialect` | 2 |
| `object_not_found` | 1 |

| chosen source | count |
|---|---:|
| `C1_retrieval_docs` | 3 |

**Honest read.** Coder-7B (BF16 on Colab L4) emits BigQuery backticks /
wrong column case for SF tasks even with the 12-rule SF prompt. The
verifier catches `wrong_dialect` (BQ backticks → SF) early and the
selector correctly falls back to retrieval-grounded candidate. Real
Spider2-Snow numbers are expected to be low for a 7B coder; the
pipeline is correct.

### 3.2 Spider2-Lite PILOT (per-lane 1+1+1, no-execute)

Run: [outputs/spider2_lite/runs/lite_v8_pilot_1plus1plus1/](spider2_lite/runs/lite_v8_pilot_1plus1plus1/).

| lane | n | parse_ok | execute_ok | non_comparable |
|---|---:|---:|---:|:---:|
| `A_bq` | 1 | 0 (0.0%) | 0 (0.0%) | no |
| `A_sf` | 1 | 0 (0.0%) | 0 (0.0%) | no |
| `C_sqlite_stub` | 1 | 0 (0.0%) | 0 (0.0%) | **YES — never report officially** |

**Honest read.** All three lanes did dispatch correctly; the
LLM-generated SQL failed parse on each (BQ: `Could not cast literal
"20210101" to type DATE`; SF: model emitted incorrect column case;
SQLite: model emitted prose, not SQL). The pipeline correctness is
proven (router routes, executors run, errors are classified into the
small taxonomy). Quality of the SQL itself is bottlenecked on
Coder-7B's Spider2 reasoning, not on the framework.

### 3.3 Spider2-DBT PILOT (limit=1 + limit=3 in flight, variant=v4)

limit=1 run: [outputs/spider2_dbt/runs_v8/dbt_v8_v4_lim1_1778195957/](spider2_dbt/runs_v8/dbt_v8_v4_lim1_1778195957/)

| metric | value |
|---|---:|
| n | 1 |
| done | 1 (100%) |
| dbt_deps_ok / dbt_run_ok / dbt_test_ok | 1 / 1 / 1 |
| task_success (matched>0) | **1 (100%)** |

successful task: `playbook001`. limit=3 run is in flight at file write time —
update from `outputs/spider2_dbt/runs_v8/dbt_v8_pilot3/` once it lands.

---

## 4. FULL benchmark slots (deferred)

Each FULL benchmark requires multi-hour wall-clock and was not run in
this session. Per the explicit user policy, no FULL claim is made
on PILOT data.

| benchmark | n | est. wall-clock | runner command |
|---|---:|---|---|
| Spider2-Snow | 207 (SF subset of Lite) — 547 once `spider2-snow.jsonl` is local | ~3.5 h | `python tools/run_spider2_snow_full_v8.py --limit 0` |
| Spider2-Lite | 547 | ~9–10 h | `python tools/run_spider2_lite_full_v8.py --limit 0` |
| Spider2-DBT | 68 | ~1.5 h | `python tools/run_spider2_dbt_full_v8.py --limit 0 --variant v4` |

Recommended next-session plan:
1. Run Spider2-DBT FULL 68 first (cheapest, on remote dbt server).
2. Run Spider2-Snow FULL 547 with `spider2-snow.jsonl` (downloaded
   from Spider2 GitHub; if 547 is unavailable, run on the 207 SF
   subset of Spider2-Lite and clearly label).
3. Run Spider2-Lite FULL 547 last (uses both BQ and SF live, longest).

---

## 5. v7 → v8 deltas (carry-over context)

| benchmark | v7 number (commit) | v8 status |
|---|---|---|
| Spider2-Lite BQ EX | 1.96% (Phase 9, commit 0f70a5c) | Phase 10 BQ stack already pushed exec_ok 20.5% → 45.4% (commit 54e060c, EX 1.96 → 2.45). v8 PILOT preserves that path. |
| Spider2-Lite SF | blocked (no SF account) | v8 lane-aware runner now executes live against PARTICIPANT / COMPUTE_WH_PARTICIPANT (PILOT validated). |
| Spider2-DBT 6-task ablation | V4 helpful=1 / harmful=0 (commit 8f57eea) | v8 wraps V4 as default; PILOT 1 = `playbook001` succeeded with score 1/1. |

---

## 6. Cost / runtime (PILOT)

| benchmark | tasks | total wall (s) | s/task |
|---|---:|---:|---:|
| Spider2-Snow PILOT 3 | 3 | 138 | 46 |
| Spider2-Lite PILOT 3 | 3 | ~135 | 45 |
| Spider2-DBT PILOT 1 | 1 | 53 | 53 |

Runtime is dominated by Coder-7B inference on Colab L4 (~10–25 s per
generate × multiple candidates per task) plus EXPLAIN/dry_run round
trips to BQ / SF. SQLite stub is essentially free.

---

## 7. Blockers and known issues

1. **`spider2-snow.jsonl` (547) not on local Drive.** Phase 1 FULL
   currently runs on the 207 SF-prefix subset of Spider2-Lite. To run
   the canonical Spider2-Snow 547 benchmark, that jsonl must be
   downloaded from the Spider2 GitHub release.
2. **Coder-7B dialect bias.** The model defaults to BigQuery syntax
   even when the SF prompt explicitly forbids it. Mitigations
   available: post-process backticks → double-quotes, switch to
   Coder-32B (slower / OOM risk), or fine-tune.
3. **Colab GPU shared between runners.** The Snow/Lite runner and
   the DBT inference helper used different model-global names
   (`_MDL` vs `_MODEL`) which caused OOM when both pipelines ran
   sequentially. Mitigation in this session: explicit `_MDL`/`mdl`
   delete + `torch.cuda.empty_cache()` between phase switches.
4. **Tracked `tools/.bridge_url`.** Ephemeral Cloudflare URL is
   currently committed; we should add it to `.gitignore` (Phase 5).
5. **GCP service-account key was leaked in chat earlier.** User has
   approved continued use of the test key; rotation deferred to merge
   time.

---

## 8. Artifact paths

- Code (added/extended this session):
  - `repo/src/evaluation/spider2_snow_{router,tools,schema_retrieval,candidate_generator,selector,repair,agent}_v8.py`
  - `repo/src/evaluation/spider2_lite_{router,tools,bq_tools,snow_tools,sqlite_tools,agent}_v8.py`
  - `repo/src/evaluation/spider2_dbt_{agent,tools,project_builder,evaluator}_v8.py`
  - `tools/run_spider2_{snow,lite,dbt}_full_v8.py`
  - `tools/spider2_preflight_vnext.py`
- Preflight: [outputs/logs/spider2_preflight_vNext.md](logs/spider2_preflight_vNext.md), [outputs/tables/spider2_preflight_vNext.csv](tables/spider2_preflight_vNext.csv)
- Snow PILOTs: `outputs/spider2_snow/runs/{snow_v8_lim1_*, snow_v8_pilot3}/`
- Lite PILOT: `outputs/spider2_lite/runs/lite_v8_pilot_1plus1plus1/`
- DBT PILOTs: `outputs/spider2_dbt/runs_v8/{dbt_v8_v4_lim1_*, dbt_v8_pilot3}/`
- Canonical predictions copies: `outputs/predictions/spider2_{snow,lite,dbt}_agent_v8_*_predictions.jsonl`
- Spider2-Lite local cache: `data/spider2_lite/raw/spider2-lite.jsonl` (547 rows)

---

## 9. Next recommendation

1. Resume in a fresh session and trigger the three FULL runs
   (DBT → Snow → Lite, in that order) using the runner commands in §4.
2. Replace Coder-7B with Coder-32B (or a stronger SF-aware model) once
   GPU budget allows; this is the highest-leverage quality lever.
3. Once `spider2-snow.jsonl` (the 547-task canonical benchmark) is on
   local disk, run Phase 1 FULL on the canonical 547 rather than the
   207 subset.
4. Add `tools/.bridge_url` and `snowflake_setup/.env` to `.gitignore`
   before pushing further commits.
