# B2 Readiness After smoke25

Updated: 2026-04-25T17:11:23.195349+00:00

## Current baseline state on smoke25
- B0 EX = 0.96
- B1 EX = 0.96
- Both subsets so far probe only `concert_singer` (4 tables, smoke10 ⊂ smoke25). Schema-linking benefit is bounded on this slice.

State summary: **baselines strong**

## What B2 needs vs what we already have

| Component | Required for B2 | Already in repo? | Notes |
|---|---|---|---|
| Spider data + schema linking helper | yes | yes (`repo/src/evaluation/baselines.py`) | Reused from B1. |
| Reduced-schema prompt builder | yes | yes (`build_reduced_schema_context`, `make_b1_prompt`) | Reused from B1. |
| Execution + EX evaluation | yes | yes (`execute_sql`, evaluator pattern) | Reused from B0/B1. |
| **Planner** that emits a JSON Plan | yes | no | Need a `make_plan_prompt`, JSON parser, validation against `plan_schema.json`. |
| **Schema retrieval** index (db -> top-K tables/columns) | yes | partial (lexical linker is the seed) | Could start with the same lexical scorer as B1, ranking *across DBs* not within one. |
| **Domain doc retrieval** (e.g. column descriptions, glossary) | nice-to-have | no | Not strictly needed for Spider; document if later switching benchmarks. |
| **Plan -> SQL prompt routing** | yes | no | New prompt template that takes the Plan + reduced schema and emits SQL. |
| **Validation + repair loop** | yes | no | Run generated SQL, inspect error, ask model to repair. Bounded retries. |
| **Execution-guided selection** (multi-candidate generate, pick by execution result) | yes | no | Sample N candidates, prefer the executable one whose result matches another candidate's. |

## Cheapest next experiment ordering
1. **B2 on smoke10 (cheap dry-run of Plan->SQL pipeline)**
2. If (1) clears, B2 on smoke25 (more questions per DB but still single DB — primarily a soak test of the pipeline).
3. Build a multi-DB sample (e.g. one question per `concert_singer`, `wrestler`, `assets_maintenance`, …) — this is where schema linking and retrieval start mattering.
4. After multi-DB shows separation between B0/B1/B2, scale to dev-full.

## Risks
- 4-bit model may regress on planner-style prompts that produce JSON; sanity-check JSON validity before counting EX.
- Cloudflare quick-tunnel timeouts (~100 s) keep biting; the bridge-side background-thread pattern from `04b_smoke25_b0_and_b1_bg.py` should be reused for any B2 run that touches >10 questions.
- One-DB smoke sets give noisy signal; do not treat smoke25 ties as evidence that schema linking is useless in general.
