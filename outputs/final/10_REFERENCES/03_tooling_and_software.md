# Tooling and Software — External Dependencies

This file enumerates the third-party software the system depends on, with pinned versions and the role each component plays in the architecture. External research references in [01_research_dossier_references.md](01_research_dossier_references.md), internal artefacts in [02_internal_phase_reports.md](02_internal_phase_reports.md), datasets in [04_datasets_and_benchmarks.md](04_datasets_and_benchmarks.md).

Pinning convention: where a package version is load-bearing for a specific behaviour (a bugfix release, a new feature we depend on, a backwards-incompatible API change we are insulated against), the exact pin is recorded with the reason. Where a package is functionally fungible across recent versions (a logging library, a path utility), the recorded version is the one used in the published runs and is not asserted as load-bearing.

## 1. Model runtime and inference

### 1.1 Hugging Face transformers

* **Package**: `transformers` (Wolf et al. 2020).
* **Version pin**: 4.45.2. Pinned because newer releases changed the `model.generate()` token-streaming callback signature in a way that breaks our resume-from-Drive trigger. We tested up to 4.48.0 at Phase 26 and saw no benefit; the upgrade is deferred until Phase 31.
* **Role**: Inference backend for both planner (Qwen3-Coder-30B-A3B) and emitter (Qwen2.5-Coder-7B). Configured with `torch_dtype=torch.bfloat16`, `device_map="auto"`, and a custom decode loop that flushes tokens to disk every 256 tokens for resume safety.
* **Notes**: We deliberately did not adopt vLLM despite its better throughput; the resume scaffolding for our long-running Colab sessions is built against transformers' streaming callbacks and would not port directly.

### 1.2 PyTorch

* **Package**: `torch`.
* **Version pin**: 2.4.1+cu121. Pinned for CUDA 12.1 compatibility with the Colab A100 runtime.
* **Role**: GPU kernels and tensor operations for transformers. The `torch.cuda.empty_cache()` + `gc.collect()` pattern we use in [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md) is the canonical pattern for recovering from CUDA OOM events.

### 1.3 BitsAndBytes (NOT used)

* Considered for 4-bit quantisation of the 30B planner at Phase 17; the latency overhead from dequantisation per generation step was higher than the memory budget gain. Recorded here as an explicitly rejected dependency.

## 2. SQL parsing and transpilation

### 2.1 SQLGlot

* **Package**: `sqlglot` (Mao 2024).
* **Version pin**: 25.16.1. Load-bearing for two specific behaviours: (a) `DATE_TRUNC` parses as `exp.TimestampTrunc` in the snowflake dialect — this was a Phase 28 discovery and is checked by `hasattr(exp, 'TimestampTrunc')` in the F4 wrapper code; (b) LATERAL FLATTEN occasionally fails to parse, which is why the F4c regex fallback exists. Upgrading SQLGlot may close the LATERAL FLATTEN parse gap; this is a Phase 29 candidate.
* **Role**: AST manipulation for the F1 identifier guard ([08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md](../08_CUSTOM_TOOLS/05_snow_identifier_guard_v27.md)) and the F4 date-cast wrapper ([08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md](../08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md)). Also used in lighter form by the v18 validator for SELECT-alias protection.
* **Notes**: SQLGlot is one of the few libraries in the stack where the version pin is genuinely load-bearing — the AST node types we case-match against are part of the public API but evolve across releases.

### 2.2 SQLParse (fallback only)

* **Package**: `sqlparse`.
* **Version pin**: 0.5.1. Not load-bearing.
* **Role**: Tokenisation in the regex fallback path of the identifier guard when SQLGlot fails to parse. Phase 28 F4c uses sqlparse's token-stream to identify the LATERAL FLATTEN pattern without requiring a full AST.

## 3. Database engine adapters

### 3.1 Snowflake Connector for Python

