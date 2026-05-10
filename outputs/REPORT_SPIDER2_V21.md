# Spider2 Phase 21 (STAGE A1: engine-compat rewrites + UNNEST alias trust) — report

_Generated: 2026-05-09 | branch: `experiments/denis` | author: Denis_

> **Scope of this session.** STAGE 0 baseline freeze + STAGE A1 of the
> brief: deterministic engine-compat fixes derived from
> Phase 20 v20a pilot50 traces. No model swap, no architecture
> change, no new lane. Two surgical patches:
>
> 1. **Renderer metric label normalisation** — planner-emitted aliases
>    like `Total Revenue` (with space) get snake_cased to
>    `Total_Revenue`. Kills all 11 Phase 20 parse_errors.
> 2. **Validator UNNEST/CTE/Lateral alias trust** — when a column
>    reference roots at an alias declared by `UNNEST(arr) AS x`, we
>    trust the alias resolution and skip pack residency check on the
>    inner struct fields (which we have no way to validate without
>    runtime types). Kills the GA4 `event_params/param.key` false
>    positive class.
>
> Stages A2 (join-aware), A3 (multi-CTE), A4 (renderer-feedback retry),
> B (Snow), C (Lite), D (DBT), E (premium overlay), F (FULL runs)
> remain deferred to subsequent sessions per the brief's stop rule.

---

## 1. Hard status

| component | value |
|---|---|
| Branch | `experiments/denis` |
| HEAD before Phase 21 | `643b230` (Phase 20) |
| HEAD after Phase 21 | `<commit>` (set on `git commit`) |
| Bridge / GPU / catalogs / models | ✅ same A100 80GB; both Qwen3-Coder-30B + Coder-7B still loaded |
| Push | NOT executed |

## 2. STAGE 0 — baseline freeze

Current best per lane prior to Phase 21:

| lane | run | n | plan_ok | sv | parse | exec | source |
|---|---|---:|---:|---:|---:|---:|---|
| Lite-BQ | `lite_bq_v18_1b_pilot50` | 50 | 42% | 52% | 96% | 46% | Phase 19 c9884ae |
| Lite-BQ | `lite_bq_v20a_pilot50_b` | 50 | 54% | 52% | 96% | 42% | Phase 20 643b230 |
| Lite-Snow | — | — | — | — | — | — | not piloted yet (catalog ready since Phase 18) |
| Lite-SQLite | — | — | — | — | — | — | not piloted yet |
| DBT FULL 68 | Phase 11 baseline | 68 | — | — | — | task_success 13.2% | only publishable Spider2 number |

## 3. STAGE A1 — what shipped

### 3.1 Patches

| module | line of attack | predicted impact |
|---|---|---|
| `sql_renderer_v18.py::render_bq` | metric label `re.sub(r'[^A-Za-z0-9_]+', '_', label).strip('_')` | kills 11 parse_errors |
| `candidate_selector_v18.py::schema_valid_against_pack` | walk Unnest/Lateral/TableFromRows nodes; collect TableAlias.columns identifiers; trust columns rooted at those aliases | kills GA4-style false-positive `col:event_params,col:param.key,...` leaks |

### 3.2 Local + on-bridge smoke

```
test 1 (metric label space):
  rendered: SELECT SUM(...) AS Total_Revenue ...
  parse_ok: True

test 2 (UNNEST alias trust):
  on-bridge: ok=True   (was False with leaks=col:key,col:value.int_value)

negative test (phantom column):
  ok=False leaks=col:phantom_col   (still rejected — alias trust does
  not over-shadow real residency check)
```

### 3.3 What was deliberately NOT done in this session

Per the brief's discipline of "одно семейство изменений за раз", I did
NOT in this commit:

- Multi-table reference fix (6 of 13 dry_run_failed in v20a are
  `unrecognized_name` from non-FROM tables) — that's STAGE A2 territory.
- Window-function + raw-column GROUP BY extension (2 dry_run_failed in
  v20a) — small fix but mixes with A1 attribution.
- Two-level UNNEST for ARRAY<STRUCT<ARRAY<STRUCT>>> (1 dry_run_failed) —
  needs renderer rework.
- Nested aggregate auto-rewrite (2 dry_run_failed) — would need WITH
  generation.
- AND signature on int operand (2 dry_run_failed) — needs type-aware
  expression rewrite.

If A1 alone moves the gate metrics, A2-A4 become incremental work on
the same harness. If A1 doesn't move the gate, the trace evidence
above is the ranked next-step punch list.

## 4. v21 BQ pilot10 sanity

`outputs/spider2_lite/runs/lite_bq_v21_pilot10/`

| metric | v18.1b | v20a (Phase 20) | **v21 (Phase 21)** |
|---|---:|---:|---:|
| plan_validation_ok | 0/10 | 5/10 | 5/10 |
| chosen_schema_valid | 3/10 | 4/10 | 4/10 |
| parse_ok | 9/10 | 9/10 | **10/10** ← +1 (metric-label-fix paid) |
| execute_ok (BQ dry_run) | 3/10 | 3/10 | 3/10 |
| chosen Family A | 6/10 | 7/10 | **8/10** ← +1 |
| chosen Family B | 4/10 | 3/10 | 2/10 |

A1 patches lifted parse_ok to 100% on pilot10 (the previously-failing
candidate had a `Total Revenue`-style alias that now becomes
`Total_Revenue`). Family A wins +1, schema_valid stable, execute_ok
stable.

## 5. v21 BQ pilot50 — FULL gate measurement

