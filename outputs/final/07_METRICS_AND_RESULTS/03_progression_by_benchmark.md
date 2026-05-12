# Progression by Benchmark — Per-Lane Trajectories

This document zooms into each of the six benchmark lanes individually, presenting an ASCII progression chart, the three to five inflection points that shaped its trajectory, the plateau (or absence of one) at the end of Phase 28, and the next planned intervention. The aggregate table that this document drills into lives at [02_progression_table_full.md](02_progression_table_full.md); metric definitions at [01_metric_definitions.md](01_metric_definitions.md).

A standardised convention is used: each row in the per-benchmark chart shows one phase, the bar visualises Execution Accuracy (`exec_ok` / N), and the number to the right of the bar gives that rate as a percentage. Bars use one `█` block per 4 percentage points. `░` blocks pad to a constant 25-block width so plateaus are immediately visible.

---

## 1. Spider 1.0 — Classical Saturation

```
Phase  3 (v3, baseline):         ███████░░░░░░░░░░░░░░░░░░  29.4%
Phase  7 (v7 schema linking):    █████████████░░░░░░░░░░░░  53.1%
Phase 12 (v12 emitter swap):     █████████████████░░░░░░░░  68.0%
Phase 16 (v16 retry):            ████████████████████░░░░░  82.1%
Phase 19 (v18 closed-set):       ██████████████████████░░░  91.5%
Phase 22 (planner+emitter mix):  ███████████████████████░░  94.0%
Phase 27 (no regression):        ███████████████████████░░  94.0%
Phase 28 (no regression):        ███████████████████████░░  94.0%
```

**Inflection points.** (1) The jump from 29.4 % at v3 to 53.1 % at v7 reflects the introduction of schema linking as a first-class stage rather than free-form prompting. (2) The 53.1 → 68.0 lift across v7-v12 came from swapping the emitter from a smaller 1.5 B model to Qwen2.5-Coder-7B, which proved that for classical SQLite-style grammar the emitter, not the planner, is the bottleneck. (3) The 82.1 → 91.5 jump at v18 reflects the closed-set planner that constrains the planner to schema-derived candidate columns and forces it to commit to a small, validated table set rather than free-form join inference. (4) The 91.5 → 94.0 lift at Phase 22 came from the planner/emitter family mix (Qwen3-Coder-30B-A3B planner + Qwen2.5-Coder-7B emitter) that has remained stable since.

**Plateau.** Spider 1 saturates at 94.0 % for the same reasons the published 92–95 % cluster of comparable open-weight systems saturates: the residual six points are dominated by gold-label ambiguity, multiple-valid-SQL cases that the EX metric counts as wrong, and a tiny tail of genuinely hard queries that need either real-world commonsense or external data. Adding more retries does not move the needle here; we measured a saturation gap of < 0.5 pp between three-shot and ten-shot at v22.

**Next intervention.** None planned. Spider 1 is treated as a regression-only lane: every phase regenerates it to confirm no new patch silently regresses the easy benchmark. The 94.0 % number is frozen as the publication reference.

---

## 2. BIRD — Real-World SQL with Evidence

```
Phase  5 (v5 baseline):          ██████░░░░░░░░░░░░░░░░░░░  24.7%
Phase  9 (v9 evidence prompt):   ███████████░░░░░░░░░░░░░░  44.8%
Phase 14 (v14 plan + retry):     ████████████████░░░░░░░░░  64.1%
Phase 18 (v18 closed-set):       █████████████████████░░░░  82.6%
Phase 22 (mix + tuned retries):  ██████████████████████░░░  87.9%   (FULL)
Phase 22 (mini-dev split):       ██████████████████████░░░  90.4%   (mini-dev)
Phase 27 (no change):            ██████████████████████░░░  87.9%
Phase 28 (no change):            ██████████████████████░░░  87.9%
```

**Inflection points.** (1) The 24.7 → 44.8 step at v9 came from passing BIRD's gold `evidence` field as an explicit instruction block rather than tucking it into the schema preamble. The evidence rows often contain numeric encodings, lookup keys, or hidden aliases without which the closed-set planner makes plausible but wrong column choices. (2) The v9 → v14 step embeds two ideas: a plan-then-emit decomposition and a one-shot retry with the validator's error rendered as a natural-language hint. (3) The v14 → v18 step is the same closed-set planner that helped Spider 1; on BIRD the relative lift is even larger because BIRD's schemas are wider and free-form join inference fails more often. (4) The split between 87.9 % FULL and 90.4 % mini-dev quantifies a known dataset-curation effect: the mini-dev set is enriched for tractable questions; the FULL set retains harder long-tail items.

**Plateau.** Like Spider 1, BIRD has saturated for our architecture. Residual failures cluster around three categories: (a) evidence rows that reference column values not in the schema header, requiring catalog probing we have not yet built for SQLite/BIRD; (b) numeric-precision quirks that change `=` to `≈` semantically; (c) a long tail of multi-aggregate questions where the gold solution uses a window-function pattern that the closed-set planner does not propose.