* **Package**: `snowflake-connector-python`.
* **Version pin**: 3.12.2. Pinned because the 3.13.x line changed the result-set iteration to lazily fetch by default, which broke our row-count check in the exec_ok validator. The downgrade to 3.12.2 restored eager fetching.
* **Role**: Connection lifecycle, query execution, result-set retrieval, and the catalog-probe queries used in Phase 28 F2a falsification. The connection-restore pattern for kernel recovery (Section 2a of the bringup memory file) calls `snowflake.connector.connect()` directly with credentials loaded from `secrets/snowflake.json`.

### 3.2 Google BigQuery Python Client

* **Package**: `google-cloud-bigquery`.
* **Version pin**: 3.25.0. Not load-bearing — any 3.x release with `dry_run=True` support works.
* **Role**: BigQuery query execution and dry-run validation for Spider2-Lite-BQ. The dry-run mode is the basis of the `dry_run_ok` metric.

### 3.3 SQLite

* **Package**: stdlib `sqlite3`, plus the BIRD-bundled SQLite databases.
* **Version pin**: SQLite 3.45 (Python stdlib bundled).
* **Role**: Spider 1.0 and BIRD execution engine. The SQLite databases ship with the benchmark releases and are not re-fetched; their checksums are recorded in [04_datasets_and_benchmarks.md](04_datasets_and_benchmarks.md).

## 4. dbt and project-level tooling

### 4.1 dbt-core

* **Package**: `dbt-core`.
* **Version pin**: 1.8.4. Spider2-DBT's release notes specify dbt 1.8.x as the reference version; we pin to .4 because earlier .x releases had a parse bug that affected one of the 68 tasks.
* **Role**: `dbt parse`, `dbt compile`, `dbt run`, and `dbt test` against the staging workspace for each DBT task. The grading rubric reads dbt's output tables directly.

### 4.2 dbt-snowflake

* **Package**: `dbt-snowflake`.
* **Version pin**: 1.8.3. Compatible with dbt-core 1.8.4.
* **Role**: Snowflake adapter for dbt. Required because the Spider2-DBT staging workspace materialises against the same Snowflake account used by Spider2-Snow.

### 4.3 dbt-bigquery

* **Package**: `dbt-bigquery`.
* **Version pin**: 1.8.2.
* **Role**: BigQuery adapter for dbt. Used for the subset of Spider2-DBT tasks whose staging workspace is BigQuery rather than Snowflake.

## 5. Information retrieval and schema linking

### 5.1 rank_bm25

* **Package**: `rank-bm25`.
* **Version pin**: 0.2.2. Not load-bearing.
* **Role**: BM25 scoring for the schema linker ([08_CUSTOM_TOOLS/03_schema_linking_v18.md](../08_CUSTOM_TOOLS/03_schema_linking_v18.md)). The per-task BM25 partition introduced in Phase 27 F1 wraps this library; the partition logic is in our code, not the library.

### 5.2 NLTK (tokenisation only)

* **Package**: `nltk`.
* **Version pin**: 3.9.1.
* **Role**: Stop-word filtering and basic tokenisation for the BM25 input. We do not use any of NLTK's heavier NLP features.

## 6. Data handling and serialisation

### 6.1 Pandas

* **Package**: `pandas`.
* **Version pin**: 2.2.2.
* **Role**: Used in result-set comparison for the EX metric (constructing canonical-ordered DataFrames from gold and predicted SQL outputs) and in the per-DB breakdown computations.

### 6.2 JSONLines

* **Package**: `jsonlines`.
* **Version pin**: 4.0.0.
* **Role**: Reading and writing the `predictions.jsonl` and `traces.jsonl` files. The append-mode + periodic-close pattern that fixes the Drive FUSE sync issue ([08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md) §4) is implemented against this library.

## 7. Infrastructure and orchestration

### 7.1 Cloudflare Tunnel (cloudflared)

* **Tool**: `cloudflared`.
* **Version pin**: latest stable as of each session; not pinned because Cloudflare manages the binary.
* **Role**: Exposes the Colab Jupyter kernel's local Flask bridge as a publicly-resolvable HTTPS URL. The agent reads `tools/.bridge_url` to discover the current tunnel and POSTs `/exec` calls to it. The bridge has the 502-on-large-payload limitation documented in [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md) §3.

