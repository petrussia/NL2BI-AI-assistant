# Stage F2: rewrite architecture_document.md and operations_manual.md
# with final numbers, v2 baselines, defense-ready language.

import csv
import datetime as dt
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def load(prefix):
    p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return next(csv.DictReader(p.open(encoding='utf-8')), None)

def fex(prefix):
    m = load(prefix)
    if not m: return '—'
    try: return f'{float(m["ex"]):.4f}'
    except: return '—'


arch = OUTPUTS/'docs'/'architecture_document.md'
arch.write_text(f'''# Architecture document — final (defense-ready)

**Date:** {NOW}
**Project:** NL2BI-AI-assistant — natural-language → SQL technology for extracting and processing data from a heterogeneous source array.
**Author of this subsystem:** Шубин Денис Алексеевич (Shubin). Visualisation/BI subsystem (out of scope) — Petukhov.

---

## 1. High-level architecture

```
[NL question]
     │
     ▼
[Query Analysis]  (rule-based intent + signals; closes ТЗ 2.2.1)
     │
     ▼
[Schema Linking]  (lexical, token-overlap, table×2 + col×1, min_score=0.5)
     │
     ▼ (optional, for B3 family)
[Knowledge Channel] (DISABLED in B3_v2 — was harmful prompt noise on Spider)
     │
     ▼
[Planner]  (JSON plan, jsonschema-validated)
     │       on invalid plan → [B1 fallback (single-shot SQL)]
     ▼
[Plan Validator]  (Draft 2020-12 jsonschema vs `plan_schema_v1.json`)
     │
     ▼
[SQL Synthesizer]  (prompt = full schema + plan)
     │
     ▼
[Validation Gate] (SELECT-only AST guard, regex-level forbidden keywords)
     │
     ▼ (multi-cand, k=3, T=0.7, top_p=0.95 — only for B4 family)
[Consistency Selection] → if no executable: [B1 fallback (B4_v2 only)]
     │
     ▼
[Executor]  (SQLite, 8s `func_timeout`)
     │
     ▼
[Postprocess]  (normalize_rows + compute_summary)
     │
     ▼
[Analytics Handoff Payload v1] → consumed by Petukhov's BI subsystem
```

Diagrams: [outputs/plots/system_architecture_overview.png](../plots/system_architecture_overview.png),
[outputs/plots/ablation_pipeline_ladder.png](../plots/ablation_pipeline_ladder.png).

---

## 2. Components

| Layer | Component | Module | Closes |
|---|---|---|---|
| 1 | Query analyzer (NL→intent+signals) | `repo/src/evaluation/query_analysis.py` | ТЗ 2.2.1 |
| 2 | Schema linker (lex) | `repo/src/evaluation/baselines.py::lexical_schema_linking` | ТЗ 2.2.2 |
| 2b | Cross-DB retrieval helper | `repo/src/evaluation/retrieval.py` | ТЗ 2.2.2 |
| 3 | Planner v2 (B2_v2/B3_v2/B4_v2) | `baselines_b2_v2.py`, `baselines_b3_v2.py` | ТЗ 2.2.4 |
| 4 | Plan validator | `repo/docs/plan_schema_v1.json` + jsonschema | ТЗ 2.2.4 |
| 5 | SQL synthesizer | `baselines_*` make_*_sql_prompt | ТЗ 2.2.3 |
| 6 | SELECT-only AST guard | `baselines_b4_final.py::is_safe_select` | ТЗ 2.2.3 (safety) |
| 7 | Multi-cand + repair | `baselines_b4_v2.py::consistency_pick_v2` | ТЗ 2.2.4 |
| 8 | B1 fallback safety net | inline in B2_v2/B3_v2/B4_v2 | engineering |
| 9 | Executor + 8s timeout | `func_timeout`-wrapped `execute_sql` | ТЗ 2.2.3 (performance) |
| 10 | Postprocess + handoff | `repo/src/evaluation/postprocess.py` | ТЗ 2.2.5 / 2.2.6 |
| 11 | Bridge tooling | notebook cell `7f6bca53` + `tools/exec_remote.py` | infrastructure |

---

## 3. Baseline ladder and observed accuracy

| Baseline | smoke_10 | smoke_25 | multidb_30 | Notes |
|---|---|---|---|---|
| B0 (full schema, single-shot) | {fex("b0_spider_smoke10")} | {fex("b0_spider_smoke25")} | {fex("b0_multidb30_v2")} | Strongest direct config |
| B1 (lex schema linking) | {fex("b1_spider_smoke10")} | {fex("b1_spider_smoke25")} | {fex("b1_multidb30_v2")} | Reduces prompt 50%, hurts on multidb |
| B2_v0 (Plan→SQL v0) | {fex("b2_spider_smoke10")} | — | — | Initial planner |
| B2_v1 (subq+distinct) | {fex("b2v1_spider_smoke10")} | — | {fex("b2v1_multidb30")} | Patches over v0 |
| **B2_v2 (B1-fallback + anti-overengineering)** | **{fex("b2v2_spider_smoke10")}** | — | **{fex("b2v2_multidb30")}** | Targeted fixes, safety net |
| B3_v1 (adaptive dual retrieval) | {fex("b3v1_spider_smoke10")} | — | {fex("b3v1_multidb30")} | Knowledge channel partial-off |
| **B3_v2 (knowledge OFF + B1 fallback)** | **{fex("b3v2_spider_smoke10")}** | — | **{fex("b3v2_multidb30")}** | +0.50/+0.27 vs v1 |
| B4-lite | {fex("b4_spider_smoke10")} | — | — | Initial validation+repair |
| B4_final (B3_v1 + multi-cand + repair) | {fex("b4_final_spider_smoke10")} | — | {fex("b4_final_multidb30")} | Capped by upstream plan failures |
| **B4_v2 (B3_v2 + multi-cand + B1 fallback ×2)** | **{fex("b4v2_spider_smoke10")}** | — | **{fex("b4v2_multidb30")}** | Same +Δ as B3_v2 |

Cross-model on smoke_10:
- Qwen2.5-7B-Instruct (no Coder fine-tune): B0 = {fex("b0_qwen_qwen2.5_7b_instruct_smoke10")}, B1 = {fex("b1_qwen_qwen2.5_7b_instruct_smoke10")}
- Llama-3.1-8B-Instruct: B0 = {fex("b0_llama_3p1_8b_instruct_smoke10")}, B1 = {fex("b1_llama_3p1_8b_instruct_smoke10")}
- Qwen2.5-Coder-14B-Instruct: B0 = {fex("b0_qwen2p5_coder_14b_instruct_smoke10")}, B1 = {fex("b1_qwen2p5_coder_14b_instruct_smoke10")}

---

## 4. Constraints and assumptions

1. **Hardware:** NVIDIA L4 24 GB, 4-bit nf4 bitsandbytes quantisation. Higher-precision runs would shift absolute EX but not the relative ordering.
2. **Benchmark:** Spider dev (n=1034) and 3 subsets: smoke_10, smoke_25, multidb_30 (6 distinct DBs).
3. **Decoding:** greedy for B0/B1/B2/B3 (`do_sample=False`); 3-cand sampling for B4 family (T=0.7, top_p=0.95).
4. **Plan schema:** `plan_schema_v1.json` (Draft 2020-12, additionalProperties:false). Required: intent, tables, operations.
5. **Safety:** SELECT-only via regex AST guard; no INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/PRAGMA/ATTACH/DETACH/GRANT/REVOKE.
6. **Execution sandbox:** SQLite read-only; 8 second timeout via `func_timeout`.

---

## 5. Recommended production configuration (defense recommendation)

**Use B0 + Qwen2.5-Coder-7B-Instruct (4-bit) + SELECT-only AST guard + 8s SQLite timeout + analytics handoff post-processor.**

- It is the **single strongest direct configuration** in this evaluation slice (1.00 / 0.96 / 0.9333).
- It is the **fastest** path (no planner, no multi-cand, no repair).
- B1 only when the schema is too large to fit in the model context.
- B3_v2 / B4_v2 only when downstream systems require an auditable JSON plan or a structured repair trail. Layered stack provides engineering safety, **not** EX gains on this benchmark.

**Why not B3_v2/B4_v2 in production:** they trade a smaller EX loss for the ability to validate, repair, and select among candidates. On Spider with Qwen-Coder-7B, B0 already saturates accuracy — the safety net is paying for nothing.

---

## 6. Trade-offs

| Choice | Pros | Cons |
|---|---|---|
| Full-schema prompt (B0) | Highest EX | Largest token budget; needs context window |
| Lex schema linker (B1) | 50% prompt reduction | Over-prunes on schema-diverse benchmarks |
| Plan-then-SQL (B2/B3/B4) | Auditable, repair-able | EX cost vs B0 on this benchmark |
| Multi-candidate (B4 family) | Robustness via consistency vote | 3× generation latency per item |
| Bounded repair | Self-correction on SQL errors | Negligible EX gain when plan is broken upstream |
| B1 fallback safety net (v2) | Guarantees layered ≥ B1 - noise | None observed |

---

## 7. Risk controls

- **All SQL is SELECT-only,** verified by regex AST guard before execution.
- **All execution is sandboxed** in a `func_timeout`-wrapped SQLite call; max 8 seconds per query.
- **All generated SQL is logged** per-item with raw model output, gold SQL, executable flag, match flag, and error type (`outputs/predictions/*.jsonl`).
- **All metrics are reproducible** by re-running the corresponding `tools/remote_scripts/NN_*.py` against a kernel with the same model loaded.
- **Negative results are documented honestly** — no inflation of layered baseline EX.

---

## 8. Connection diagram between components

```
Query Analyzer ──▶ Schema Linker ──▶ Reduced Schema ─┐
                                                     ├─▶ Planner ─▶ Plan Validator
Full Schema ─────────────────────────────────────────┘                  │
                                                                        ▼
                                                                  SQL Synthesizer
                                                                        │
                                                                        ▼
                                                                Validation Gate
                                                                        │
                                                                        ▼
                                                              Multi-Cand / Repair
                                                                        │
                                                                        ▼
                                                                    Executor
                                                                        │
                                                                        ▼
                                                                   Postprocess
                                                                        │
                                                                        ▼
                                                          Analytics Handoff Payload v1
```

---

## 9. References

- Master experiment matrix: [outputs/tables/final_experiment_master_matrix.md](../tables/final_experiment_master_matrix.md)
- Multi-DB scientific slice: [outputs/logs/multidb30_scientific_readout.md](../logs/multidb30_scientific_readout.md)
- Negative-result analysis: [outputs/logs/final_negative_result_analysis.md](../logs/final_negative_result_analysis.md)
- Plan schema (canonical): [repo/docs/plan_schema_v1.json](../../repo/docs/plan_schema_v1.json)
- Component registry: [outputs/tables/component_registry.csv](../tables/component_registry.csv)
- IO contracts (boundary with Petukhov's BI): [outputs/docs/io_contracts.md](io_contracts.md)
''', encoding='utf-8')


