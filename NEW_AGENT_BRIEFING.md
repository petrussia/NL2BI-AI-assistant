# Briefing for the next agent — pick up at Priority 4 (Spider2-Lite)

Copy everything inside the `=====` markers into the new agent's first turn.
The brief is self-contained: paths, baselines, blockers, and the exact
first action are spelled out so the agent can start without re-asking.

=====================================================================

You are continuing a multi-session research project on the
NL2BI-AI-assistant repo, branch `experiments/denis`. Eight phases of
architecture work are already committed; full state and reasoning are
in `RESEARCH_SUMMARY_FINAL.md` (root of repo). DO NOT re-run earlier
phases. Your job is to pick up at Priority 4 (Spider2-Lite agent) as
the immediate next deliverable.

## Repository state to verify on session start

Branch: `experiments/denis`. Recent commit log should match exactly:

```
158be33 Add RESEARCH_SUMMARY_FINAL.md — full-arc summary across all 9 phases
cc245d4 Phase 8 S1_v7 demo retrieval — clean negative ablation
56ec0f3 Phase 7 evidence_semantics_v7 — clean negative ablation
8559379 Phase 6 B6_v7 LLM-as-judge selector — new SOTA on Spider AND BIRD
cfcafe3 Phase D planner-model swap — clean negative result
6525a94 Phase R2 Premium retrieval — clean negative result
adf4415 Phase C v5 verifier+repair controller
98d39e1 Phase B v5 planner+compiler — clean negative ablation
d2cf0b4 Phase A v2 retrieval
684a818 v11 full-benchmark replication
```

If a SHA is missing, STOP and tell the user. Do not proceed.

## What is already SOTA (do not break)

Production architecture: B6_v7 controller (commit `8559379`).
Frozen FULL-benchmark numbers on Qwen2.5-Coder-7B-Instruct, BF16, A100:

- Spider dev FULL (1034 ex): EX = **76.79%**, Wilson 95% CI [74.1, 79.3]
- BIRD Mini-Dev FULL (500 ex): EX = **38.80%**, Wilson 95% CI [34.6, 43.1]
- Spider2-Lite FULL (547 ex): structural-only — execution blocker

Any new method must either beat or honestly tie these numbers using
paired statistics on FULL splits. Smoke / sample / partial runs are NOT
admissible as final evidence. Full ladder, paired tests, helpful/harmful
counts, source breakdowns, error taxonomy, and Wilson CIs are all required
for any new claim.

## Documents you must read FIRST (in order)

1. `RESEARCH_SUMMARY_FINAL.md` — full arc, all phases, all paths
2. `outputs/logs/baseline_freeze_after_r2_phase_d.md` — frozen numbers contract
3. `outputs/logs/bird_discrimination_gap_closure_v7.md` — Phase 6 SOTA story
4. `outputs/logs/evidence_negative_result_v7.md` — Phase 7 ablation reasoning
5. `repo/src/evaluation/baselines_b6_v7.py` — current production controller
6. `repo/src/evaluation/llm_judge_v7.py` — current selector layer

## Your first task: Priority 4 — Spider2-Lite agent (v7)

