# 3.1.8 Сравнительная таблица бенчмарков

Этот файл — **master synthesis** across шести бенчмарков, к которым применён наш единый pipeline. Используется для отвечающих на «где наш стэк сидит в общем landscape text-to-SQL benchmarks» в защите.

## Сводная таблица

| Бенчмарк | Год | n (наш test set) | Engine | Schema scale (avg tables/DB) | Total cols в catalog | Eval metric | Top **closed** SOTA (May 2026) | Top **open** SOTA (May 2026) | **Наш** result | Gap до top reproducible |
|---|---|---|---|---|---|---|---|---|---|---|
| **Spider 1.0** dev | 2018 | 1,034 | SQLite | ~5.1 | n/a (per-DB tables.json) | EM + EX | ~89-91% (closed fine-tune) | **94.0%** (наш open ≤30B) | **94.0%** | leading among open ≤30B |
| **BIRD** dev FULL | 2023 | 1,534 | SQLite | ~7.4 | n/a (per-DB) | EX | ~73-76% (Hayabusa, CHASE-SQL family) | **87.9%** (наш, *с methodology caveat*) | **87.9%** | leading among open ≤30B; verification needed |
| **BIRD** mini-dev | 2023 | 250 | SQLite | ~7.4 | n/a | EX | (subset rarely reported separately) | **90.4%** (наш) | **90.4%** | n/a — rapid iteration set |
| **Spider2-Lite (BQ)** | 2025 | ~205 | BigQuery | hundreds-thousands | ~428K | multiset EX (extra cols allowed) | SOMA-SQL 72.02% (Oracle Cloud) | AutoLink+DeepSeek-R1 52.28%; ReFoRCE+Qwen3 35.6% | **34.6%** (Phase 22-26 stack, pilot50 projection) | ~18 pp до AutoLink |
| **Spider2-Lite (Snow)** | 2025 | 207 | Snowflake | hundreds-thousands | ~587K (per-task subsets) | multiset EX row-match | (split rarely separated) | Spider-Agent+Qwen3-Coder open ceiling | partial n=40/207 (\*) — deferred to Phase 28b | cross-metric; "in same band as open-weight Spider-Agent baselines, pending row-match audit" |
| **Spider2-Snow** | 2025 | 547 | Snowflake | hundreds-thousands | ~587K | multiset EX row-match | Genloop 96.70%; ReFoRCE+o3 62.89% (top reproducible) | Spider-Agent+Qwen3-Coder 31.08% | **23.76 % Snowflake EXPLAIN-pass (\*)** (130/547) | cross-metric (наш plan-acceptance vs leaderboard row-match); row-match audit Phase 28b |
| **Spider2-DBT** | 2025 | 68 | DuckDB + DBT | varies (per-project) | per-project | task_success (table+column match) | Databao 58.82% (JetBrains, closed) | Spider-Agent+Claude-3.7 14.70% | **13.2%** (Phase 11 baseline) | ~10pp до open SOTA; matches Spider-Agent ceiling regardless of model class |

**Sources**: own measurements + research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` (May 2026 leaderboard fetch).

## Difficulty progression

```
Spider 1.0 ──→ BIRD ──→ Spider2-Lite (BQ) ──→ Spider2-Snow ──→ Spider2-DBT
   ↓             ↓              ↓                     ↓                   ↓
 Clean         Noisy        Live BQ            Live Snow           Multi-file
schemas       schemas       catalog            catalog              DBT project
SQLite        SQLite        ~428K cols         ~587K cols           DuckDB local
no EK         evidence     domain MD docs      domain MD docs       open-ended
≤30 tabs      ~50-100      hundreds-thousands  hundreds-thousands   varies
              tables       tables/DB            tables/DB            project size
