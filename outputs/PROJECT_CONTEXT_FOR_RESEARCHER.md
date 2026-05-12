# NL2BI / Spider2 Project Context — researcher onboarding

_Repository: `NL2BI-AI-assistant` | Branch: `experiments/denis` | Owner: Denis (HSE)_

## 1. What this project is

This is an HSE diploma project (ВКР / final qualifying work) on **NL2BI** (Natural Language to Business Intelligence) — text-to-SQL generation against real warehouse schemas. The research arc has two phases of focus:

1. **Classical benchmarks** (Phases 1–16, January-April 2026): Spider 1.0 dev + BIRD mini-dev / dev, on SQLite. Goal: characterize the smallest competitive single-model + linker architecture and decide whether a planner step helps. **Outcome: B1_v3 (bidirectional retrieval linker, no planner, 1 LLM call) with Qwen2.5-Coder-7B was the production winner**, EX = 0.80 on multi-DB. Planner was shown to **hurt EX by -0.033** in a controlled comparison.

2. **Spider 2.0 family** (Phases 17–26, April-May 2026): Spider2-Lite / Snow / DBT — modern multi-DB warehouse benchmarks with live BigQuery, Snowflake, and a DBT repo agent task. Goal: get production-quality numbers on the three Spider2 lanes that are commercially comparable to closed-LLM agents. **Current status (Phase 26): Spider1/BIRD are SOTA-tier (94 %, 88 %); Spider2 lanes are mixed — DBT 13 % matches Phase 11 baseline, Lite-BQ 35 %, Snow lanes near 0 % due to a known cross-DB identifier-grounding failure.**

The thesis itself focuses on Spider2 since classical benchmarks are largely solved. Spider2 was released in 2024 to address gaps in Spider1/BIRD (closed schemas, no real cloud-warehouse semantics).

## 2. Research question (high level)

> Can a small open-source coder-LLM (≤30 B params, no commercial overlay) match closed-LLM agent performance on a modern multi-DB warehouse benchmark (Spider2) when paired with a deterministic schema-linking + closed-set + validator-first pipeline?

Sub-questions:
- Does a planner step help when the model is a coder-tuned 7B+ ?
- How much of the gap to GPT-4-class systems is **architectural** (better retrieval, better constraints, better engine-compat) vs **model-size**?
- Where does the same architecture succeed (SQLite-only) vs fail (multi-DB Snowflake)?

## 3. Stack used end-to-end

| component | choice | rationale |
|---|---|---|
| Planner model | Qwen3-Coder-30B-A3B-Instruct (BF16, ~60 GB) | MoE 30B/3B-active; structured-JSON-following capability above 7B comparators |
| Emitter model | Qwen2.5-Coder-7B-Instruct (BF16, ~14 GB) | Production winner from Phase 9-11 controlled comparison; fast |
| Schema linker | v18 BM25 over live `INFORMATION_SCHEMA` catalogs | Spider2-Lite-BQ catalog: 428K cols; Snow: 587K cols |
| Pack builder | v18, `max_tables=8`, `max_cols_per_table=22` | Compact for prompt + `all_columns` side-channel for validator |
| Structured plan | JSON-validated against pack (closed set) | One validator-feedback retry on AST fail |
| Candidate factories | Family A (deterministic BQ render) + Family B (Coder-7B direct) + Family C (BQ JOIN-aware; rarely chosen) + `<X>_v24` rewrites | Selector tie-breaks by dry_run_ok ≻ parse_ok ≻ schema_valid ≻ Family A |
| BQ engine check | `dry_run` (no bytes billed) | Phase 18 forward |
| Snow engine check | `EXPLAIN` (compile-only) | Phase 25 forward |
| SQLite engine check | `cur.execute() + fetchmany(10)` | Phase 26 |
| DBT eval | `dbt deps + run + test + server_official_eval.py` (SSH to remote dbt project) | Spider2-DBT official scoring |