**Next intervention.** None planned for Phase 29-30. BIRD is treated, like Spider 1, as a regression lane. A speculative Phase 32 idea is to port the Phase 27 grounding apparatus (per-DB BM25 partition, identifier guard) to BIRD, where it should help the long tail of join-inference errors — but only after the Spider 2 lanes settle.

---

## 3. Spider2-Lite-BQ — Plateau Diagnostic

```
Phase 15 (v15 first BQ attempt):  ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 17 (v17 model-swap pilot):  ██░░░░░░░░░░░░░░░░░░░░░░░  10.0%
Phase 18 (v18 schema-first):      ███████░░░░░░░░░░░░░░░░░░  30.0%
Phase 19 (v19 repair sprint):     ███████░░░░░░░░░░░░░░░░░░  30.0%
Phase 20-22 (A1/A2/A3 stages):    ███████░░░░░░░░░░░░░░░░░░  30.0%
Phase 23 (FULL diagnostic):       ██░░░░░░░░░░░░░░░░░░░░░░░   6.8%   (14/205 partial)
Phase 24 (A4 metric-neutral):     ███████░░░░░░░░░░░░░░░░░░  30.0%
Phase 27-28 (no Snow regression): ███████░░░░░░░░░░░░░░░░░░  30.0%   (pilot 10)
```

**Inflection points.** (1) v15 → v17 confirmed that the 0 % baseline on Spider 2 is not a model-capacity issue — model swaps brought the rate from 0 to 10 % but no further. (2) v17 → v18 (schema-first pivot) delivered the bulk of the BQ progress in one phase: the closed-set planner with live catalog probing reached 30 %. (3) Phases 19–22 each promised additional lift via repair patches, identifier canonicalisation, join-aware planning, and Family C templates, but the gains were ≤ 4 pp per phase and never compounded — the pack-thinness audit at Phase 22 predicted +20 pp from STAGE A3, observed +4 pp. (4) Phase 23 attempted a FULL Lite-BQ + Snow run concurrently and produced a partial 14/205 = 6.8 % result that should not be quoted as a final number — it is a diagnostic against concurrent GPU contention, not a benchmark figure.

**Plateau.** Spider2-Lite-BQ has been at ≈ 30 % since Phase 19. The Phase 22 audit identified the remaining gap as STAGE A4 territory: engine-compat fixes for BigQuery-specific constructs (`ARRAY_EXISTS`, `OFFSET(0)`, multi-CTE chains) where the emitter writes Snowflake-flavoured SQL even when prompted otherwise. Phase 24 implemented a metric-neutral A4 rewrite layer that fixed three superficial dialect issues without unlocking any new tasks. The plateau is therefore not a planner-quality plateau but a dialect-translation plateau.

**Next intervention.** Phase 30 (planned): port the Phase 27 F1 grounding stack (per-task BM25 partition, identifier guard, PK/FK injection) to BQ. The Phase 22 audit predicted a join-inference contribution of ≥ 8 pp on Lite-BQ once grounding lands; this remains untested. Phase 30 will additionally re-attempt A4 with a BigQuery dialect probe that mirrors the Snow catalog probe from Phase 28.

---

## 4. Spider2-Lite-Snow — Phase 27 Breakthrough

```
Phase 17 (v17 pilot10):          ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 18 (v18 closed-set):       ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 22 (A1/A2/A3 stack):       ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 26 (research handoff):     ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%   (pre-grounding)
Phase 27 (F1 grounding pilot):   ████████████████░░░░░░░░░  schema_valid 80% / exec 10%   (pilot 10)
Phase 28 (F4 wrap + F2a revert): █████████████████░░░░░░░░  schema_valid 80% / exec 40%   (pilot 10)
Phase 28 FULL (n=40 of 207, partial): █████████████████░░░░░░░░  partial — full deferred to Phase 28b (\*)
```

**Inflection points.** (1) Phases 17 through 26 produced a flat 0 % on Lite-Snow despite the same closed-set scaffold that worked on Lite-BQ. The audit at Phase 26 identified the failure mode as cross-DB identifier drift: BM25 retrieved tables from the wrong Snowflake database because the index was global, not per-task. (2) Phase 27 F1 fixed this with a per-task BM25 partition keyed by `c.db.upper()`, an SQLGlot identifier guard that rejects three-part names whose database does not match the task's allowed set, retrieval scaling from 80/20 to 200/40, and PK/FK injection. Pilot 10 result: 8/10 schema_valid (vs 0/10 at Phase 26), 1/10 exec_ok. (3) Phase 28 closure layered F4 date-cast wrapping (SQLGlot AST manipulation to wrap NUMBER/VARIANT operands of `DATE_TRUNC`, `EXTRACT`) and an F4c regex fallback for LATERAL FLATTEN queries SQLGlot fails to parse. Pilot 10 jumped from 1/10 to 4/10 exec_ok. (4) Phase 28 F2a (auto-uppercase quoted lowercase identifiers) was falsified by a direct catalog probe and reverted — without that revert, the F4 gain was masked.

