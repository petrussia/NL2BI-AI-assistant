# 2.4 Agentic frameworks для DBT lane

## Назначение

Spider2-DBT — единственный из бенчмарков нашей работы, где задача — не single SQL emission, а **multi-file project editing**. Это меняет class problem с *text-to-SQL* на *agent-driven software engineering*. Этот файл — survey agentic frameworks relevant к Spider2-DBT lane, и **direct preview** для Phase 31 scaffold redesign (out of dossier scope, but foundational future work).

Современная база: Spider2-DBT 13.2% naшa baseline = Spider-Agent ceiling 14.7% regardless of backbone — **scaffold-bound**. Databao 58.82% (closed top) = 4× lift from scaffold redesign **at same model class tier**. Phase 31 target: 22-32% через partial Databao-style reproduction.

## Spider-Agent (xlang-ai baseline)

**Citation**: part of Spider 2.0 release [Lei et al., ICLR 2025, arXiv 2411.07763].
**Repo**: github.com/xlang-ai/Spider2.

### Architecture

ReAct (Reason + Act) agent loop:
1. Agent receives task instruction + project directory.
2. Each turn: agent emits a thought + tool call (bash command, file read, file write).
3. Tool outputs returned to agent context.
4. Agent decides next action or terminate.

Tool surface includes:
- `bash <cmd>` — arbitrary shell command (free).
- `read_file <path>` — view file contents.
- `write_file <path> <content>` — overwrite file.
- `terminate` — finish task.

### Spider-Agent ceiling evidence

Per research dossier §3 Spider2-DBT leaderboard:

| Backbone | task_success |
|---|---|
| Spider-Agent + Claude-3.7-Sonnet | **14.70%** |
| Spider-Agent + o1-preview | **13.24%** |
| Spider-Agent + наш Qwen3-Coder-30B-A3B + Qwen2.5-Coder-7B | **13.2%** |

**Three different model classes producing equal results** (~13-15%). Convergence у scaffold ceiling.

### Связь с нашей архитектурой

Spider-Agent's ReAct loop — **paradigmatic enterprise NL2BI agent baseline**. Наша Phase 11 DBT pipeline reproduces this baseline ~exactly (13.2% confirms reproduction).

**Limits Spider-Agent ceiling hits**:
- Free bash → agent occasionally runs unhelpful commands (`ls /tmp`, irrelevant `find`).
- No structural guidance — agent decides what to do at each turn without strong priors.
- Diff-patch edit format predominant — penalizes Coder-7B per Aider Polyglot evidence.
- No staged verifier — agent can `terminate` with broken `dbt run`.

## Databao Agent (JetBrains)

**Citation**: Mikhailovskii & Zolotarev. *Databao Agent — #1 on Spider2-DBT*. blog.jetbrains.com/databao/2026/02/.
**Verbatim methodology quote** (research dossier §4):

> *"We made it smarter not by replacing the model, but by changing the environment around it."*

### Disclosed methodology (3 core principles)

1. **Up-front DB overview**: before any task, agent first reads + analyzes complete DB schema + DBT project structure. **Front-loads context** so subsequent edits informed.
2. **Restricted tool surface**: NO free `bash`. Defined operations only — `read_model`, `write_model`, `compile`, `test`. Constrains agent action space.
3. **Verifier gate**: agent **cannot** `terminate` until `dbt run` returns 0 exit. Forces iteration on broken outputs.

### Best metrics

- **Spider2-DBT: 58.82%** (rank 1).
- **Spider2-Lite: 69.65%** (rank 3).

### Связь с нашей архитектурой

**Recipe для нашего Phase 31 scaffold redesign**:

| Databao principle | Phase 31 plan |
|---|---|
| Up-front DB overview | Read `sources.yml` + `schema.yml` + existing `models/*` files перед planner step. Inject summary в planner prompt. |
| Restricted tool surface | Replace free filesystem operations с specific verbs: `view_model(name)`, `view_source(name)`, `propose_model(name, content)`, `run_dbt_compile(model)`. |
| Verifier gate | Staged validator: `dbt parse → compile → run → test`. On any fail, capture error + agent retry up to N times. |

