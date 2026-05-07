# Spider2 v8 — scientific findings (PILOT data)

_Generated: 2026-05-08 | branch experiments/denis_

> All findings below are derived from PILOT runs (limit ≤ 3). They are
> hypotheses to validate, not benchmark claims. FULL data is required
> before any scientific conclusion can be published.

## Methodology guard-rails (already enforced in code)

1. **No mixing of benchmarks.** Spider2-Snow / Spider2-Lite /
   Spider2-DBT each have separate runner CLI, separate output trees,
   separate metric tables. The unified report keeps three rows in the
   master matrix and explicitly tells readers not to average.
2. **No mixing of lanes.** Spider2-Lite is **lane-aware**: BQ, SF,
   SQLite are reported separately. SQLite is flagged
   `non_comparable=True` in every output.
3. **Diagnostic vs ranking.** No "ground-truth-table" or oracle-table
   path is enabled in v8 runners. If we add it later it must live
   under a separate `_diagnostic_v8.py` module and be excluded from
   the master matrix.
4. **Honest pilot vs full.** Pilot results are explicitly labeled and
   never used for "official" claims. The master matrix has a `status`
   column that reads `PILOT_only_FULL_deferred` until FULL is run.

## Hypotheses raised by the PILOT data

### H1 — Coder-7B has a strong BigQuery-syntax prior even when prompted for Snowflake
PILOT Snow n=3: 2/3 chosen candidates failed `wrong_dialect` (BQ
backticks emitted despite the explicit 12-rule SF prompt). The
post-processor that auto-rewrites backticks to double-quotes would
likely flip those tasks to `parses` at zero compute cost.

### H2 — Snowflake column-case sensitivity is the second-largest error class
1/3 SF tasks died on `invalid identifier 'PUBLICATION_DATE'`; the
schema metadata uses lowercase `publication_date`. The agent currently
renders the case from `render_subset(...)` but the model still emits
uppercase. Pre-normalizing identifier case to match the schema or
double-quoting risky names is a candidate fix.

### H3 — V4 (diff-form) holds up beyond the 6-task ablation
Spider2-DBT v8 PILOT 1: `playbook001` succeeded with score 1/1, dbt
run_rc=0, dbt test_rc=0. Consistent with the n=6 ablation result
(commit 8f57eea: V4 helpful=1 / harmful=0). To validate the hypothesis,
FULL 68 with V4 vs V0_floor must be paired-tested.

### H4 — Lane router routes 100% correctly on Spider2-Lite
PILOT 1+1+1: bq → A_bq, sf → A_sf, local → C_sqlite_stub.
The router is already deterministic by `instance_id` prefix; no
hypothesis needed, but the PILOT confirms the dispatch.

## Validation plan for FULL runs

- Spider2-DBT FULL 68: paired McNemar V4 vs V0_floor on 68 tasks.
  Stratify by primary_bucket (taxonomy already at
  `outputs/spider2_dbt/task_taxonomy.csv`).
- Spider2-Lite FULL 547: per-lane BCa-bootstrap 95% CI on parse_ok /
  execute_ok / EX. SQLite lane explicitly excluded from EX claims.
- Spider2-Snow FULL 547: same as Lite-SF lane but on the canonical
  spider2-snow.jsonl (must be downloaded before run).

## Cost projection

| benchmark | candidates × n × ~20s | est. wall |
|---|---|---|
| Spider2-Snow FULL 547 | 5 × 547 × 20s | ~15h naive; ~3.5h after cutting to 3 candidates |
| Spider2-Lite FULL 547 | mixed lanes; SF/BQ have I/O latency too | ~9–10h |
| Spider2-DBT FULL 68 | 1 × 68 × ~50s | ~1.5h |

