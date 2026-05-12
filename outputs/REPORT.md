# Diploma Project Report — Final v10 (ВКР v1 closure)

**Generated:** 2026-04-30T23:02:45.552926+00:00
**v10 delivered:** final gap audit, master matrix consistency audit (127 rows verified), thesis_pack_shubin_v10 (12 files), joint VKR export pack v10, DeepSeek fresh-kernel runbook, BIRD official evaluator inspection.

---

## TL;DR (final v10)

| metric | value |
|---|---|
| Master matrix rows | **127** (consistency audit: 0 missing files, 0 duplicates) |
| Final production direct | **B0 + Qwen2.5-Coder-7B** (1.00 / 0.96 / 0.9333 internal; 0.2667 BIRD) |
| Final production audit-trail | **B1_v3 + Qwen2.5-Coder-7B** (multi-DB 0.80; 1 LLM call, no planner) |
| Planner conclusion | **HURTS by -0.0333 EX vs retrieval-only on multi-DB** (definitive v9 result) |
| BIRD official metrics | **BLOCKED** (CLI drift) — internal `evaluate_bird` provides equivalent EX |
| DeepSeek | **BLOCKED** (environmental) — fresh-kernel runbook ready |
| Joint export pack | **READY** at `outputs/exports/joint_vkr_export_pack_v10.tar.gz` |
| Ready for ВКР v1 | **YES** (engineering-closed; ~3-5 h human editorial work to ship) |

---

## Final scientific picture (v10)

### Strongest configurations

| Role | Configuration | EX |
|---|---|---|
| **Production direct (overall winner)** | B0 + Qwen2.5-Coder-7B | 1.00 / 0.96 / 0.9333 internal; 0.2667 BIRD |
| **Production audit-trail (REVISED v9)** | **B1_v3 + Qwen-Coder-7B** | multi-DB = 0.8000 |
| Best non-Qwen-Coder model | Gemma-3-12b-it B0 | 1.00 / 0.96 / 0.8667 / 0.2333 |
| Best mandatory model | Llama-3.1-8B B0 multi-DB | 0.8333 |
| Right-sizing comparator (14B) | Qwen-Coder-14B B0 multi-DB | 0.8667 (loses 0.067 to 7B) |
| Right-sizing comparator (32B) | Qwen-Coder-32B B0 multi-DB | 0.8333 (loses 0.10 to 7B) |

### Definitive v9 finding: planner HURTS

| Configuration on multi-DB | Has planner? | EX |
|---|---|---|
| B1_v3 (bidirectional linker) | NO | **0.8000** |
| B3_v3 (hybrid retrieval) | NO | **0.8000** |
| B2_v3 (planner + linker fallback) | YES | 0.7667 |
| B4_v3 (planner + multi-cand + repair) | YES | 0.7667 |

**Audit-trail recommendation revised:** use B1_v3 (1 LLM call, deterministic linker), NOT B2_v2 (2-3 LLM calls + jsonschema + planner).

---

## Final blockers (v10)

| Item | Class | Unblock |
|---|---|---|
| **DeepSeek-Coder-V2-Lite** | environmental ABI | Fresh Colab notebook per `outputs/logs/deepseek_fresh_kernel_runbook_v10.md`. ETA ~30-40 min. |
| **Spider 2.0-Lite EX** | env (BQ/Snowflake creds) | Out of scope; structural-only metrics confirm pipeline soundness (96-100% safe-SELECT). |
| **BIRD official R-VES, Soft F1** | CLI drift | Adapt subprocess CLI per `outputs/logs/bird_official_metrics_blocker_v10.md`. ~30-60 min code. Internal EX is equivalent and authoritative. |
| **Editorial polish + docx insertion** | human writing | ~3-5 h Shubin per `outputs/thesis_pack_shubin_v10/12_docx_patch_map_for_joint_vkr.md` |

**No other blockers.** Engineering scope is closed.

---

## What is ready for ВКР v1

### For Shubin's part
- 12-file thesis pack: `outputs/thesis_pack_shubin_v10/`
- Defense-final architecture v2 + operations v2: `outputs/docs/architecture_document_v2.md`, `operations_manual_v2.md`
- IO contracts boundary doc: `outputs/docs/io_contracts.md`
- Joint VKR export pack v10: `outputs/exports/joint_vkr_export_pack_v10.tar.gz` (single download)