**Estimated Phase 31 outcome**: 13.2% → 22-32% (partial Databao reproduction). Full 58.82% likely requires proprietary engineering not disclosed.

## SWE-agent

**Citation**: Yang, J. et al. *SWE-agent: Agent-Computer Interfaces Enable Software Engineering Language Models*. NeurIPS 2024, arXiv 2405.15793.
**Repo**: swe-agent.com / github.com/SWE-agent/SWE-agent.

### Architecture

General-purpose SWE agent for software engineering tasks (SWE-bench, SWE-bench Lite, etc.). **Custom Agent-Computer Interface (ACI)**: specialized tool wrappers vs raw bash.

### Key ablation result

Per research dossier §4: **edit-linter-revert ablation: +8 pp на SWE-bench Lite**. Means staged verifier (lint after edit, revert if broken) — substantial empirical lift.

### Связь с нашей архитектурой

**Direct evidence для staged verifier loop concept** в Phase 31 plan. SWE-agent showed:
- Linter feedback after edit beneficial.
- Revert ability на broken edits prevents agent stuck в local minimum.
- ACI (tool wrappers) vs raw bash — improves agent decision quality.

Phase 31 plan adopts SWE-agent ACI concept — high-level verbs (`propose_model`, `run_dbt_compile`) instead of free bash.

## OpenHands (CodeAct successor)

**Citation**: Wang, X. et al. *OpenHands: An Open Platform for AI Software Developers as Generalist Agents*. ICLR 2025, arXiv 2407.16741.

### Architecture

Multi-agent SWE framework. Sandbox tooling, restricted action space, several agent personalities (PlannerAgent, CodeActAgent, BrowsingAgent).

### Связь с нашей архитектурой

Less directly relevant к Spider2-DBT (OpenHands broader SWE scope), но contributes к Phase 31 design:
- **Multi-agent role separation** parallels наш planner-emitter (planner = PlannerAgent equivalent, emitter = CodeActAgent equivalent).
- Sandbox tooling — restricted tool surface aligns с Databao principle.

Phase 31 не plans full multi-agent — single agent с structured tools sufficient.

## aider — edit format research

**Citation**: aider.chat / paul-gauthier/aider (open source).

### Polyglot benchmark finding

aider maintains **Polyglot leaderboard** — code editing benchmark across multiple programming languages. Per research dossier §4:

> *Qwen2.5-Coder-7B drops ~30% accuracy on Polyglot when forced into diff vs whole-file format on files <200 LOC*

— **Direct evidence** что **edit format choice matters more than model upgrade** в этом size class.

### Связь с нашей архитектурой

**Critical для Phase 11 / Phase 26 DBT pipeline assessment**. Наш current DBT pipeline:
- ~90% diff-patch edits.
- 0% multi-block whole-file emits.
- DBT files typically <200 LOC.

Coder-7B systematically underperforms на этом edit format. **Phase 31 plan**: switch к **multi-block whole-file emit format** — agent emits entire `model.sql` per task, not diff against existing. Expected lift +4-8 pp from this single change.

### What "multi-block whole-file" means в DBT context

Current (diff-patch):
```
@@ -10,5 +10,9 @@
     select user_id,
-           count(*) as orders
+           count(*) as orders,
+           sum(amount) as total
     from {{ ref('orders') }}
     group by user_id
```

Phase 31 (whole-file regenerate):
```
-- models/agg/user_summary.sql
{{ config(materialized='table') }}

select
    user_id,
    count(*) as orders,
    sum(amount) as total
from {{ ref('orders') }}
group by user_id
```

Agent emits complete file content. Simpler structurally, более forgiving к minor mismatches с existing structure.

## Cline / Cursor / Claude Code — production coding agents

### Цитирование / репозитории

- **Cline** (formerly Claude Dev) — open-source. github.com/cline/cline.
- **Cursor** — closed commercial product. cursor.com.
- **Claude Code** — Anthropic official CLI. claude.com/claude-code.

### Common patterns

