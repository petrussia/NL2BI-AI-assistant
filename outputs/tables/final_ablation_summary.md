# Final Ablation Summary

Generated at: 2026-04-29T14:44:56.644440+00:00

## Qwen2.5-Coder-7B-Instruct (primary model) on smoke10

| Baseline | EX | Executable | Plan valid | Avg reduction | Notes |
|---|---|---|---|---|---|
| B0 | 1.0000 | 10 / 10 | — | — | |
| B1 | 1.0000 | 10 / 10 | — | 0.475 | |
| B2_v0 | 0.7000 | 9 / 10 | 9 | 0.475 | |
| B2_v1 | — | — | — | — | not run |
| B3 | 0.2000 | 2 / 10 | 2 | 0.475 | |
| B4-lite | 0.2000 | 2 / 10 | 2 | 0.475 | |

## Qwen2.5-Coder-7B-Instruct on smoke25

| Baseline | EX | Executable | Plan valid | Avg reduction | Notes |
|---|---|---|---|---|---|
| B0 | 0.9600 | 25 / 25 | — | — | |
| B1 | 0.9600 | 25 / 25 | — | 0.58 | |
| B2_v1 | — | — | — | — | not run (deferred / lost-bridge incident) |

## Cross-model comparator(s) on smoke10

| Model | Baseline | EX | Executable | Notes |
|---|---|---|---|---|
| `Qwen/Qwen2.5-7B-Instruct` | B0 | 0.6000 | 9 / 10 | comparator |
| `Qwen/Qwen2.5-7B-Instruct` | B1 | 1.0000 | 10 / 10 | comparator |
