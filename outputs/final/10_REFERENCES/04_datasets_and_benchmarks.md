# Datasets and Benchmarks — Versions, Splits, Checksums

This file documents every dataset and benchmark version used by the dossier, including the exact release tags, the split sizes, the licenses, and the on-disk paths. The purpose is reproducibility: a future reader who wants to re-run any of the published numbers should be able to fetch exactly the data we used.

External research references at [01_research_dossier_references.md](01_research_dossier_references.md); internal artefacts at [02_internal_phase_reports.md](02_internal_phase_reports.md); tooling at [03_tooling_and_software.md](03_tooling_and_software.md).

## 1. Versioning convention

Each benchmark family has a *release tag* (the upstream version identifier we depend on), a *frozen-copy date* (the date the local mirror was last refreshed), and a *checksum file* in `data/<benchmark>/CHECKSUMS.sha256` listing the SHA-256 hashes of every consumed file. Numbers in the dossier are reported against the frozen-copy versions, not against upstream-as-of-publication, so that future upstream changes do not invalidate the reported figures.

Where the upstream release also publishes a leaderboard, the leaderboard snapshot date is recorded separately. Our published numbers in [09_RESULTS_ANALYSIS/](../09_RESULTS_ANALYSIS/) are dated to the leaderboard snapshot in [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md); reproducing against a later leaderboard requires comparison against that later snapshot, not against ours.

## 2. Spider 1.0

* **Release tag**: v1.0 (final), as defined in Yu et al. 2018.
* **Upstream URL**: github.com/taoyds/spider — `spider.zip` release.
* **Frozen-copy date**: 2024-12-03. The local mirror at `data/spider1/spider/` has not been refreshed since.
* **License**: CC BY-SA 4.0.
* **Splits used**:
  * Train: 7000 questions across 140 databases (not used directly — we report dev-split numbers only).
  * **Dev: 1034 questions across 20 databases.** This is the canonical evaluation set; our 94.0 % EX is reported against this split.
  * Test: held out by Spider's authors; not available locally.
* **On-disk paths**:
  * Databases: `data/spider1/database/<db_name>/<db_name>.sqlite`
  * Dev questions: `data/spider1/dev.json`
  * Gold SQL: `data/spider1/dev_gold.sql`
* **Checksums**: `data/spider1/CHECKSUMS.sha256` (20 database files + 2 JSON files + 1 gold SQL file).

## 3. BIRD

* **Release tag**: v1.0, as defined in Li et al. 2023.
* **Upstream URL**: bird-bench.github.io.
* **Frozen-copy date**: 2024-12-03.
* **License**: CC BY-SA 4.0.
* **Splits used**:
  * Train: 9428 questions across 69 databases (not used).
  * **Dev FULL: 1534 questions across 11 databases.** Our 87.9 % EX reports against this split.
  * **Dev mini: 147 questions** — a curated tractable subset, used for rapid iteration during the v9 / v14 phases. Our 90.4 % EX reports against this split.
  * Test: held out.
* **On-disk paths**:
  * Databases: `data/bird/dev_databases/<db_name>/<db_name>.sqlite`
  * Dev questions: `data/bird/dev.json`
  * Mini-dev questions: `data/bird/mini_dev.json`
  * Evidence rows: embedded in each question's `evidence` field.
* **Checksums**: `data/bird/CHECKSUMS.sha256`.
* **Notes on the evidence field**: BIRD's evidence rows are part of the question and not a separate dataset — they ship inside `dev.json`. Our v9 evidence-block prompt design (see [05_PIPELINES/02_bird_pipeline.md](../05_PIPELINES/02_bird_pipeline.md) §3) parses these rows verbatim and presents them as an instruction block to the planner.

## 4. Spider 2.0 — full series

The Spider 2.0 release contains four sub-benchmarks: Snow, Lite-Snow, Lite-BQ, and DBT. They share a common task structure and grading framework but target different engines.

* **Release tag**: v2024-09 (the September 2024 release accompanying Lei et al. 2024).
* **Upstream URL**: github.com/xlang-ai/Spider2.
* **Frozen-copy date**: 2024-12-03. Refresh blocked: the v2025-03 upstream release reorganises the task directory structure in a way that breaks our pipeline; we will refresh during Phase 31 once we can re-pin the pipeline.
* **License**: Apache 2.0.

### 4.1 Spider2-Snow

* **Split sizes**: 547 tasks (the FULL split). No train/dev/test stratification — every task is for evaluation.
* **On-disk paths**:
  * Task directories: `data/spider2_snow/tasks/<task_id>/`
  * Each task contains: `instance.json` (the question + metadata), `gold.sql` (the reference SQL), `db.json` (the database connection identifier), and `context/` (task-specific files like documentation or sample data).
  * Live database state: hosted on Snowflake, accessed via the connection credentials in `secrets/snowflake.json`.
* **Headline number**: Phase 28 FULL pending; pilot 10 4/10 exec_ok at Phase 28-revert-A.

### 4.2 Spider2-Lite-Snow

* **Split sizes**: 207 tasks (curated subset of Snow with tractable schemas).
* **On-disk paths**: `data/spider2_lite_snow/tasks/<task_id>/` with the same per-task structure as Snow.
* **Live database state**: same Snowflake account as Spider2-Snow.
* **Headline number**: Phase 28 FULL pending; pilot 10 4/10 exec_ok at Phase 28-revert-A.