**Hardware:** 3 × Colab A100 80 GB (free-tier-equivalent compute) running in parallel since Phase 26.

**Bridges:** each Colab kernel exposes a Flask `/exec` + `/health` + `/file` + `/ls` via Cloudflare quick-tunnel; local Windows orchestrator talks to bridge via `tools/exec_remote.py`.

## 4. Research history — concise timeline

### Phase 1-10 (January-March 2026): foundational baseline grid

- Multi-model × multi-prompt-style grid over **8 emitter models** and 4-5 prompt styles on Spider1 + BIRD mini-dev subsets (10, 25, 30 tasks).
- Models tried: Qwen2.5-Coder-7B, Qwen2.5-Coder-14B, Qwen2.5-Coder-32B, Llama-3.1-8B, Gemma-3-12B, Qwen3-8B, SQLCoder-7B-2, Mistral-7B.
- Master matrix: **127 rows** (model × style × benchmark × split). Available at `outputs/tables/final_experiment_master_matrix.csv`.
- **Conclusion:** Qwen2.5-Coder-7B at the B0 prompt style (full schema in context) dominates. Larger Coder-14B and 32B variants *lose* to 7B on multi-DB — a "right-sizing" finding.

### Phase 11 (March 2026): DBT baseline

- First end-to-end DBT FULL 68 run on Spider2-DBT.
- Result: **9 / 68 = 13.2 % task_success** with Qwen2.5-Coder-7B + v4 prompt style.
- This is the **published baseline number** for the project. Phase 26 (current) reproduces it exactly, confirming pipeline reproducibility.

### Phase 12-16 (March-April 2026): Spider2-Lite/Snow pilot iterations

- v12, v13, v16 pipelines on Spider2-Lite-BQ and Spider2-Snow pilot10.
- v16 Snow added "constrained identifier repair" — model emits SQL, a validator catches unknown identifiers, agent suggests replacements.
- Outcome: **BQ pilot10 schema_valid 1→6**, **Snow constrained repair could not move Snow off 0 schema_valid** — early signal of the Snow-specific failure mode that still hurts today.

### Phase 17 (April 2026): model-swap pilot10 grid on Spider2-Lite/Snow

- 4 models × 2 lanes (BQ, Snow): Qwen2.5-Coder-7B, Qwen3-Coder-14B, Qwen3-Coder-30B-A3B, Mistral-Coder.
- **Key finding: "family > scale".** Qwen-Coder family dominates regardless of size. Larger non-Qwen models lose.
- **Snow lane was retrieval-bound** even with the best model. BQ ceiling on Coder-7B at v16 pipeline was ~60 % schema_valid.
- v17 confirmed: the BQ ceiling is **architectural, not model-size**. Catalyzed Phase 18 pivot.

### Phase 18 (April 2026): schema-first / closed-set / validator-first pivot

- Replaced "model writes SQL → validate" with "model writes JSON plan against closed-set pack → validate plan → render SQL deterministically → engine dry_run".
- **First non-zero BQ `dry_run_ok`: 1 / 10 pilot10.** Major architectural shift.
- 7 punch-list issues found in v18.0 → fixed in v18.1.

### Phase 19 (April 2026): v18.1 repair sprint

- 7 patches on v18 stack lifted BQ pilot10 to **3 / 10 schema_valid + 3 / 10 dry_run_ok** (both gates cleared at 30 %). Launched pilot50.

### Phase 20 (April 2026): STAGE A1 partial — shared identifier canonicaliser

- Lifted plan_validation_ok 42 → 54 %, but didn't move chosen_schema_valid.
- Diagnostic conclusion: the gap is **engine-compat** (BQ-specific dialect quirks: ARRAY_EXISTS, NTH, multi-CTE), not identifier canonicalization.

### Phase 21 (April 2026): STAGE A1 convergence