### 7.2 Google Drive FUSE

* **Tool**: Colab's bundled `drive.mount()`.
* **Role**: Mounts the project root at `/content/drive/MyDrive/diploma_plan_sql`. The FUSE sync delay is the root cause of the 79-unsynced-tasks incident documented in the Phase 28 closure report; the fix is the periodic `pf.close() + reopen` pattern in [tools/remote_scripts/_phase27_snow_runner.py](../../../../tools/remote_scripts/_phase27_snow_runner.py).

### 7.3 Flask (bridge)

* **Package**: `flask`.
* **Version pin**: 3.0.3. Not load-bearing.
* **Role**: Implements the `/exec` and `/health` endpoints that the cloudflared tunnel exposes. The bridge runs as a background process inside the Colab kernel and shares globals with `__main__` only via the `_SHARED_GLOBALS` dict (this is the indirection that caused the "models missing from `__main__`" recovery incident).

### 7.4 Custom run-time scripts

* **`tools/exec_remote.py`** — agent-side client for posting `/exec` calls to the bridge.
* **`tools/run_spider2_sequential_v24.py`** — orchestration entry point for sequential pilot/full runs. Documented in [04_ARCHITECTURE/09_orchestration.md](../04_ARCHITECTURE/09_orchestration.md).
* **`tools/remote_scripts/_phase27_snow_runner.py`** — main Snow lane runner (≈ 620 LOC). Includes resume scaffolding, periodic flush, supervisor heartbeats. Underpins [05_PIPELINES/04_spider2_snow_pipeline.md](../05_PIPELINES/04_spider2_snow_pipeline.md).
* **`tools/remote_scripts/_run_dbt_inference.py`** — DBT lane runner. Documented in [05_PIPELINES/05_spider2_dbt_pipeline.md](../05_PIPELINES/05_spider2_dbt_pipeline.md).
* **`spider2_dbt_bridge/run_dbt_ablation.py`** — DBT-specific orchestration with the staging-workspace lifecycle. Phase 31's dbt-parse pre-check will extend this file.

These run-time scripts are part of the dossier's artefact set; their internal architecture is documented in the [04_ARCHITECTURE/](../04_ARCHITECTURE/) and [05_PIPELINES/](../05_PIPELINES/) sections.

## 8. Development environment

* **Python**: 3.11.10 on the Colab runtime, 3.11.6 on the local development machine. The dossier's claims are robust to minor Python version drift within 3.11.x; the inference scripts will run on 3.10.x and 3.12.x without modification.
* **OS**: Linux 5.15 in Colab; Windows 11 on the local development machine. The development-machine paths use Windows separators (`D:\HSE\Диплом\...`) for the dossier files; the Colab paths use POSIX. The bridge insulates the agent from this distinction.
* **CUDA**: 12.1 on Colab. The 30B planner requires bf16 on an A100 80 GB or equivalent; the 7B emitter runs comfortably on smaller GPUs but is co-located on the A100 in our setup.

## 9. License and provenance notes

All packages listed above are open-source under permissive licenses (Apache 2.0, MIT, BSD-3-Clause). The dossier does not redistribute any of them; the pinned versions are installed at session start from PyPI. The Spider 2.0 dataset is released under the Apache 2.0 license; the BIRD dataset is released under CC BY-SA 4.0; Spider 1.0 is released under CC BY-SA 4.0. Dataset license details are in [04_datasets_and_benchmarks.md](04_datasets_and_benchmarks.md).

The Qwen3-Coder and Qwen2.5-Coder models are released under the Qwen License (Apache 2.0-compatible for non-commercial research use up to 100M monthly active users). Our use is for academic thesis research and falls within the license terms. No model weights are redistributed by the dossier; they are downloaded from Hugging Face Hub at session start.