`outputs/spider2_lite/runs/lite_bq_v21_pilot50/`

| metric | v18.1b | v20a | **v21** | gate | status |
|---|---:|---:|---:|---|---|
| plan_validation_ok | 42% | 54% | 54% | — | unchanged vs v20a |
| chosen_schema_valid | 52% | 52% | **50%** | ≥ 60% | ❌ −2pp (noise band 50-52%) |
| parse_ok | 96% | 96% | **98%** | — | ✅ +2pp from metric label |
| execute_ok | 46% | 42% | **44%** | ≥ 50% | ❌ noise band 42-46% |
| Family A chosen | 80% | 82% | **86%** | — | +6pp vs v18.1b |
| Family B chosen | 20% | 18% | 14% | — | mirror |

**Gate composite (FULL precondition):**
- chosen_schema_valid ≥ 60%: ❌ **50%** (10pp short)
- dry_run_ok ≥ 50%: ❌ **44%** (6pp short)
- **FULL launch decision: NOT launched.**

### 5.1 The 4-session convergence

| session | sv | parse | exec |
|---|---:|---:|---:|
| Phase 19 v18.1b pilot50 | 52% | 96% | 46% |
| Phase 20 v20 pilot50 (canonicaliser only) | _not run as p50_ | _–_ | _–_ |
| Phase 20 v20a pilot50_b | 52% | 96% | 42% |
| **Phase 21 v21 pilot50** | **50%** | **98%** | **44%** |
| range | 50-52% | 96-98% | 42-46% |

Across **four sessions** of surgical patching (FQN canonicalisation,
dotted-path validator, pseudo-column whitelist, metric label normalise,
UNNEST/CTE/Lateral alias trust), the BQ pilot50 gate metrics moved
inside a 4pp band on schema_valid and a 4pp band on dry_run_ok. parse_ok
went 96% → 98%. **The bottleneck is decisively NOT in this class of
fixes.**

### 5.2 What's in the failing 28 chosen candidates (pilot50)

| error_class | count | cause class |
|---|---:|---|
| schema_invalid | 24 | mostly multi-table reference (planner refers to a table not in FROM) — STAGE A2 join-aware territory |
| bq_dry_run_failed | 13 | engine-compat (unrecognized_name, window+raw GROUP BY, multi-level UNNEST, nested aggregate, AND-signature) |
| parse_error | 1 | residual edge case |
| chosen-OK | 12 | the 22 dry_run_ok wins minus 10 that also passed sv |

The 24 schema_invalid + 13 dry_run_failed = 37 of the 50 tasks fail
end-to-end on patterns that A1 surgical patches don't reach. STAGE A2
(join-aware deterministic rendering) addresses the dominant class
(multi-table unrecognized_name).

## 6. STAGE A6 — oracle-table diagnostic

Per the brief's STAGE A6 ("oracle-table diagnostic-only special setting"
to separate retrieval-bound from planning-bound failures), this
session does NOT run oracle-table mode. Reason: oracle-table mode
requires a separate code path in the schema linker (skip retrieval,
inject pack from `gold_columns` field of Spider2 task records) that
I have not yet built. STAGE B of the brief explicitly asks for it
on Snow first; for BQ it's deferred to v21.1.

## 7. Honest gate decisions + next stage handoff

**FULL gate not cleared.** Per the brief's stop rule, no FULL launch
on hope-driven grounds.

The decisive next-step lever, based on the trace evidence in §5.2 and
4 sessions of measurement, is **STAGE A2: join-aware deterministic
rendering** plus its prerequisite — `pack.join_hints` population from
catalog co-occurrence / FK signals. A2 directly attacks the 24
schema_invalid bucket, which is dominated by multi-table reference
patterns the single-table renderer cannot express.

Defer to v21.1 / next session:
- STAGE A2: graph closure around top tables, bridge-table expansion,
  deterministic JOIN renderer.
- STAGE A3: multi-CTE Family C for WITH patterns.
- STAGE A4: renderer-feedback retry on `dry_run_failed` (use the
  exact engine error class).
- STAGE B-D-E-F: Snow lane, Lite-SF/SQLite officialisation, DBT v2
  agent, premium overlay, FULL runs.

**Independent track that does NOT depend on A2** and could run in
parallel: Snow oracle-table diagnostic pilot10 (STAGE B1). Snow live
catalog has been on disk since Phase 18; only a Snow runner stub plus
oracle-mode pack-injection path are needed to measure
retrieval-bound vs planning-bound on Snow.

## 8. ВКР-disciplined claims

What this Phase 21 commit may contribute to ВКР:
- Honest engineering chronology of the v18 stack: 4 named patches
  across 3 sessions (Phase 19 v18.1b, Phase 20 STAGE A1 canonicalise,
  Phase 21 metric label + UNNEST trust) with explicit pilot10/pilot50
  metric deltas.
- The v20a → v21 metric move is a clean attribution of two surgical
  validator/renderer fixes. Either it closes the FULL gate or it
  surfaces the next bottleneck class concretely.

What MUST NOT go in:
- Pilot10/pilot50 numbers as benchmark headlines.
- Any FULL claim — no FULL run launched in this commit.
- DBT FULL 68 = 13.2% remains the only publishable Spider2 number.

## 9. Operational status

- v16/v17 modules untouched.
- Patched in this commit: `sql_renderer_v18.py` (metric label),
  `candidate_selector_v18.py` (alias trust).
- Live catalogs unchanged.
- No `git push`.