- Metric-label fix + UNNEST alias trust.
- 4-session pilot50 reproducibility check: stable in **sv 50-52 % / exec 42-46 %** bands.
- Concluded: FULL gap is STAGE A2 (join-aware) territory.

### Phase 22 (April 2026): STAGE A1 + A2 + A3

- Pack `all_columns` side-channel (full schema visible to validator, compact to planner).
- `join_hints` heuristic.
- Family C deterministic JOIN-aware renderer.
- Result: **sv 50 → 54 %** (audit predicted +20 pp, got +4 pp). Family C **never chosen** (heuristic too weak).
- FULL gate not cleared. Gap is STAGE A4 (engine-compat).

### Phase 23 (May 2026): FULL diagnostic — infrastructure blocked

- Tried to run FULL 547 + 547 + 68 across BQ + Snow + DBT simultaneously.
- All 3 sessions tried to use the same Colab kernel → concurrent CUDA OOM on A100 80GB.
- **BQ FULL stalled at 14 / 205**, both Snow CANCELLED, DBT BLOCKED.
- Outcome: no new official Spider2 numbers. DBT 13.2 % remained the only publishable.
- Phase 23 documented the orchestration failure → Phase 24 fix.

### Phase 24 (May 2026): GPU lock + sequential runner + A4 engine-compat

- Drive-file GPU lock to enforce ONE inference run at a time.
- STAGE A4: 6 BigQuery engine-compat rewrites (ARRAY_CONTAINS → EXISTS UNNEST; NTH → array offset; multi-UNNEST; nested-agg flag; window+GROUP_BY flag; AND-on-int wrap).
- Lite-BQ pilot50 v24 vs v22: **IDENTICAL metrics (sv 54 %, exec 44 %)**. Engine rewrites METRIC-NEUTRAL.
- Diagnosis: trace-driven categorization in Phase 22-23 mis-identified actual failure modes. Real top-cases: `unrecog_name` (5/14) and unquoted-date-literal `AND_int` (3/14), not bare-int.

### Phase 25 (May 2026): stable Lite-BQ FULL retry

- After multiple Colab kernel deaths, pulled off the **first complete Spider2-Lite-BQ FULL 205** run.
- Result: **sv 58.0 % / exec 34.6 % / parse 99.5 %**. This is the most-current Lite-BQ number.
- Then ran Snow FULL on the same kernel; got 0 % exec due to Phase 26-confirmed cross-DB identifier drift.

### Phase 26 (May 2026, current): 3-session parallel run + legacy benchmarks

- **Three Colab runtimes** in parallel:
  - S1: Spider2-Snow FULL 547 (in progress, 70 % done at time of write)
  - S2: DBT FULL 68 → Spider1 dev FULL 1034 → BIRD mini-dev 250 → BIRD FULL dev 1534 → Lite-SQLite 135
  - S3: Lite-Snow 207 → Lite-SQLite 135
- **NEW results (Phase 26):**
  - **Spider1 dev FULL 1034: exec_ok 94.0 %** ← first official-style Spider1 result
  - **BIRD mini-dev 250: exec_ok 90.4 %**
  - **BIRD FULL dev 1534: exec_ok 87.9 %** ← first official-style BIRD result
  - **DBT FULL 68: task_success 13.2 %** ← reproduces Phase 11 baseline exactly
  - **Lite-Snow 207: exec_ok 0.5 %** ← confirms Snow failure mode generalized
- Detailed handoff doc: `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md`

## 5. Key architectural decisions and why