Все three используют **Plan-Act / Architect-Editor** separation:
- **Plan / Architect agent**: reads context, proposes high-level approach.
- **Act / Editor agent**: applies changes, runs tools.

Verifier loops через **command execution + error feedback**.

### Связь с нашей архитектурой

Inspiration для **planner-emitter role separation** в DBT context. Currently наш planner produces structured JSON plan; emitter generates SQL. Phase 31 plan: similar to Plan-Act split но с **DBT-specific tool wrappers**:
- Planner: outputs structured plan (which models to create/modify, what's in each).
- Emitter: per-model whole-file content generation.

## Recapitulation: Phase 31 design preview

Combining evidence from above:

| Evidence source | Phase 31 design implication | Expected lift |
|---|---|---|
| Databao principle 1: up-front DB overview | Read existing project files before planner | +2-3 pp |
| Databao principle 2: restricted tool surface | Replace bash с `view_model / propose_model / run_compile` verbs | +2-4 pp |
| Databao principle 3: verifier gate | Staged `parse → compile → run → test` retry loop | +4-6 pp |
| SWE-agent edit-linter-revert | Same staged verifier с revert ability | (covered by Databao verifier) |
| aider Polyglot diff drop | Switch к multi-block whole-file emit | +4-8 pp |
| Cline/Cursor Plan-Act | Already have planner-emitter; minor refinement | +1-2 pp |

**Total estimated lift**: 13.2% (current) → **22-32%** (Phase 31 target). Full Databao 58.82% requires proprietary engineering.

## Gap acknowledgement

### Limit 1: Databao closed methodology
Blog disclosure provides three principles, but **detailed implementation hidden**. Cannot fully reproduce 58.82% без proprietary engineering effort.

### Limit 2: Phase 31 estimated lift uncertain
Compound multiple changes (whole-file format + verifier loop + restricted tools + read-before-write). Atomic ablation per change not yet measured. Total +9-23 pp estimated, но could be less if interactions negative (Phase 28 F2a-class regression possibility).

### Limit 3: DBT lane structurally different
Все compared systems (Spider-Agent, Databao, SWE-agent) — agent-style. Naшa main pipeline (Spider 1.0/BIRD/Lite/Snow) — single-pass plan→emit. **Architectural duplication** для DBT lane — extra engineering cost vs Snow/Lite focus.

### Limit 4: Coder-7B model class limit
Even с perfect scaffold, Coder-7B emitter has reasoning ceiling. Databao 58.82% likely uses larger backbone (research dossier doesn't disclose). Our Phase 31 target ~25% — within ≤30B band, but cannot match closed-API agent reasoning depth.

## Cross-references

- Spider2-DBT benchmark detail: [03_BENCHMARKS/07_spider2_dbt.md](../03_BENCHMARKS/07_spider2_dbt.md)
- DBT pipeline (current): [05_PIPELINES/05_spider2_dbt_pipeline.md](../05_PIPELINES/05_spider2_dbt_pipeline.md)
- Models discussion (Coder-7B edit format limit): [03_open_source_text2sql_models.md](./03_open_source_text2sql_models.md)
- DBT analysis (current state + future): [09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md](../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md)
- Lessons learned (Phase 31 motivation): [06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md)
- Text-to-SQL evolution: [01_text2sql_evolution.md](./01_text2sql_evolution.md)
- Per-system SOTA reviews: [02_sota_systems_2024_2026.md](./02_sota_systems_2024_2026.md)

## Источники

| Утверждение | Источник |
|---|---|
| Spider-Agent ceiling 14.7% | research dossier `outputs/REPORT_PHASE27_RESEARCHER_STRATEGY.md` §3 |
| Databao 58.82% + 3 principles | research dossier §4 Databao entry; JetBrains blog Feb 2026 |
| SWE-agent edit-linter-revert +8pp | research dossier §4 SWE-agent; Yang et al., NeurIPS 2024, arXiv 2405.15793 |
| Coder-7B 30% drop on diff format | research dossier §4 aider |
| OpenHands | Wang et al., ICLR 2025, arXiv 2407.16741 |
| Cline / Cursor / Claude Code Plan-Act pattern | own observation of public agent products |
