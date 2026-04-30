# Final numbers for joint report (v1)

**Generated:** 2026-04-30T19:42:45.696599+00:00
**Authoritative source:** `outputs/tables/final_experiment_master_matrix.csv`

> Все числа в общей ВКР должны совпадать с этим файлом. Если какое-то число отсюда нельзя вставить как есть — обнови в master matrix или скажи, и пересобери pack.

## 1. Internal core benchmarks (Spider, EX = Execution Match)

| Baseline | Model | smoke_10 | smoke_25 | multidb_30 |
|---|---|---|---|---|
| **B0** | Qwen2.5-Coder-7B | **1.0000 (10/10)** | **0.9600 (24/25)** | **0.9333 (28/30)** |
| B1 | Qwen2.5-Coder-7B | 1.0000 (10/10) | 0.9600 (24/25) | 0.7667 (23/30) |
| B2_v2 | Qwen2.5-Coder-7B | 0.8000 (8/10) | 0.9600 (24/25) | **0.8000 (24/30)** |
| B3_v2 | Qwen2.5-Coder-7B | 0.8000 (8/10) | 0.9600 (24/25) | 0.7333 (22/30) |
| B4_v2 | Qwen2.5-Coder-7B | 0.8000 (8/10) | 0.9600 (24/25) | 0.7333 (22/30) |

## 2. Mandatory comparator — Llama-3.1-8B-Instruct

| Baseline | smoke_10 | smoke_25 | multidb_30 | BIRD-mini-dev |
|---|---|---|---|---|
| B0 | 0.8000 (8/10) | 0.6000 (15/25) | **0.8333 (25/30)** | 0.1333 (4/30) |
| B1 | 0.9000 (9/10) | 0.7200 (18/25) | 0.7000 (21/30) | 0.1333 (4/30) |
| B2_v2 | 0.8000 (8/10) | 0.8000 (20/25) | 0.7333 (22/30) | 0.0667 (2/30) |
| B3_v2 | 0.8000 (8/10) | 0.7600 (19/25) | 0.6667 (20/30) | — |
| B4_v2 | 0.8000 (8/10) | 0.7600 (19/25) | 0.6333 (19/30) | — |

## 3. Larger model comparator — Qwen2.5-Coder-14B-Instruct

| Baseline | smoke_10 | smoke_25 | multidb_30 |
|---|---|---|---|
| B0 | 1.0000 (10/10) | 0.9600 (24/25) | **0.8667 (26/30)** ⬅ ниже 7B |
| B1 | 1.0000 (10/10) | 0.9200 (23/25) | 0.7667 (23/30) |

## 4. External validation — BIRD-Mini-Dev (full SQLite EX)

| Baseline | Qwen2.5-Coder-7B | Llama-3.1-8B |
|---|---|---|
| B0 | **0.2667 (8/30)** | 0.1333 (4/30) |
| B1 | 0.2000 (6/30) | 0.1333 (4/30) |
| B2_v2 | 0.2000 (6/30) | 0.0667 (2/30) |

## 5. External validation — Spider 2.0-Lite (prediction-only, structural metrics)

EX is N/A on Spider 2.0-Lite — gold queries target BigQuery/Snowflake; no execution from Colab. Structural safety holds:
- Qwen-Coder-7B B0: safe-SELECT 96.7%, has-JOIN 40%
- Qwen-Coder-7B B2_v2: safe-SELECT 96.7%, has-JOIN 53.3%
- Llama-3.1-8B B0: safe-SELECT 100%, has-JOIN 66.7%
- Llama-3.1-8B B2_v2: safe-SELECT 100%, has-JOIN 43.3%

## 6. Strongest configurations (defense-grade)

| Role | Configuration | EX |
|---|---|---|
| **Strongest direct & strongest overall** | B0 + Qwen2.5-Coder-7B-Instruct | **1.00 / 0.96 / 0.9333** (smoke_10 / smoke_25 / multi-DB) |
| **Strongest layered** | B2_v2 + Qwen2.5-Coder-7B-Instruct on multi-DB | **0.80** — beats B1 = 0.7667 by **+0.0333** |
| **Strongest layered (smoke_25 parity)** | B2_v2 / B3_v2 / B4_v2 + Qwen2.5-Coder-7B | **0.96** — match B0/B1 (parity) |
| **Mandatory model B0 best** | Llama-3.1-8B B0 multi-DB | 0.8333 (competitive vs Coder family) |
| **External BIRD strongest** | B0 + Qwen2.5-Coder-7B | 0.2667 (vs Llama 0.1333 = 2× ratio) |

## 7. Production recommendation

**B0 + Qwen2.5-Coder-7B-Instruct (4-bit nf4 or BF16) + SELECT-only AST guard + 8s SQLite timeout + AnalyticsPayload v1 post-processor.**

- Strongest EX on every internal subset
- Strongest EX on the harder external benchmark (BIRD)
- Cheapest GPU footprint (fits L4 24 GB)
- Stronger than Coder-14B on multi-DB (right-sizing argument)
- Single LLM call per query (lowest latency)

**Audit-trail variant:** B2_v2 + Qwen2.5-Coder-7B (when downstream needs JSON plan).

## 8. Honest blockers

| Item | Class | Unblock path |
|---|---|---|
| DeepSeek-Coder-V2-Lite-Instruct | environmental (transformers ABI in trust_remote_code) | Fresh Colab notebook, `transformers==4.39.3` pinned BEFORE other imports — full checklist in `outputs/tables/deepseek_blocker_reproduction_checklist.csv` |
| Spider 2.0-Lite EX evaluation | environmental (BigQuery/Snowflake credentials needed) | Out of project scope; pipeline is structurally sound (96-100% safe-SELECT) |
| Editorial polish + docx insertion | human writing | ~3-5 h Shubin manual work |