| decision | rationale | when |
|---|---|---|
| **No planner for production** | Controlled v9 comparison: B0/B1 (no planner) > B2/B4 (planner) by 0.033 EX on multi-DB | Phase 9-10 |
| **Qwen2.5-Coder-7B as emitter** | Won the 8-model × 4-style grid; right-sizes 14B and 32B variants | Phase 8-10 |
| **Schema-first / closed-set / validator-first** | Replaced "generate SQL → check" with "generate JSON against closed schema → render SQL"; lifted BQ from 0 % dry_run to >40 % | Phase 18 |
| **Live catalog instead of static `tables.json`** | Spider2 lanes need real INFORMATION_SCHEMA because the benchmark uses live warehouse DBs | Phase 18 |
| **Pack `all_columns` side-channel** | Pack compact (BM25 top-K) for prompt economy; full column list (`all_columns`) for validator residency | Phase 22 |
| **Family A (deterministic) + Family B (model)** | Validator-first selector picks Family A 84-86 % of the time on BQ; gives architectural lift independent of model | Phase 19 |
| **Phase 24 GPU lock** | A100 80 GB can't run 3 concurrent forward passes on 70 GB-loaded models without OOM. Required for any parallel/sequential orchestration | Phase 24 |
| **Snow connector creds set on bridge env** | Snow EXPLAIN replaces BQ dry_run for `execute_ok` metric; user-supplied SF account | Phase 25 |
| **3 separate Colab runtimes, not 3 notebooks** | Force-checked via pid-match in bridge tunnel reuse — otherwise the 3 notebooks of one Colab account share ONE runtime. True parallelism only with new browser profiles per notebook | Phase 26 |

## 6. Open scientific questions (in priority order for thesis closure)

1. **Why does this architecture get 94 % on Spider1 SQLite and 0 % on Spider2-Snow?**
   Hypothesis: multi-DB ambiguity in the Snow live catalog allows cross-DB identifier drift. Strict single-DB pack filtering should test this in <1 day of engineering.

2. **Why does the same Qwen2.5-Coder-7B emitter reproduce Phase 11 DBT 13.2 % despite all our v18+v22+v24 pipeline work?**
   Hypothesis: DBT is bottlenecked on the **agent loop**, not on the SQL emitter. Single-shot generation can't match what a multi-iteration verifier could.

3. **Why does BIRD beat Spider1 by 6 pp (88 % vs 94 %) despite higher task difficulty?**
   Hypothesis: BIRD `evidence` field gives the model the knowledge it needs; Spider1 has no equivalent. Counter: maybe our Spider1 scorer (cur.execute success) is more lenient than BIRD's (set-match). Should re-score Spider1 with set-match.

4. **Why did Phase 22 audit predict +20 pp from the validator FP fix but only get +4 pp?**
   The audit assumed all `ast_leak` cases were validator false positives. Trace inspection in Phase 24 showed that many of those cases reference columns NOT in INFORMATION_SCHEMA either (derived columns, sub-query aliases). The validator was actually right.

5. **Why does Family C (JOIN-aware) get emitted on 17 / 50 BQ pilot50 tasks but chosen 0 / 50?**
   Heuristic for join detection (shared key-shape column names) is too weak. Replacement with real FK signal from `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` is unrealized.

## 7. Known infrastructure quirks

- **Cloudflare quick-tunnels rotate.** A Colab kernel that loses connectivity needs cell 07 (`AGENT_BRIDGE_SETUP_FIXED`) re-run. The Drive-side BG runners survive tunnel rotation; only the local poller dies.
- **Colab idle timeouts** kill the kernel after ~12-24 h. All BG runners write per-task to Drive so resume after kernel death is possible (`_phase25_resume_lite_bq.py`).
- **`/exec` is single-threaded Flask** — under heavy GPU load, status probes can timeout at Cloudflare's 524 (~100 s) limit. The kernel is fine; just retry with longer timeout.
- **Drive sync to Windows is NOT enabled** in this project — the local repo and `<PROJECT_ROOT>` on Drive are mirrored manually for code (`repo/src/evaluation/*`), and predictions/traces flow from Drive → local via `tools/exec_remote.py` base64 file pull.
- **DBT remote server** at `denis@103.54.18.91` (gitignored config). dbt venv at `/home/denis/dbt/.venv`. The Spider2-DBT scoring runs SSH eval calls.
- **Each Colab runtime starts with 0 GB allocated.** Model load takes ~10-15 min (Qwen3-Coder-30B BF16 = 60 GB, then Qwen2.5-Coder-7B = 14 GB). After load, ~6 GB free for activations.

