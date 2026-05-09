# Final numeric consistency audit
_Generated: 2026-04-30T14:50:05.209628+00:00_

## Source of truth
`outputs/tables/final_experiment_master_matrix.csv` — derived from per-run `outputs/metrics/*_metrics.csv`.

## Authoritative numbers (4-decimal)
| Key | Value |
|---|---|
| `b0_smoke10_coder7b` | 1.0000 |
| `b1_smoke10_coder7b` | 1.0000 |
| `b0_smoke25_coder7b` | 0.9600 |
| `b1_smoke25_coder7b` | 0.9600 |
| `b0_multidb30_coder7b` | 0.9333 |
| `b1_multidb30_coder7b` | 0.7667 |
| `b2v0_smoke10` | 0.7000 |
| `b2v1_smoke10` | 0.6000 |
| `b2v1_multidb30` | 0.6333 |
| `b2v2_smoke10` | 0.8000 |
| `b2v2_multidb30` | 0.8000 |
| `b3v1_smoke10` | 0.3000 |
| `b3v1_multidb30` | 0.4667 |
| `b3v2_smoke10` | 0.8000 |
| `b3v2_multidb30` | 0.7333 |
| `b4_final_smoke10` | 0.3000 |
| `b4_final_multidb30` | 0.4667 |
| `b4v2_smoke10` | 0.8000 |
| `b4v2_multidb30` | 0.7333 |
| `b0_smoke10_qwen14b` | 1.0000 |
| `b1_smoke10_qwen14b` | 1.0000 |
| `b0_multidb30_qwen14b` | 0.8667 |
| `b1_multidb30_qwen14b` | 0.7667 |
| `b0_smoke10_llama` | 0.8000 |
| `b1_smoke10_llama` | 0.9000 |
| `b0_smoke10_qwen7binst` | 0.6000 |
| `b1_smoke10_qwen7binst` | 1.0000 |

## Per-document audit

| File | Present | Size (B) | Expected hits | Suspicious decimals | Verdict |
|---|---|---|---|---|---|
| `REPORT.md` | True | 9400 | 27 | 0 | **OK** |
| `logs/final_scientific_findings.md` | True | 3468 | 16 | 0 | **OK** |
| `logs/final_negative_result_analysis.md` | True | 2125 | 18 | 2 | **CHECK** |
| `logs/multidb30_scientific_readout_final.md` | True | 1535 | 14 | 0 | **OK** |
| `thesis_pack_shubin/01_final_numbers.md` | True | 2335 | 26 | 0 | **OK** |
| `thesis_pack_shubin/02_final_tables.md` | True | 5188 | 26 | 0 | **OK** |
| `thesis_pack_shubin/04_scientific_conclusions.md` | True | 3088 | 3 | 0 | **OK** |
| `thesis_pack_shubin/09_defense_narrative_shubin.md` | True | 4146 | 3 | 0 | **OK** |
| `thesis_pack_shubin/10_answers_to_expected_questions.md` | True | 7014 | 2 | 0 | **OK** |
| `thesis_pack_shubin/11_final_insertion_blocks.md` | True | 8653 | 16 | 0 | **OK** |
| `tables/final_experiment_master_matrix.md` | True | 3163 | 27 | 0 | **OK** |

## Headline claim cross-check

- ✅ B0 + Coder-7B = 1.00 / 0.96 / 0.9333 across smoke10/smoke25/multidb_30
- ✅ B2_v2 multi-DB (0.8) beats B1 (0.7666666666666667) by ~+0.0333 (+0.0333)
- ✅ Qwen-Coder-14B B0 multi-DB (0.8666666666666667) < Qwen-Coder-7B B0 (0.9333333333333333); 14B underperforms
- ✅ B3_v2 smoke10 (0.8) − B3_v1 (0.3) ≥ +0.45
- ✅ Llama smoke_10: B0=0.8, B1=0.9