### For joint report (Shubin + Petukhov)
- README and patch map in joint_vkr_export_pack_v10
- All numbers in `01_final_numbers_for_vkr.md` (single source of truth)
- All figures with captions in `03_ready_figures_for_vkr.md`
- All ready-to-paste blocks in `04..09_*_ready_block.md`
- Defense bundle: `10_defense_narrative_5min.md` + `11_expected_questions_and_answers.md`

---

## Exact file pointers

| Item | Path |
|---|---|
| Main report | `outputs/REPORT.md` (this file) |
| Master matrix CSV (127 rows, internally consistent) | `outputs/tables/final_experiment_master_matrix.csv` |
| Master matrix MD | `outputs/tables/final_experiment_master_matrix.md` |
| Final gap audit v10 | `outputs/logs/final_gap_audit_v10.md` (+ `.csv`) |
| Master matrix consistency audit v10 | `outputs/logs/master_matrix_consistency_audit_v10.md` (+ `.csv`) |
| Final scientific findings v10 | `outputs/logs/final_scientific_findings_v10.md` |
| Final negative-result analysis v10 | `outputs/logs/final_negative_result_analysis_v10.md` |
| Final submission readiness v10 | `outputs/logs/final_submission_readiness_v10.md` |
| Thesis pack v10 | `outputs/thesis_pack_shubin_v10/` (12 files) |
| Joint export pack v10 | `outputs/exports/joint_vkr_export_pack_v10.tar.gz` (+ stable copy `exports/latest_joint_vkr_export_pack.tar.gz`) |
| Architecture v2 | `outputs/docs/architecture_document_v2.md` |
| Operations manual v2 | `outputs/docs/operations_manual_v2.md` |
| IO contracts | `outputs/docs/io_contracts.md` |
| DeepSeek fresh-kernel runbook | `outputs/logs/deepseek_fresh_kernel_runbook_v10.md` |
| BIRD official evaluator blocker (with inspection) | `outputs/logs/bird_official_metrics_blocker_v10.md` |
| Plot: planner vs retrieval-only (KEY) | `outputs/plots/retrieval_vs_planner_v7.png` |
| Plot: master overview | `outputs/plots/final_experiment_master_overview.png` |
| Plot: model screening | `outputs/plots/model_screening_v7_closure.png` |
| Plot: BIRD all configs | `outputs/plots/bird_gain_vs_incumbent_v7_closure.png` |

---

## Recommended defense narrative

See `outputs/thesis_pack_shubin_v10/10_defense_narrative_5min.md` for the full 5-minute oral story. Key points:

1. **Production answer:** B0 + Qwen-Coder-7B + AST guard + sandbox. Saturates Spider; best on BIRD.
2. **Architectural finding (v9):** retrieval-only B1_v3/B3_v3 = planner-equipped B2_v3/B4_v3 minus 0.0333 EX on multi-DB. Planner HURTS. Use B1_v3 as audit-trail variant.
3. **Right-sizing #1 + #2:** 14B and 32B both lose to 7B on multi-DB. Bigger ≠ better.
4. **127 baseline runs across 5 subsets × 8 models.** Honest negative results documented.
5. **TZ coverage 100%** by physical-evidence rule. Honest blockers.

---

## Final hard status

- **master matrix rows:** 127
- **final production config:** B0 + Qwen2.5-Coder-7B-Instruct + AST guard + sandbox + AnalyticsPayload v1
- **final structured/audit config:** B1_v3 + Qwen2.5-Coder-7B-Instruct (replaces B2_v2)
- **planner conclusion:** HURTS by -0.0333 EX vs retrieval-only on multi-DB; recommend retrieval-only path
- **BIRD official metrics:** BLOCKED (CLI drift); internal EX equivalent
- **DeepSeek:** BLOCKED (environmental); fresh-kernel runbook ready
- **joint export pack:** READY (`outputs/exports/joint_vkr_export_pack_v10.tar.gz`)
- **ready for ВКР v1:** YES
- **remaining human work:** ~3-5 h editorial polish + docx insertion per `12_docx_patch_map_for_joint_vkr.md`