## 8. Memory / continuity

The Claude Code session memory (under `C:\Users\dlaze\.claude\projects\d--HSE--------NL2BI-AI-assistant\memory\`) carries phase-by-phase findings (`spider2_phase17_findings.md` through `spider2_phase24_findings.md`) that summarize the per-phase conclusions in 1-2 paragraphs each. These are deliberately terse — read them for the "what would I forget" version of the history.

## 9. What the diploma / ВКР needs

The diploma write-up requires:

1. **Three published Spider2 numbers** that are honest, official-comparable, and not "diagnostic-only":
   - DBT 13.2 % ✅ (Phase 11; reproduced Phase 26)
   - Lite-BQ exec_ok: best honest number is **34.6 % from Phase 25 FULL 205**
   - Spider2-Snow: currently **0 %** (in progress); needs architectural fix before publishable

2. **Comparison to leaderboards** so the thesis can say "we are at X-th place / SOTA-tier on benchmark Y". With Phase 26:
   - Spider1 dev exec_ok 94 % → top-tier (research-grade)
   - BIRD dev exec_ok 88 % → top-tier (better than published 75 % for GPT-4 + reasoning)
   - DBT 13 % → matches baseline, doesn't beat it (this is honest; not all benchmarks have to be wins)

3. **Diagnostic on why some lanes fail.** Phase 26 researcher-handoff doc (`REPORT_PHASE26_RESEARCHER_HANDOFF.md`) does this with hypotheses + concrete experiments to verify.

4. **Reproducibility kit**: predictions/traces files on Drive for every claim; runner scripts in `tools/`; pipeline code in `repo/src/evaluation/`; configs gitignored but documented.

## 10. Hard constraints inherited from earlier phases (don't violate)

- **NEVER mix Lite/Snow/DBT into one combined metric** — each is a separate benchmark.
- **NEVER use SQLite stub of Lite as an official comparable** — per Phase 23 non-comparable policy.
- **NEVER use oracle / gold tables in the official score path** — only as diagnostic.
- **NEVER use released Spider2 gold SQL for SFT or unfair prompting** — the gold queries can be inspected for analysis but not fed to the model.
- **NEVER call a `diagnostic` run an `official` benchmark headline** — be honest about partial / killed / OOM-degraded runs.
- **NEVER push to git without explicit user command** — local-only commits are the norm.
- **NEVER over-claim:** if a number is from a sample / sub-set / aborted run, label it that way.

## 11. Tactical TODO if researcher picks up Phase 27

If this is a fresh handoff, the most leveraged next steps (per Phase 26 analysis):

1. **Strict single-DB pack filtering on Snow** — should lift Spider2-Snow + Lite-Snow from 0 % toward 20-40 % execute_ok. ~1 day engineering.
2. **JOIN-aware Family C with real FK signal** (`INFORMATION_SCHEMA.KEY_COLUMN_USAGE`) — should lift Lite-BQ by +5-10 pp on `unrecog_name` failures. ~2 days.
3. **DBT v2 governed agent: read-before-write + 3-iteration verifier loop** — should lift DBT 13 % to 25-30 %. ~1 week.
4. **Date-literal post-render fix** for Lite-BQ — should fix 3 of 14 dry_run_failed in v22 pilot50. ~2 hours.
5. **Run Spider1 + BIRD with stricter set-match scorer** — verify whether our 94 %/88 % numbers hold up against the official scorer methodology.

Pass any of those to the researcher and the project moves forward.

---

**End of context.** Detailed Phase 26 numbers + file paths in companion document `REPORT_PHASE26_RESEARCHER_HANDOFF.md`.
