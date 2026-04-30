# Full closure plan

**Generated:** 2026-04-30T19:42:44.668093+00:00

## Canonical matrix scope
- **Benchmarks:** smoke_10, smoke_25, multidb_30, bird_minidev_30, spider2lite_30 (5)
- **Baselines:** B0, B1, B2_v2, B3_v2, B4_v2 (5)
- **Models:** Qwen2.5-Coder-7B-Instruct, Qwen2.5-Coder-14B-Instruct, Llama-3.1-8B-Instruct, Qwen2.5-7B-Instruct, DeepSeek-Coder-V2-Lite-Instruct (5)
- **Total logical cells:** 125 (5 × 5 × 5)

## Status counts
- ✅ done: **80**
- ❌ missing: **20**
- 🚫 blocked: **25**
- ⚪ not_applicable: 0

## Per-model summary

| Priority | Model | Done | Missing | Blocked |
|---|---|---|---|---|
| P0 | Qwen2.5-Coder-7B-Instruct | 25/25 | 0 | 0 |
| P0 | Llama-3.1-8B-Instruct | 25/25 | 0 | 0 |
| P0 | Qwen2.5-Coder-14B-Instruct | 16/25 | 9 | 0 |
| P1 | Qwen2.5-7B-Instruct | 14/25 | 11 | 0 |
| P2 | DeepSeek-Coder-V2-Lite-Instruct | 0/25 | 0 | 25 |

## Priority order for closure (this iteration)

### P0 (defense-critical) — 9 runs to add
1. **Qwen-Coder-7B fill** — close `B1, B3_v2, B4_v2` on bird/spider2lite (6 runs)
2. **Llama-3.1-8B fill** — close `B2_v2, B3_v2, B4_v2` on smoke/multidb (9 runs) + `B1, B3_v2, B4_v2` on external (6 runs) = 15 runs
3. **Qwen-Coder-14B fill** — close `B2_v2, B3_v2, B4_v2` on smoke/multidb (9 runs) + `B0, B1, B2_v2, B3_v2, B4_v2` on external (10 runs) = 19 runs

### P1 — 11 runs to add
4. **Qwen2.5-7B-Instruct comparator extension** — minimum `B0, B1, B2_v2` on each of 5 benchmarks = 13 missing (2 already done on smoke_10)

### P2 — 25 blocked
5. **DeepSeek-Coder-V2-Lite-Instruct** — environmental blocker (transformers 5.0 ABI vs trust_remote_code modeling). Documented as blocker; clean-notebook unblock recipe in `outputs/tables/deepseek_blocker_reproduction_checklist.csv`.

## Realistic closure scope this iteration

Given A100 budget (~5 min per run on 30-item benchmarks, ~2 min on smoke):

**Aim to add ~30-50 runs in batches:**
- Batch 01: Qwen-Coder-7B external fill (6 runs, ~30 min)
- Batch 02: Llama-3.1-8B internal layered fill (9 runs, ~30 min)
- Batch 03: Llama-3.1-8B external fill (6 runs, ~30 min)
- Batch 04: Qwen-Coder-14B internal layered fill (9 runs, ~30 min)
- Batch 05: Qwen-Coder-14B external fill (10 runs, ~50 min)
- Batch 06: Qwen2.5-7B-Instruct B0/B1/B2_v2 across 5 benchmarks (13 runs, ~50 min)
- Batch 07: DeepSeek final blocker artifact (no runs)

**Total estimated wall time:** ~3-4 hours on A100. Run as detached subprocess BG with incremental Drive sync.

## Stop rule
Phase done when every cell in `outputs/tables/full_closure_gap_matrix.csv` is one of:
- `done` with a real artifact, OR
- `blocked` with a real reproduction-checklist artifact, OR
- `not_applicable` with a one-line explanation.
