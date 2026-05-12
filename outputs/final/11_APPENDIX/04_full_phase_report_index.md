# Full Phase Report Index

This appendix is the dossier's "table of contents to itself" for the 28-phase experimental progression. For each phase it gives the phase number, the canonical short name used elsewhere in the dossier, the date range, the headline contribution, the primary report file, and a pointer to the dossier section that uses the phase's findings. Together with [10_REFERENCES/02_internal_phase_reports.md](../10_REFERENCES/02_internal_phase_reports.md) (which lists report files and commits) this gives a complete cross-reference between phase numbers, dates, contributions, and dossier locations.

The narrative-flow rendering of these phases is in [06_EXPERIMENTAL_PROGRESSION/](../06_EXPERIMENTAL_PROGRESSION/). This appendix is the reference-style index.

## Phases 1–14: classical-benchmark sprint (March–July 2025)

| Phase | Short name | Date range | Headline contribution | Primary report | Dossier section |
|---|---|---|---|---|---|
| 1 | bootstrap | 2025-03-02 → 03-09 | First end-to-end Spider 1 pipeline; 12 % EX baseline | `outputs/REPORT_SPIDER1_BIRD_PHASE1_TO_14.md` §1 | 06/01 |
| 2 | prompt-iter | 2025-03-10 → 03-21 | Manual prompt refinement; 19 % | ibid §2 | 06/01 |
| 3 | v3-baseline | 2025-03-22 → 04-02 | First publishable Spider 1 number (29.4 %) | ibid §3 | 06/01 |
| 4 | bird-entry | 2025-04-03 → 04-12 | First BIRD pipeline submission | ibid §4 | 06/01 |
| 5 | v5-baseline | 2025-04-13 → 04-22 | BIRD baseline 24.7 %; gap-analysis | ibid §5 | 06/01 |
| 6 | schema-naive | 2025-04-23 → 05-01 | First naive schema linker; +5 pp on Spider 1 | ibid §6 | 06/01 |
| 7 | v7-link | 2025-05-02 → 05-14 | Schema linking promoted to first-class stage; Spider 1 53.1 % | ibid §7 | 06/01, 08/03 |
| 8 | bird-iter | 2025-05-15 → 05-23 | BIRD evidence-row reading attempts | ibid §8 | 06/01 |
| 9 | v9-evidence | 2025-05-24 → 06-04 | Evidence-block prompt design; BIRD 44.8 % | ibid §9 | 06/01, 09/01 |
| 10 | emitter-survey | 2025-06-05 → 06-14 | Emitter model survey (CodeS, DeepSeek-Coder, Qwen2.5-Coder) | ibid §10 | 04/02 |
| 11 | runtime-bring | 2025-06-15 → 06-23 | transformers vs vLLM evaluation; transformers retained | ibid §11 | 04/04 |
| 12 | v12-emitter | 2025-06-24 → 07-04 | Qwen2.5-Coder-7B emitter swap; Spider 1 68.0 % | ibid §12 | 06/01 |
| 13 | retry-design | 2025-07-05 → 07-15 | Validator-feedback retry prototype | ibid §13 | 06/01 |
| 14 | v14-retry | 2025-07-16 → 07-28 | Plan-then-emit + retry; Spider 1 82.1 % / BIRD 64.1 % | ibid §14 | 06/01 |

## Phases 15–22: Spider 2 entry through STAGE A1/A2/A3 (August 2025–January 2026)

| Phase | Short name | Date range | Headline contribution | Primary report | Dossier section |
|---|---|---|---|---|---|
| 15 | v15-first-bq | 2025-08-04 → 08-18 | First Spider2-Lite-BQ submission; 0 % | `REPORT_SPIDER2_V15_FIRST_BQ.md` | 06/01 |
| 16 | v16-retry-tune | 2025-08-19 → 09-02 | Retry budget tuning; Spider 1 82.1 % stable | ibid (consolidated) | 06/01 |
| 17 | v17-model-swap | 2025-09-03 → 09-21 | 4-model × 2-lane pilot; family > scale finding | `REPORT_SPIDER2_V17_MODEL_SWAP.md` | 06/01, 04/02 |
| 18 | v18-schema-first | 2025-09-22 → 10-09 | Schema-first pivot; Lite-BQ 30 % schema_valid; Spider 1 91.5 % | `REPORT_SPIDER2_V18_SCHEMA_FIRST.md` | 06/01, 08/01 |
| 19 | v19-repair | 2025-10-10 → 10-27 | Seven-patch repair sprint; Lite-BQ 3/10 dry_run_ok pilot | `REPORT_SPIDER2_V19_REPAIR_SPRINT.md` | 06/01 |
| 20 | v20-stage-A1 | 2025-10-28 → 11-15 | Identifier canonicaliser; plan_validation 42→54 % | `REPORT_SPIDER2_V20_STAGE_A1.md` | 06/01 |
| 21 | v21-A1-converge | 2025-11-16 → 12-01 | Metric-label fix + UNNEST alias trust; sv 50-52 % | `REPORT_SPIDER2_V21_STAGE_A1_CONVERGE.md` | 06/01 |
| 22 | v22-A1+A2+A3 | 2025-12-02 → 2026-01-14 | All-columns + join-hints + Family C; sv 54 %; pack-thinness audit | `REPORT_SPIDER2_V22.md` | 06/01, 07/04 |

## Phases 23–26: orchestration, DBT, research handoff (January–March 2026)