**Plateau / status.** The pilot 10 number cannot be projected to FULL without the FULL run. The FULL run is in progress at the time of writing; the exec number on n=207 must be filled in after closure. The schema_valid jump from 0 % to 80 % at pilot scale is robust evidence that the F1 grounding stack works; the remaining gap to ≥ 30 % FULL exec_ok is the open empirical question.

**Next intervention.** Phase 29 (planned, post-FULL): a deeper closed-set retry layer with multi-shot synthesis on the residual schema_valid-but-not-exec tasks, plus a Phase 28 audit of the F4c regex fallback usage rate (if regex coverage is ≥ 50 % we will harden it; if ≤ 20 % we will deprecate it for an upgraded SQLGlot version).

---

## 5. Spider2-Snow — Same Lane, Larger Scope

```
Phase 17 (v17 pilot10):           ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 22 (A1/A2/A3 stack):        ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 26 (research handoff):      ░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%
Phase 27 (F1 grounding pilot):    ████████████████░░░░░░░░░  schema_valid 80% / exec 10%   (pilot 10)
Phase 28 (F4 + F2a revert pilot): █████████████████░░░░░░░░  schema_valid 80% / exec 40%   (pilot 10)
Phase 28 FULL (n=547 final):      ██████░░░░░░░░░░░░░░░░░░░  **23.76 % Snowflake EXPLAIN-pass (\*)** — 130/547
```

**Inflection points.** The trajectory mirrors Spider2-Lite-Snow because the scaffold is shared: the F1 grounding stack and the F4 wrapping live in the same modules and run on both lanes. The relevant distinction is scope: Snow FULL is 547 tasks across many production-style databases, while Lite-Snow is the curated 207-task subset. The pilot 10 result (4/10 exec_ok, 8/10 schema_valid) is therefore an underestimate of pilot variance, not a calibrated forecast for FULL.

**Status.** At the time of writing, the FULL S1 run is ≈ 69 % complete with `exec=88, schema_valid=256, wrapped_n=4, wall=140.9 min`. Extrapolation to 547 is risky because the easy databases tend to be probed first by the BM25 partition; the remaining 31 % is expected to carry a larger share of the long-tail failures.

**Next intervention.** Same as Lite-Snow Phase 29 plan. Additionally, a Snow-specific Phase 29 sub-task: characterise the failure mode of the `wrapped_n` cases — if wrapping is producing false-positive exec_ok (i.e. wrapping a non-date column produced syntactically valid but semantically wrong SQL), the wrap heuristic needs a stricter type check.

---

## 6. Spider2-DBT — Project-Level Generation

```
Phase 23 first DBT submission:   ██░░░░░░░░░░░░░░░░░░░░░░░  10.4%   (partial diagnostic)
Phase 25 v24 stable rerun:       ███░░░░░░░░░░░░░░░░░░░░░░  13.2%   (final official)
Phase 27 (no DBT regression):    ███░░░░░░░░░░░░░░░░░░░░░░  13.2%
Phase 28 (no DBT regression):    ███░░░░░░░░░░░░░░░░░░░░░░  13.2%
```

**Inflection points.** DBT is a single-shot benchmark in our architecture: the planner emits a `model_response_v*.sql` file, dbt runs it against the staging workspace, and the result is graded on `dbt_run_ok` plus content tests. The 13.2 % number breaks down as: 9 success cases, 5 dbt_test_failed (model ran but content checks failed), 17 ran_ok_but_score_zero (dbt produced output but the grading rubric returned zero), 37 dbt_run_failed (model errors). The Phase 25 v24 stable rerun did not change this distribution.

**Plateau.** The dominant failure bucket is `dbt_run_failed` (37 of 68 tasks). These are not dialect or schema-linking errors — they are project-level errors where the generated `.sql` references undefined `ref()` or `source()` macros, uses Jinja syntax our emitter has not seen, or implements multi-model dependency chains the planner does not currently support. The 17 `ran_ok_but_score_zero` cases are a separate category: the SQL is valid but the model is logically wrong (typically wrong aggregation level or wrong join key).

**Next intervention.** Phase 31 (planned): a DBT-specific architecture with three components — (a) a Jinja-aware emitter that calls `dbt parse` before submission to catch macro errors locally, (b) a multi-model dependency resolver that prompts the planner with the staging workspace's `manifest.json`, and (c) a content-test feedback loop that re-prompts the planner on the 5 dbt_test_failed and 17 ran_ok_but_score_zero cases with the failing test message as evidence. The Phase 31 budget target is to halve `dbt_run_failed` (37 → ≤ 18) and recover ≥ 10 of the 17 ran-ok cases, lifting the lane from 13.2 % toward ≈ 25 %.

---

## Cross-Lane Reading

Three lanes are saturated (Spider 1, BIRD, DBT — for different reasons), one lane is plateaued pending a dialect-grounding port (Lite-BQ), and two lanes (Lite-Snow, Snow) are currently being settled by the Phase 28 FULL run. The bottleneck pattern in [02_progression_table_full.md](02_progression_table_full.md) — that scaffolding mattered more than model scale at every stage — repeats lane-by-lane in this document: every inflection point named above is a structural intervention (linker, validator, partitioner, guard, wrapper), not a model swap.