### 4.3 Spider2-Lite-BQ

* **Split sizes**: 205 tasks.
* **On-disk paths**: `data/spider2_lite_bq/tasks/<task_id>/`.
* **Live database state**: hosted on BigQuery, accessed via the service-account JSON at `secrets/spider2_bq_sa.json`. The Spider 2 release ships with the public-dataset project IDs embedded in each task's `db.json`.
* **Headline number**: 30 % exec_ok plateau at Phase 22; unchanged through Phase 28 because the Phase 27 F1 grounding has not been ported to BQ.

### 4.4 Spider2-DBT

* **Split sizes**: 68 tasks.
* **On-disk paths**: `data/spider2_dbt/tasks/<task_id>/`. Each task contains a full dbt project skeleton (a `dbt_project.yml`, an upstream `seeds/` directory, an `models/` directory with the existing models the task should extend, and a `tests/` directory with the content tests the rubric runs).
* **Live database state**: a hybrid — some tasks target Snowflake (sharing credentials with Spider2-Snow), some target BigQuery (sharing credentials with Spider2-Lite-BQ). The target engine is recorded in each task's `dbt_project.yml`.
* **Headline number**: 13.2 % task success at Phase 25 (9 of 68); unchanged through Phase 28.
* **Notes**: The Spider2-DBT task directories are the largest on-disk artefacts in the dossier; the snapshot tarballs (e.g. `data/spider2_dbt/tasks/asana001/context/snapshot.tgz`) are committed to git as compressed archives. The `workspace_staging/` subdirectories under each task are the dbt working trees materialised at task time and are git-ignored.

## 5. Spider 2.0 leaderboards used for positioning

The leaderboard snapshots cited in [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md) and [07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md) are dated 2026-05-08 (one week before this dossier's compilation). The relevant positions:

* **Spider 2.0 Snow** — Genloop 96.70 (closed-source top), ReFoRCE+o3 62.89 (reproducible top), Spider-Agent + Qwen3-Coder 31.08 (open-weight ≤30B top).
* **Spider 2.0 Lite-BQ** — analogous tiering with closed-source frontier at ≈ 65 % and open-weight ≤30B at ≈ 32 %.
* **Spider 2.0 DBT** — closed-source frontier at ≈ 23 %, open-weight ≤30B at ≈ 14 %.

Re-validating against a later leaderboard requires fetching the live page at that later date; our compiled dossier uses the 2026-05-08 numbers as fixed reference points.

## 6. Database state and snapshot stability

Two of the four Spider 2.0 sub-benchmarks (Snow and Lite-Snow) depend on *live* database state — the Snowflake account hosts the actual tables that the gold and predicted SQL execute against. This introduces a reproducibility concern: if Snowflake's data drifts (a column is dropped, a table is re-loaded with different rows), the gold results change and the EX metric becomes non-stationary.

The Spider 2.0 authors mitigate this by versioning the Snowflake snapshot to the v2024-09 release. We verify snapshot stability before each major run by querying a small set of canary tables (defined in `outputs/snowflake/readiness/databases_visible.json`) and comparing row counts and a content hash against the recorded baseline. The Phase 28 FULL run was preceded by such a stability check on 2026-05-08 (the bridge-readiness check that lives at `outputs/snowflake/readiness/`); no drift was detected.

For BigQuery (Lite-BQ) and SQLite (Spider 1, BIRD), state stability is not a concern — BigQuery's public datasets are versioned by Google, and SQLite databases are static files.

The DBT lane's staging workspaces are created fresh per task and torn down at task end; their state is not persistent and cannot drift.

## 7. Re-fetch and bootstrap instructions

A reader wanting to reproduce the dossier numbers from scratch should:

1. Clone the dossier repository at the commit listed in [02_internal_phase_reports.md](02_internal_phase_reports.md) for the relevant figure.
2. Fetch the dataset releases at the upstream URLs listed above, verify checksums against `data/<benchmark>/CHECKSUMS.sha256`.
3. Install the pinned tooling versions in [03_tooling_and_software.md](03_tooling_and_software.md).
4. Provide credentials for Snowflake and BigQuery (the dossier does not ship credentials). Snowflake credentials require a Spider 2.0 access invitation from the upstream authors; BigQuery credentials require a service account with public-dataset read permissions.
5. Run the orchestration entry points in `tools/run_spider2_sequential_v24.py` for sequential pilots, or the per-benchmark runners under `tools/remote_scripts/` for full runs.
6. Compare results against the canonical `metrics.json` files indexed in [02_internal_phase_reports.md](02_internal_phase_reports.md) §3.

Step 4 is the operational bottleneck for external reproduction. The dossier records the methodology and numbers but cannot lower the credential barrier; Spider 2.0's design as a *real-world enterprise* benchmark intentionally requires real-world credentials.

## 8. License acknowledgements

* Spider 1.0 — CC BY-SA 4.0, Yu et al. (Yale University and collaborators).
* BIRD — CC BY-SA 4.0, Li et al. (HKUST, Alibaba DAMO).
* Spider 2.0 — Apache 2.0, Lei et al. (XLang AI consortium).
* Qwen3-Coder, Qwen2.5-Coder model weights — Qwen License (Alibaba), Apache 2.0-compatible for academic research use.

The dossier uses these resources strictly under their stated licenses for academic research. No redistribution of dataset files or model weights occurs in the dossier itself; the local mirrors are working copies for reproduction.