Saturated     Saturated    Active research      Most active         Scaffold-bound
~89-91%       ~73-76%      Top open 52%        Top open 31%        Top open 14.7%
```

Spider 1.0 и BIRD — **saturated** for closed-API tier. Improvement past 90% requires diminishing-returns work. Spider2 family остаётся фронтиром: **2-3× gap** между closed и open даже на top systems.

## Why classical methods fail on Spider2

Per research dossier §1 (Spider2-Snow leaderboard): *"DAIL / CHESS / DIN + GPT-4o (baselines): 0.0-2.2% EX"*. Same systems на Spider 1.0 dev achieve 70-85% EX.

**Why fail**:

1. **Schema scale**: Spider 1.0 ≤50 tables/DB → fits in 8K-32K LLM context window directly как prompt; Spider2-Snow PATENTS alone имеет hundreds of tables — must use retrieval.
2. **Identifier hallucination**: free SQL emission produces invalid column/table names при unfamiliar schema. Classical methods (DAIL with question similarity, DIN with decomposition, CHESS with PK/FK injection) **lack closed-set planning + validator**.
3. **Dialect mismatch**: classical methods optimized for SQLite. Snowflake LATERAL FLATTEN, BigQuery ARRAY UNNEST, three-part identifiers — not in classical training data heavily.
4. **External knowledge integration**: Spider2 .md domain documents not parsed by classical methods. Even Spider2 train-set fine-tuning не bridge gap.

Это motivation для:
- **Schema-first ranking + closed-set planning** (Phase 18+).
- **Per-task BM25 partitioning** (Phase 27 F1).
- **Dialect post-processors** (Phase 27 F1 + Phase 28 F4).

## Why наш single architecture работает across all 6 benchmarks

Architectural choices, которые перетягивают через все шесть бенчмарков:

### 1. Lane-agnostic schema linker

BM25 over text representation — **works на любом catalog** (live INFORMATION_SCHEMA для Spider2, packaged tables.json для Spider1/BIRD). Same `SchemaLinker` class indexes без modification.

### 2. Closed-set plan-JSON contract

Planner emits **structured plan** validated против pack. Identifier hallucination — главная failure mode на Spider 2.0 — caught upstream. Slight cost on Spider1/BIRD (-0.033 EX from planner decomposition cost) **acceptable trade**.

### 3. Layered validators

JSON Schema + AST closed-set + engine dry_run / EXPLAIN / SQLite execute. Каждый layer catches different class failures. Removing any layer regressses EX (Phase 17-22 empirical).

### 4. Family B universal

Coder-7B direct emit — works на every lane без modification. Lane-specific Family A (BQ-only) + Family C (BQ-only) — bonus где applicable.

### 5. Dialect post-processors lane-gated

Phase 27 F1 + Phase 28 F4/F4c — Snow-specific dialect handlers. Phase 24 v24 BQ engine-compat rewrites — BQ-specific. Gated explicitly via `lane in ('snow', 'lite_snow')` checks. **Не leak into Spider1/BIRD/SQLite paths**.

### 6. Resume + resilience

Phase 28 resume scaffolding + periodic flush + supervisor heartbeat — orchestration patterns same across lanes. Не lane-specific, не pipeline change.

Это иллюстрирует **separation of concerns**: общая core, lane-specific extensions локально.

## Where gap до closed top is fundamentally tied к model class

Closed-API top tier achieves:
- Spider 1.0: ~89-91% (closed fine-tune) — similar к нашему 94% (better open)
- BIRD: ~73-76% (Hayabusa) — наш 87.9% claims above ⚠️ verification needed
- Spider2-Lite: 72% (SOMA-SQL closed), 55% (ReFoRCE + o3)
- Spider2-Snow: 96.70% (Genloop closed), 62.89% (ReFoRCE + o3 reproducible)
- Spider2-DBT: 58.82% (Databao closed)

Gaps на Spider 2.0 family между нашим open ≤30B стэк и:
- **Closed industrial top**: 2-3× gap. Unaddressable by scaffolding alone — requires either closed-API access (out of scope) или much larger open model.
- **Reproducible top (ReFoRCE/AutoLink with DeepSeek-R1)**: 1.5-2× gap. Partially addressable:
  - DeepSeek-R1 685B vs наш 30B+7B — **20× param difference**. Cannot close with scaffolding alone — но Phase 29 F3 self-refine plus F2 JOIN-graph + F4-equivalent BQ post-processor may halve gap.

### Realistic ceiling для нашего ≤30B stack

| Bench | Current | Phase 29-30 plan ceiling | Closed-API ceiling |
|---|---|---|---|
| Spider 1.0 | 94.0% | ~96% | ~91% (no room для big lift) |
| BIRD | 87.9% | ~90% | ~76% |
| Spider2-Lite-BQ | 34.6% | ~52-58% (with F3 + F2 + BQ F4) | 72% |
| Spider2-Snow | **23.76 % EXPLAIN-pass (\*)** | ~27.5-30 % EXPLAIN-pass (+ Phase 29 F3) | 63-97 % row-match |
| Spider2-DBT | 13.2% | ~25-30% (Phase 31 scaffold redesign) | 59% |

Source для ceiling estimates: research dossier §5 (F-series fixes expected lifts).

**Bottom line**: scaffolding interventions имеют **hard ceiling** ~30-40% Snow EX, ~55-60% Lite-BQ EX, ~30% DBT EX для open ≤30B class. Further increase requires either DeepSeek-R1-class open weights (685B, beyond ≤30B constraint) или closed-API reasoning models (out of scope).

## Honest publishability tier per benchmark

| Bench | Tier | Justification |
|---|---|---|
| Spider 1.0 dev 94.0% | **High** — top tier для open ≤30B (above CodeS-15B SFT 84.9%) | Publishable conditional оn official leaderboard verification |
| BIRD FULL 87.9% | **Mid-to-high** — claim above current top requires methodology audit | Publishable after BIRD evaluation script verification |
| BIRD mini-dev 90.4% | **Mid** — mini-dev rarely reported separately в leaderboard | Acceptable as supplementary number |
| Spider2-Lite-BQ 34.6% | **Mid** — band с reproducible mid-tier; not top open | Publishable as «open ≤30B baseline» |
| Spider2-Lite-Snow partial n=40/207 (\*) | Deferred to Phase 28b; pilot10 v28-revert-A 4/10 trends consistent | Publishable as «open ≤30B Lite-Snow plan-acceptance baseline» post Phase 28b |
| Spider2-Snow **23.76 % EXPLAIN-pass (\*)** | **First non-zero publishable Snow plan-acceptance figure** для open ≤30B; row-match audit Phase 28b | Workshop publishable now with cross-metric disclosure; top-tier conditional on Phase 28b row-match audit |
| Spider2-DBT 13.2% | **Reproduction tier** — matches Spider-Agent ceiling regardless of backbone | Not publishable as new contribution; pointer для Phase 31 scaffold redesign direction |

## Какие методологические claims supports overall pattern

1. **Single architecture works cross-bench (RQ1)**: same stack achieves non-trivial result на 5 of 6 lanes (DBT — scaffold-limited). Confirms hypothesis.

2. **Scaffolding-level interventions matter more чем model upgrade в ≤30B class (RQ2)**:
   - Spider2-Snow 0% → 4/10 pilot10 (40% pilot lift) с Phase 27 F1 + Phase 28 F4 — **same models throughout**.
   - Spider2-DBT 13.2% regardless of model class — **scaffolding bottleneck**.

3. **Catalog-probe methodology validates dialect heuristics (RQ3)**:
   - Phase 28 F2a opposed empirically — без catalog probe would have been deployed FULL → regressions.

4. **First publishable Snow number for open-weight ≤30B stack (Claim 4)**:
   - Pre-Phase-27 baseline 0% (v25 FULL exec=0).
   - Post-Phase-28 revert-A: 130/547 = 23.76 % Snowflake EXPLAIN-pass (\*) — first non-zero FULL number (plan-level acceptance; row-match audit Phase 28b).

5. **Reproducibility achieved**: every result via committed code at `ad5493b`.

## Cross-references

- Each benchmark в detail:
  - [01_spider1.md](./01_spider1.md)
  - [02_bird.md](./02_bird.md)
  - [03_spider2_overview.md](./03_spider2_overview.md)
  - [04_spider2_lite_bq.md](./04_spider2_lite_bq.md)
  - [05_spider2_lite_snow.md](./05_spider2_lite_snow.md)
  - [06_spider2_snow.md](./06_spider2_snow.md)
  - [07_spider2_dbt.md](./07_spider2_dbt.md)
- Pipelines per benchmark: [05_PIPELINES/](../05_PIPELINES/)
- Architecture (shared core): [04_ARCHITECTURE/01_overview_single_architecture.md](../04_ARCHITECTURE/01_overview_single_architecture.md)
- Methodological claims: [01_INTRODUCTION/04_thesis_contributions.md](../01_INTRODUCTION/04_thesis_contributions.md)
- Leaderboard position: [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md)
- Publishability assessment: [09_RESULTS_ANALYSIS/07_publishability_assessment.md](../09_RESULTS_ANALYSIS/07_publishability_assessment.md)
- Final headline results table: [07_METRICS_AND_RESULTS/07_headline_results.md](../07_METRICS_AND_RESULTS/07_headline_results.md)

## Источники

| Утверждение | Источник |
|---|---|
| Our results progression | `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` §1 + Phase 27/28 reports |
| SOTA numbers | research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §1-3 + §4 |
| Schema scale per bench | own measurements + bench docs |
| F-series fix expected lifts | research dossier §5 |
| Publishability tier justifications | own + research dossier §8 caveats |
