# Spider2-DBT task taxonomy plan

_Used by Phase 0 to label all 68 tasks. Each label drives prompt
policy, expected solution pattern, and error-bucket mapping.
Taxonomy is task-shape based (what kind of edit gold expects), not
domain based — domains (asana, playbook, retail, …) are orthogonal._

## Buckets

### 1. `patch_existing_model`

**Definition.** Gold expects an existing model file in `models/` to be modified. The file is non-empty in upstream and the gold answer is a *small* delta: add columns, fix joins, fix aggregation grain, add filter.

**Detection rules.**
- Gold's `condition_tabs[0]` corresponds to a `models/<table>.sql` that exists in upstream.
- File body in upstream is non-trivial (>100 chars, has SELECT statement).
- gold col indices are within `[0, len(upstream cols) + 5)`.

**Expected solution pattern.** Unified diff against the named file, ≤20 lines added.

**Common failure modes.**
- Model invents a new file instead of patching.
- Diff applied but introduced columns reference non-existent upstream columns.
- Diff added columns in wrong order (gold matches by index).

**Best prompt policy.** V4/V5 (diff-form, strict).

**Examples (preliminary, to be confirmed in Phase 0):** lever001, playbook001, asana001 (partial), retail001 (some).

---

### 2. `fill_stub_model`

**Definition.** Gold expects a model file that already exists in upstream as a stub (empty / one-line / TODO comment). The upstream project's other models are wired to depend on it; we just need to populate the stub.

**Detection rules.**
- `models/<target>.sql` exists in upstream.
- Body is < 100 chars OR contains "TODO" / "stub" / "placeholder".
- Other models contain `{{ ref('<target>') }}`.

**Expected solution pattern.** Diff replacing the stub body. ≤40 lines.

**Common failure modes.** Same as `patch_existing_model` plus: missing the upstream `ref` chain that calls the stub.

**Best prompt policy.** V4/V5 with explicit "this file is a stub; populate it" hint.

**Examples (preliminary):** playbook001 attribution_touches.

---

### 3. `create_new_model`

**Definition.** Gold expects a model file that does NOT exist in upstream. The agent must create it from scratch with a name matching the project convention (e.g. `<src>__<entity>` for fivetran-style packages).

**Detection rules.**
- `models/**/<target>.sql` not in upstream.
- Other final models follow a clear naming convention (e.g. all start with `asana__` or `lever__`).
- `condition_cols` length is small enough to be a fresh model (≤10).

**Expected solution pattern.** Full SQL block with `path=models/<convention-matching-name>.sql`. ≤80 lines.

**Common failure modes.** Wrong name (gold matches name + columns); wrong upstream refs; wrong grain.

**Best prompt policy.** V5 with explicit `<<NEW_FILE>>` tag flow + planner-determined name.

**Examples (preliminary):** asana001 (asana__team / asana__user).

---

### 4. `fix_ref_or_source`

**Definition.** Gold expects a small fix that swaps a `{{ ref('A') }}` → `{{ ref('B') }}` or `{{ source('s','t') }}` reference, perhaps because the upstream is broken. No new logic.

**Detection rules.**
- Existing model body compiles incorrectly (compile error mentions ref/source not found).
- Diff between upstream-as-is and gold-passing run is essentially a single-token replacement.

**Expected solution pattern.** 1-line diff.

**Common failure modes.** Model rewrites the whole logic instead of one swap.

**Best prompt policy.** V5 + planner emits `action_type=fix_ref_or_source` and the SQL prompt becomes "find and replace the broken ref".

---

### 5. `grain_aggregation`

**Definition.** Gold expects a specific aggregation grain (e.g. monthly per project, not daily total). The model must group by the right keys.

**Detection rules.** Question text contains "per <X>" / "for each <Y>" / "monthly" / "yearly" / "by <Z>".

**Expected solution pattern.** Patch existing or new model with explicit `GROUP BY` and matching column shape.

**Common failure modes.** Right columns, wrong grain (whole-period totals instead of per-period rows).

**Best prompt policy.** Planner must declare `expected_grain` explicitly; output-shape pre-check rejects the candidate if it doesn't satisfy the declared grain.

---

### 6. `join_semantics`

**Definition.** Gold expects a particular join (left vs inner, multiple joins, anti-join). The columns are right but the rows aren't because of a join error.

**Detection rules.** Question text contains "exclude X" / "but not Y" / "where also" / "regardless of".

**Expected solution pattern.** Patch existing model with corrected join clause.

**Common failure modes.** INNER vs LEFT mismatch; missing join filter; cartesian on poorly-keyed tables.

**Best prompt policy.** V4 + planner emits explicit join hint in `acceptance_checks`.

---

### 7. `date_time_semantics`

**Definition.** Gold's columns are date/time computed from raw timestamps; the model must compute days_diff / month_truncation / first_visit_date correctly.

**Detection rules.** Question contains "days between" / "average X time" / "first/last <Y>" / "ending on <DATE>" / "monthly".

**Expected solution pattern.** Use DuckDB date functions: `DATEDIFF('day', a, b)`, `DATE_TRUNC('month', d)`, `EXTRACT(YEAR FROM d)`.

**Common failure modes.** BigQuery `DATE_DIFF` syntax (wrong arg order for DuckDB); `STRFTIME` (Postgres-only), `DATEDIFF(DAY, ...)` Snowflake order; ambiguous timestamps without timezone.

**Best prompt policy.** V4 + DuckDB-specific date rules in the prompt's RULES block (already present).

---

### 8. `nested_json_list_struct`

**Definition.** Sources contain JSON / ARRAY columns (rare in DBT lane but exists for some packages).