ops = OUTPUTS/'docs'/'operations_manual.md'
ops.write_text(f'''# Operations manual — final (defense-ready)

**Date:** {NOW}
**Author:** Шубин Денис Алексеевич

---

## 1. Runtime profile

- **GPU:** NVIDIA L4 24 GB (or stronger). Confirmed working: Qwen-Coder-7B, Qwen-Instruct-7B, Llama-3.1-8B-Instruct, Qwen-Coder-14B in 4-bit nf4 bitsandbytes.
- **CPU:** standard Colab default (12+ GB RAM).
- **Python:** 3.10+ (tested on 3.12.13).
- **Key dependencies:** `transformers>=4.45`, `bitsandbytes>=0.43`, `accelerate>=0.34`, `func_timeout`, `jsonschema`, `sentencepiece`, `safetensors`.
- **Disk:** ~30 GB for model cache (Qwen-Coder-7B ≈ 15 GB, Llama-3.1-8B ≈ 16 GB, Qwen-Coder-14B ≈ 28 GB on disk fp16; 4-bit on-disk is similar — quant happens at load).

## 2. How to run experiments — end-to-end recipe

1. **Mount Drive and start the bridge.**
   - In the Colab notebook `notebooks/example.ipynb`, run cell `AGENT_BRIDGE_SETUP` (id `7f6bca53`). It starts a Flask server in the kernel and exposes it via a free Cloudflare tunnel.
   - The cell prints `BRIDGE_URL: https://<random>.trycloudflare.com`.
   - Copy that URL into `tools/.bridge_url`.

2. **Sanity-check the bridge.**
   ```bash
   python tools/exec_remote.py --health
   ```
   Should print `{{"ok": true, "pid": <int>}}`.

3. **Bootstrap helpers and load the primary model (Qwen-Coder-7B).**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/30_kernel_bootstrap.py
   ```
   Cold cache load: ~3 min. Hot cache: ~30 sec.

4. **Run a baseline.** Example for B0 smoke_10:
   - the run is *internal* to the bootstrap script for B0/B1; for B2/B3/B4 use the dedicated BG scripts (`13_b2_smoke10_bg.py`, `23_b2_v1_smoke10_bg.py`, `54_b2v1_b3v1_b4final_smoke10_bg.py`, `62_b3v2_b4v2_smoke10_bg.py`, `74_b2v2_smoke10_multidb30_bg.py`).
   - Each BG script writes per-item predictions to `outputs/predictions/`, metrics to `outputs/metrics/`, and a task log to `outputs/logs/`.

5. **Poll BG progress.**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/_peek_b3v2.py
   ```
   (or `_peek_qwen14b.py`, `_peek_llama.py`, etc.)

6. **Consolidate.**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/65_final_consolidation_v2.py
   ```
   Rebuilds the master matrix CSV/MD and the master overview plot.

7. **Build deliverable tarball.**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/59_final_tarball.py
   ```
   Tarball lands at `/content/drive/MyDrive/diploma_plan_sql/exports/latest_tz_closure.tar.gz`.

8. **Sync to local mirror.** Either download the tarball via the bridge `--download` flag, or extract via the b64-encoded path used in `tools/remote_scripts/_upload_local_mirror_v2.py`.

## 3. How to restore the bridge after it dies

Cloudflare quickrun tunnels are ephemeral; they die when the Colab cell or kernel restarts. Recovery:

1. In the notebook, re-run cell `7f6bca53`. A fresh URL is printed.
2. Update `tools/.bridge_url` with the new URL.
3. Re-run `python tools/exec_remote.py --health` to confirm.
4. The previous BG threads in the kernel are still alive if the kernel itself wasn't restarted; otherwise re-bootstrap helpers via `30_kernel_bootstrap.py`.

## 4. How to reproduce the master numbers

1. Mount Drive, restore Spider via `31_restore_drive_spider.py` if missing.
2. Restore local mirror to Drive via `_upload_local_mirror_v2.py` if Drive content was wiped.
3. Bootstrap kernel: `30_kernel_bootstrap.py`.
4. Re-run baselines in this order:
   - `54_b2v1_b3v1_b4final_smoke10_bg.py` (B2_v1, B3_v1, B4_final smoke_10)
   - `56_multidb30_5baselines_bg.py` (B0, B1, B2_v1, B3_v1, B4_final on multidb_30)
   - `62_b3v2_b4v2_smoke10_bg.py` (B3_v2, B4_v2 smoke_10 + multidb_30)
   - `74_b2v2_smoke10_multidb30_bg.py` (B2_v2)
   - `67_llama_b0_b1_bg.py` (Llama smoke_10)
   - `71_qwen14b_bg.py` (Qwen-Coder-14B smoke_10 + multidb_30)
5. Final consolidation: `65_final_consolidation_v2.py` then `66_final_docs_v2.py` then `59_final_tarball.py`.

## 5. Failure handling

| Failure | Symptom | Recovery |
|---|---|---|
| Bridge tunnel dead | `getaddrinfo failed` from `exec_remote.py` | Re-run cell `7f6bca53`; update `tools/.bridge_url`. |
| Drive content lost | Empty subdirectories under `/content/drive/MyDrive/diploma_plan_sql/` | Re-run `31_restore_drive_spider.py` then `_upload_local_mirror_v2.py`. |
| Model download interrupted | `from_pretrained` raises connection error | Re-run BG script — `from_pretrained` resumes from cache. |
| OOM on model load | `CUDA out of memory` | Free prior model first (BG scripts do this); reduce concurrent threads. |
| Plan parse failure | Predictions show `path=b1_fallback_invalid_plan` | Expected; B1 fallback handles this. |
| SQL execution timeout | `error_type=timeout` in predictions | Per-query 8s budget; gold SQL timed out too is rare. |

## 6. Honest blockers

- **DeepSeek-Coder-V2-Lite-Instruct** — environmental: `trust_remote_code` modeling file imports `is_torch_fx_available` which is not exported by current transformers. Unblock requires a fresh kernel with `transformers==4.39.x`. See `outputs/logs/deepseek_blocker_final.md`.
- **Llama-3.1-8B-Instruct** — was credential-blocked (no HF_TOKEN); **resolved** when the user attached HF_TOKEN to the runtime. See `outputs/logs/llama_blocker_final.md`.

## 7. Where things live

| Artifact | Path |
|---|---|
| Master matrix CSV | `outputs/tables/final_experiment_master_matrix.csv` |
| Master matrix MD | `outputs/tables/final_experiment_master_matrix.md` |
| Master plot | `outputs/plots/final_experiment_master_overview.png` |
| Multi-DB scientific readout | `outputs/logs/multidb30_scientific_readout.md` |
| Final REPORT | `outputs/REPORT.md` |
| Strict TZ coverage | `outputs/logs/tz_coverage_final_strict_v2.md` |
| Thesis pack | `outputs/thesis_pack_shubin/` |
| Latest tarball | `/content/drive/MyDrive/diploma_plan_sql/exports/latest_tz_closure.tar.gz` |
| Local mirror | the user's machine: `d:\\HSE\\Диплом\\NL2BI-AI-assistant\\` |
''', encoding='utf-8')

print(f'WROTE {arch}')
print(f'WROTE {ops}')
