# Qwen2.5-Coder-14B-Instruct runtime attempt — A100 success

**Captured:** 2026-04-30T14:38:33.007726+00:00

- Model: Qwen/Qwen2.5-Coder-14B-Instruct
- GPU: NVIDIA A100-SXM4-80GB (84 GB free at start)
- Quant: 4-bit nf4 bnb, double-quant, fp16 compute
- Load: **OK** in 91.0 s, VRAM after load = 9.5 GB
- Strategy: launched as a true subprocess via `83_qwen14b_subprocess_launcher.py` because the kernel's transformers had cached `is_bitsandbytes_available()=False` from the prior install state. The subprocess gets a fresh import state.

## Runs completed

| Run | Subset | EX | Match / N |
|---|---|---|---|
| B0 | smoke_10 | 1.0000 | 10/10 |
| B1 | smoke_10 | 1.0000 | 10/10 |
| B0 | multidb_30 | 0.8667 | 26/30 |
| B1 | multidb_30 | 0.7667 | 23/30 |

## Key finding
The 14B variant **does not beat the 7B Coder on the multi-DB scientific slice** (B0 14B = 0.8667 vs 7B = 0.9333). It only ties on smoke_10 (both = 1.00).
The 14B comparator therefore **strengthens** the production recommendation for the 7B model, not weakens it.