**Detection rules.** Schema has `STRUCT` / `LIST` / `JSON` types, or upstream model body uses `JSON_EXTRACT` / `UNNEST`.

**Expected solution pattern.** Use DuckDB's `UNNEST(arr) AS x` and `JSON_EXTRACT(col, '$.path')`.

**Common failure modes.** BigQuery `UNNEST` semantics (different); Snowflake `LATERAL FLATTEN` (not DuckDB); type-coerce errors.

**Best prompt policy.** V4 + DuckDB rules + sample row preview from DuckDB.

---

### 9. `schema_yml_contract`

**Definition.** Gold's "table match" passes only when the column names + types follow a `schema.yml` declaration (e.g. test expects `unique` on column `id`; without that, dbt test fails).

**Detection rules.** Upstream's `schema.yml` block has tests that the upstream model violates; gold-passing run requires those columns to be the right type.

**Expected solution pattern.** Patch model + maybe patch `schema.yml` to declare tests.

**Common failure modes.** Patches model but ignores schema.yml; column types differ.

**Best prompt policy.** V4 + planner emits `action_type=edit_schema_yml` separately.

---

### 10. `macro_or_config`

**Definition.** Gold-passing requires touching a macro file or `dbt_project.yml` config (e.g. enable a package's variable).

**Detection rules.** `dbt_project.yml` has a `vars:` block where the value matters; or `models/<name>.sql` references a macro `{{ <pkg>.<macro>(...) }}` whose behaviour depends on a var.

**Expected solution pattern.** Diff against `dbt_project.yml` or a macro file.

**Common failure modes.** Generates SQL that bypasses the macro; or modifies SQL but the var still controls behaviour.

**Best prompt policy.** Phase 6+ (multi-candidate, one of which is a config diff).

---

### 11. `upstream_project_issue`

**Definition.** The upstream example project as shipped has bugs (substituted-source-identifier failures, like asana001's 21 dbt test errors). The agent's edit cannot succeed because the project itself is broken.

**Detection rules.** `dbt run` on the unmodified upstream produces compile errors; `dbt test` fails on > 5 tests on the unmodified upstream.

**Expected solution pattern.** Either (a) skip in dev set with a `floor_marker=upstream_broken` flag, or (b) the agent must fix the upstream issue first — usually out of scope for a one-shot prompt.

**Common failure modes.** Agent's good edit is hidden by upstream failures.

**Best prompt policy.** Tag and exclude from primary metrics; track separately.

**Examples (preliminary):** asana001 has this property (21 ERROR tests pre-existing).

---

### 12. `evaluator_artifact_mismatch`

**Definition.** Even with correct logic, the artifact path / table name shape doesn't match what the evaluator expects.

**Detection rules.** Gold's `parameters.gold` is a `.duckdb` file with specific tables; upstream's `dbt_project.yml` materializes models under different names than gold expects.

**Expected solution pattern.** Configure `dbt_project.yml` `models:` block to materialize under the gold-expected name; OR add an alias.

**Common failure modes.** Right rows in wrong-named table → 0/1.

**Best prompt policy.** Planner emits `target_file` + `target_alias` and the apply step adds `{{ config(alias='...') }}` if mismatched.

---

### 13. `unclear` / `unsupported`

**Definition.** Question is ambiguous or requires capabilities outside one-shot DBT (e.g. requires reading external doc files, multi-stakeholder context).

**Detection rules.** Question is < 20 words AND references concepts not in the example dir; OR question requires LLM reasoning over a domain document not provided.

**Expected solution pattern.** None — these tasks are out of scope for the diploma's main scoring; tag and exclude.

## Per-bucket fallback table (used by Phase 1)

| Bucket | Floor (V0) expected | Best prompt | Predicted matched on dev_20 |
|---|---:|---|---:|
| patch_existing_model | low (~10%) | V5 | high (~50%) |
| fill_stub_model | very low | V5 + stub hint | high |
| create_new_model | very low | V5 + new-file tag | medium |
| fix_ref_or_source | very low | V6 (planner) | medium |
| grain_aggregation | very low | V6 + shape check | medium |
| join_semantics | very low | V6 | medium-low |
| date_time_semantics | very low | V4 + DuckDB rules | medium |
| nested_json_list_struct | very low | V4 + sample preview | low |
| schema_yml_contract | low | V6 + edit_schema_yml | low |
| macro_or_config | low | V9 (multi-candidate) | low |
| upstream_project_issue | varies | tag, exclude from primary | n/a |
| evaluator_artifact_mismatch | medium | V6 + alias | medium |
| unclear | n/a | tag, exclude | n/a |

(Numbers are subjective priors; Phase 0 adjusts them with measured floor and current-V4 numbers.)

## Phase 0 deliverable

`outputs/spider2_dbt/task_taxonomy.csv` with columns:

```
instance_id, gold_target_table, primary_bucket, secondary_buckets,
upstream_compile_ok, upstream_test_pass, upstream_test_fail,
floor_score, v4_score (from ablation_main if available),
notes
```

Plus `outputs/spider2_dbt/dev_holdout_split.json`:

```json
{
  "smoke": ["asana001", "playbook001", "retail001",
             "recharge002", "xero001", "lever001"],
  "dev_20": ["..."],
  "holdout_30": ["..."],
  "stratification_check": {
    "patch_existing_model": {"smoke": 3, "dev_20": 7, "holdout_30": 9},
    "fill_stub_model":      {"smoke": 1, "dev_20": 4, "holdout_30": 4},
    ...
  }
}
```

Stratification rule: each bucket's representation in dev_20 should be ≥ 1 if it has any item, and ≥ 2 if it has ≥ 4 items in the full set.