Spider2-Lite is the only remaining gap in full-benchmark coverage. It
cannot be measured as standard text-to-SQL EX in our environment for
several layered reasons (already documented in
`outputs/logs/baseline_freeze_after_r2_phase_d.md` section "Spider2-Lite
blocker explanation"):

1. Dialect mismatch: gold uses BigQuery / Snowflake idioms (EXTRACT,
   DATE_TRUNC, ARRAY_AGG, STRUCT, QUALIFY, BQ types). Our pipeline
   emits SQLite by default. Hooks exist in `dialect_utils_v2.transpile`
   but are not wired into v5 baselines.
2. No data warehouse access: real Spider2 execution needs a live BQ
   project + service-account JSON or Snowflake credentials. Default
   sandbox has none.
3. Schema scale: 50–200+ tables per db; thousands of columns. Lexical
   retrieval works less well on enterprise camelCase identifiers.
4. Spider2 official evaluator ships with the benchmark but expects
   live BQ/SF execution.

What we have already published: B0 and B3_v4 structural-only metrics
(safe %, has_select %, avg joins/where/group/order/aggs/subq, avg len)
for 547 items — useful as "pipeline produces plausible SQL" signal,
NOT as accuracy.

### What to build (the deliverable)

Per the original spec (Priority 4 of the prior sprint, in the user's
"big sprint" prompt):

#### Modules

- `repo/src/evaluation/spider2_agent_v7.py` — bounded agent loop
  (max 4–8 steps) with action planner + tool calls + final SQL gen +
  dry-run / checker + bounded repair.
- `repo/src/evaluation/spider2_tools_v7.py` — tool implementations:
  metadata_doc_search, schema_search, join_path_search,
  column_profile, sample_value_probe, dialect_check,
  sql_dry_run_or_execute, cte/view_workspace_builder, bounded_repair.

Action JSON contract:
```
{ "action": "...", "args": {...}, "reason_short": "..." }
```

Candidate families inside the agent:
- C0 direct draft
- C1 retrieval+evidence draft
- C2 view/CTE decomposition draft
- C3 exploration-informed draft after the tool loop

#### Modes — the runner must declare upfront which mode it operates in

A. **Official execution mode** — only if BQ/SF credentials and
   environment are actually available.
B. **Oracle-tables dev lane** — use ground-truth tables if the
   benchmark provides them. Mark as oracle / non-comparable.
C. **Structural-compatible lane** — parse valid + dialect valid +
   table/column validity + structural features. NO official-score
   claims.
D. **Blocker report** — exact missing credentials + exact evaluator
   failure + what is needed to run official.

You will probably end up in mode C or D unless the user supplies
credentials.

#### Required outputs

- `outputs/predictions/spider2lite_agent_v7_full_predictions.jsonl`
  (547 rows)
- `outputs/traces/spider2lite_agent_v7_traces.jsonl` (per-step agent
  trace)
- `outputs/tables/spider2_structural_full_v7.csv`
- `outputs/tables/spider2_oracle_tables_full_v7.csv` (if mode B is
  available)
- `outputs/logs/spider2_agent_design_v7.md`
- `outputs/logs/spider2_execution_blockers_v7.md` (the honest blocker
  map)

### Working environment

- Google Colab Cloud notebook + Drive at
  `/content/drive/MyDrive/diploma_plan_sql/`
- A100 40GB GPU; transformers 5.x; torch 2.10+; sqlglot 25.x
- HF_TOKEN entered manually per session
- Bridge to Colab via `tools/exec_remote.py` against an ephemeral
  trycloudflare URL written to `tools/.bridge_url` (it rotates per
  session — the user re-runs `AGENT_BRIDGE_SETUP` cell and you save
  the new URL)
- `func_timeout` is sometimes missing after kernel restart — `pip
  install func_timeout` once per session.
- Predictions on Drive are PERSISTED across kernel restarts; runner
  scripts in `/tmp/` are NOT — re-upload via `_tmp_upload_*.py` helpers
  if needed.
- All runs MUST be resumable. Per-item JSONL append. Skip-if-done by
  counting existing rows. Heartbeat JSON every 10 items.

### Working norms (binding)

1. NEVER overwrite frozen historical artifacts. New modules use `_v7`
   or `_v8` naming.
2. NEVER claim a final number from a partial / smoke / sample run.
   Partial = debug only.
3. EVERY claim must include paired statistics vs the relevant
   frozen baseline (B6_v7 Spider 76.79% / BIRD 38.80%).
4. EVERY full run produces: predictions JSONL + master matrix CSV +
   paired-significance CSV + design memo + (if applicable)
   negative-result memo + plot.
5. If a method ties or hurts a baseline, that is a clean negative
   result — document the root cause and commit. Do NOT skip writing
   the failing artifact.
6. Spider regression guard: B6_v7 Spider 76.79% must not drop
   significantly. Use spider_safe_mode policy in any judge-using
   variant.
7. Honest blocker reporting: if BQ/SF credentials never appear, do
   not invent execution numbers. Mode C or D only.
8. Do not enable Phase R2 reranker, Phase 7 rich evidence, Phase 8
   demo retrieval, Phase D planner swap on the production path —
   all four were tested and rejected with paired stats.

### Concrete first-session plan (suggested 6–8 hour budget)

1. Verify state: read `RESEARCH_SUMMARY_FINAL.md` and the freeze
   doc; confirm git log; verify Drive predictions intact (10000+
   rows across 9 phases).
2. Diagnose Spider2 execution availability:
   - check for any BQ/SF credentials in env (HF_TOKEN does not count)
   - inspect Spider2 raw resources at
     `/content/drive/MyDrive/diploma_plan_sql/external_benchmarks/spider2_lite/`
   - if no creds → write `outputs/logs/spider2_execution_blockers_v7.md`
     with exact missing-creds list before doing anything else
3. Build `spider2_agent_v7.py` + `spider2_tools_v7.py` carefully
   (see spec above). Start with the structural-compatible lane (mode C)
   so something runs even without credentials.
4. Local sanity test agent on 2–3 items.
5. Phase 9 runner that loops over 547 dev items with bounded
   max_steps. Per-item JSONL + per-step trace JSONL.
6. Launch FULL Spider2 BG.
7. While BG runs, write consolidation script (master matrix
   v9 / v10, structural distribution, blocker map).
8. After BG completes (~3–5 hours), consolidate, mirror to local,
   commit.

### What to AVOID this session

- Re-running B6_v7 / B7d_rich / S1_v7 — they are frozen and committed.
- Touching Phase R2 reranker (saturated) or Phase D planner swap
  (Qwen3 thinking-mode bug, Gemma OOM).
- Adding evidence_semantics_v7 to BIRD path — it was a no-op.
- "Quick smoke" runs as final claim — partial = debug only.

### Tools you have access to inside this repo

- `tools/exec_remote.py` — POST Python code to the remote Colab
  kernel via the bridge tunnel; download files via /file?path=...
  Use this for ALL remote execution, not local scripts.
- `tools/remote_scripts/` — runner / consolidation scripts naming
  scheme: `NNN_phase_*_runner.py`, `NNN_phase_*_consolidation.py`.
  Increment the leading 3-digit number; current latest is `126`.
- `repo/src/evaluation/` — all v2/v5/v6/v7 modules. Use them as
  imports inside Phase 4 agent code; don't duplicate logic.
- `outputs/predictions/` — Drive-mirrored prediction JSONLs.
- `outputs/{tables,logs,plots}/` — analysis artifacts. Always
  download to local before committing.

### Final deliverable check (before commit)

- predictions JSONL has 547 rows
- design memo exists and explains the agent loop
- blocker memo exists if execution is not available
- master matrix v9 includes B0/B3_v4/agent_v7 cells with whatever
  metric mode was used
- structural CSV is present
- per-step trace JSONL is present (even if short)
- commit message follows the established format (see prior commits)
- co-authored line at the end

### After Spider2 is closed

Next-priority order if time allows:
- Priority 6 BIRD R-VES + Soft-F1 (CLI inspection, evaluator wrapper)
- Priority 5 multi-model SYNTH scaling (Gemma-12b / SQLCoder-7B as
  the SYNTH model, NOT planner — different memory profile)
- Priority 7 training selector (preference dataset from existing
  predictions)

Ask the user before starting any of these.

=====================================================================

End of briefing. The new agent should ack with one short paragraph
naming the first action it will take (not full plan; just the next
concrete step) and proceed.