| Phase | Short name | Date range | Headline contribution | Primary report | Dossier section |
|---|---|---|---|---|---|
| 23 | v23-full-diag | 2026-01-15 → 02-04 | Concurrent BG inference OOM diagnosis; DBT 10.4 % partial | `REPORT_SPIDER2_V23_FULL_DIAGNOSTIC.md` | 06/01, 08/09 |
| 24 | v24-orch-fix | 2026-02-05 → 02-19 | GPU lock + sequential runner; pilot 50 reproduces v22 exactly | `REPORT_SPIDER2_V24_ORCH_FIX.md` | 06/01, 04/09 |
| 25 | v25-dbt-stable | 2026-02-20 → 03-08 | DBT stable rerun; 13.2 % publication figure | `REPORT_SPIDER2_V25_DBT_STABLE.md` | 09/04 |
| 26 | v26-research | 2026-03-09 → 04-03 | Cross-DB-drift diagnostic; F1 plan formalised | `REPORT_SPIDER2_V26_RESEARCH_HANDOFF.md` | 06/02 |

## Phases 27–28: grounding breakthrough and dialect closure (April–May 2026)

| Phase | Short name | Date range | Headline contribution | Primary report | Dossier section |
|---|---|---|---|---|---|
| 27 | v27-F1 | 2026-04-04 → 04-26 | Per-task BM25 + AST guard + PK/FK; Snow 0/10→8/10 sv | `REPORT_SPIDER2_V27_F1_GROUNDING.md` | 06/03, 08/05 |
| 28a | v28-F2a-regression | 2026-04-27 → 05-03 | F2a auto-upper hypothesis tested; falsified by catalog probe | `REPORT_SPIDER2_V28_F2A_REGRESSION.md` | 06/04 |
| 28b | v28-revert-A | 2026-05-04 → 05-08 | F2a reverted; F4 + F4c retained; pilot 10 4/10 exec_ok | `REPORT_SPIDER2_V28_REVERT_A.md` | 06/04, 08/06 |
| 28-FULL | v28-full | 2026-05-09 → ongoing | FULL Snow 547 + Lite-Snow 207 baseline run | `REPORT_SPIDER2_V28_FULL_BASELINE.md` *(pending)* | 06/05 |

## Phases 29–31: planned next-quarter work (post-thesis)

These phases are scoped in [09_RESULTS_ANALYSIS/](../09_RESULTS_ANALYSIS/) but are not part of the thesis publication figure. They are recorded here for completeness.

| Phase | Short name | Target benchmarks | Headline plan |
|---|---|---|---|
| 29 | multi-shot-snow | Snow, Lite-Snow | Multi-shot synthesis on schema_valid-but-not-exec residual tasks; F4c regex coverage audit |
| 30 | bq-port | Lite-BQ | Port F1 grounding + F4 dialect fixers to BQ; expected 30 % → ≈ 38 % lift |
| 31 | dbt-architecture | DBT | dbt-parse pre-check + manifest-aware planner + rubric-feedback retry; expected 13.2 % → ≈ 30-35 % |

## Cross-cutting audit and diagnostic logs

The phase-aligned audit memos that are referenced from multiple dossier sections:

| Log file | Source phase | Used in |
|---|---|---|
| `outputs/logs/phase09_bird_evidence_audit.md` | 9 | 07/04 §2, 09/01 §2.4 |
| `outputs/logs/phase19_pack_thinness_audit.md` | 19 | 07/04 §3 |
| `outputs/logs/phase23_orchestration_oom_diagnostic.md` | 23 | 08/09 §2 |
| `outputs/logs/phase27_bm25_partition_design.md` | 27 | 08/03 §4 |
| `outputs/logs/phase27_pk_fk_injection_design.md` | 27 | 08/04 §3 |
| `outputs/logs/phase28_catalog_probe_patents.md` | 28a | 06/04 §4 (Claim 3 of thesis) |
| `outputs/logs/phase28_f4_wrap_design.md` | 28b | 08/06 §2 |
| `outputs/logs/final_scientific_findings.md` | aggregate | 07/02 cross-cutting observations |
| `outputs/logs/final_negative_result_analysis.md` | aggregate | 06/06 lessons-learned |

## Reading order recommendations

For a reader landing on this index, the recommended reading orders are:

* **Skim-only readers (15 minutes)**: Phase 18 (schema-first pivot) → Phase 22 (final classical numbers) → Phase 27 (F1 grounding breakthrough) → Phase 28b (revert + F4 closure). These four phases compress the dossier's technical arc.
* **Methodological focus (45 minutes)**: Add Phase 23 (orchestration diagnostic) and Phase 28a (F2a falsification via catalog probe). These illustrate the methodological-discipline claim — Claim 3 of the thesis.
* **Complete-narrative readers (2 hours)**: Sequential through [06_EXPERIMENTAL_PROGRESSION/](../06_EXPERIMENTAL_PROGRESSION/), which renders the phases as a coherent story rather than as a tabular index.

## Convention notes

* Date ranges are inclusive on both ends.
* "Short name" is the form used elsewhere in the dossier when a phase is referenced in running text (e.g. "v22" for Phase 22, "F1" for the Phase 27 grounding stack, "F4" for the Phase 28 wrapper).
* Phases 16, 17b, 19b, 21b, etc. exist as sub-phases internally (small follow-up patches) but are not separately indexed here; they are folded into the parent phase's row.
* Phases 1–14 are consolidated into a single primary report because the per-phase artefacts are short and the narrative interest is the cumulative classical-benchmark sprint, not the individual increments. The cumulative report `REPORT_SPIDER1_BIRD_PHASE1_TO_14.md` is structured as one section per phase.

This index is regenerated at the close of each phase. The next regeneration is scheduled for Phase 28 FULL closure, at which point the pending row will receive its final headline numbers and the row's dossier-section pointer will be updated to point at the populated [06_EXPERIMENTAL_PROGRESSION/05_phase28_full_baseline.md](../06_EXPERIMENTAL_PROGRESSION/05_phase28_full_baseline.md).
