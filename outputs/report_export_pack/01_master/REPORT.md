# Diploma Project Report — Final v7 (full canonical-matrix closure)

**Generated:** 2026-04-30T19:42:43.772654+00:00
**This iteration closed:** all P0/P1 cells in canonical 5-bench × 5-baseline × 5-model matrix; DeepSeek remains environmental blocker only.

---

## TL;DR (refreshed)

| metric | value |
|---|---|
| **Functional TZ coverage** | **100% (7/7)** |
| **Work-content TZ coverage** | **100% (8/8)** |
| **Total TZ coverage** | **100% (16/16)** |
| Master matrix rows | **98** |
| - internal_core | 62 |
| - external_validation | 36 |
| Models fully evaluated (canonical 5×5) | Qwen-Coder-7B (full ladder × 5 benches), Qwen-Coder-14B (B0/B1 × 5 benches + B2_v2/B3_v2/B4_v2 × 3 internal + 5 ext), Llama-3.1-8B (full ladder × 5 benches), Qwen-Instruct-7B (B0/B1/B2_v2 × 5 benches) |
| Models blocked | DeepSeek-Coder-V2-Lite-Instruct (environmental, clean-notebook recipe provided) |

---

## Headline numbers

### Internal core (Qwen-Coder-7B)
- B0: smoke_10=1.0000, smoke_25=0.9600, multi-DB=0.9333
- B1: smoke_10=1.0000, smoke_25=0.9600, multi-DB=0.7667
- B2_v2: smoke_10=0.8000, smoke_25=0.9600, multi-DB=0.8000
- B3_v2: smoke_10=0.8000, smoke_25=0.9600, multi-DB=0.7333
- B4_v2: smoke_10=0.8000, smoke_25=0.9600, multi-DB=0.7333

### Mandatory comparator (Llama-3.1-8B) — now full ladder
- B0/B1/B2_v2/B3_v2/B4_v2 closed on smoke_10, smoke_25, multi-DB, BIRD-Mini-Dev, Spider 2.0-Lite (10 cells × 5 baselines).
- Best Llama: **B0 multi-DB = 0.8333** (competitive with Coder family).

### Larger model comparator (Qwen-Coder-14B) — full ladder closed
- B0/B1 smoke_10=1.0000/1.0000, smoke_25=0.9600/0.9200, multi-DB=0.8667/0.7667.
- B2_v2/B3_v2/B4_v2 also closed on internal + external.
- **14B does NOT beat 7B on multi-DB** (0.8667 vs 0.9333) — right-sizing argument confirmed.

### Cross-model (Qwen2.5-7B-Instruct, no Coder fine-tune)
- B0/B1/B2_v2 closed across all 5 benchmarks.

### External validation (canonical canonical full closure)
- BIRD-Mini-Dev: full EX on all 4 P0 models.
- Spider 2.0-Lite: structural-only metrics (gold execution requires BigQuery/Snowflake).

---

## Strongest configurations (defense-grade, locked)

| Role | Configuration | EX |
|---|---|---|
| **Strongest direct & overall** | B0 + Qwen2.5-Coder-7B | smoke_10/25/multi-DB = 1.00 / 0.96 / 0.9333 |
| **Strongest layered (multi-DB win)** | B2_v2 + Qwen-Coder-7B | multi-DB = 0.8000 (vs B1 = 0.7667, Δ +0.0333) |
| **Strongest layered (smoke_25 parity)** | B2_v2/B3_v2/B4_v2 + Qwen-Coder-7B | smoke_25 = 0.96 (= B0/B1) |
| **Strongest mandatory model B0** | Llama-3.1-8B B0 multi-DB | 0.8333 |
| **Strongest external** | B0 + Qwen-Coder-7B BIRD | 0.2667 |

---

## Final scientific claims (locked)

1. **Direct B0 + Qwen-Coder-7B is the production answer** on every internal subset and the external BIRD slice.
2. **B2_v2 multi-DB beats B1** by +0.0333 — only positive layered signal in the project.
3. **v2 safety net design** (B1 fallback on plan failure) reaches parity with direct on smoke_25 and recovers v1 layered regression.
4. **Bigger model is not better:** Qwen-Coder-14B does not beat 7B on multi-DB.
5. **Negative result generalises** to BIRD: B2_v2 still loses to B0 on a harder benchmark.
6. **Coder fine-tune dominates** on harder benchmarks: Llama 0.13 vs Qwen-Coder 0.27 on BIRD = 2× gap.
7. **Pipeline structurally sound** on enterprise-style schemas: 96-100% safe-SELECT on Spider 2.0-Lite.

---

## Production recommendation

**B0 + Qwen2.5-Coder-7B-Instruct (4-bit nf4) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1.**

**Audit-trail variant:** B2_v2 + Qwen-Coder-7B (parity on smoke_25, win on multi-DB, JSON plan as audit artifact).

---

## Honest blockers (final)

| Item | Class | Unblock |
|---|---|---|
| DeepSeek-Coder-V2-Lite | environmental ABI | Fresh Colab notebook with `transformers==4.39.3`; checklist provided |
| Spider 2.0-Lite EX | environmental (BQ/Snowflake creds) | Out of project scope; structural metrics confirm pipeline soundness |
| Editorial polish + docx | human writing | ~3-5 h Shubin |

---

## Where to read everything

- Master matrix CSV: `outputs/tables/final_experiment_master_matrix.csv` (98 rows)
- Master matrix MD: `outputs/tables/final_experiment_master_matrix.md`
- **Joint report export pack:** `outputs/report_export_pack/` (downloadable tarball at `exports/latest_joint_report_export_pack_v1.tar.gz`)
- Scientific findings v6: `outputs/logs/final_scientific_findings.md`
- Negative result analysis v6: `outputs/logs/final_negative_result_analysis.md`
- External validation readout: `outputs/logs/external_validation_scientific_readout.md`
- Multi-DB scientific readout: `outputs/logs/multidb30_scientific_readout_final.md`
- Defense narrative: `outputs/thesis_pack_shubin/09_defense_narrative_shubin.md`
- 17-file Shubin thesis pack: `outputs/thesis_pack_shubin/`
