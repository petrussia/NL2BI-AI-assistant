# DeepSeek-Coder-V2-Lite-Instruct — final blocker (A100/H100 lane)

**Refreshed:** 2026-04-30T15:24:12.101245+00:00
**Model:** `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`
**Runtime tested:** NVIDIA A100-SXM4-80GB, transformers 5.0.0, torch 2.10
**VRAM available:** 84 GB free — **NOT the constraint**
**Real constraint:** transformers ABI in the model's `trust_remote_code` modeling file

## Why VRAM is no longer the issue
On A100 80 GB the model fits trivially: 4-bit nf4 footprint of DeepSeek-V2-Lite (≈ 16B total params, MoE with ~2.4B active) ≈ 9-12 GB. We have 84 GB free.

## Why import is the issue
1. The model's `modeling_deepseek.py` (loaded under `trust_remote_code=True`) references `transformers.utils.import_utils.is_torch_fx_available`. This symbol existed in `transformers <= 4.39.x`, was renamed/moved in 4.40+, and is **fully absent** in 5.0.0.
2. The kernel's installed transformers is 5.0.0. We cannot downgrade in-place without breaking the currently-loaded Qwen-Coder runtime.
3. Isolated install via `pip install --target /tmp/ds_env transformers==4.39.x` fails at `dependency_versions_check` because pinned transformers requires pinned `tokenizers`, `accelerate`, `safetensors`, `huggingface_hub` — and even with them in the target dir, the kernel's already-loaded `tokenizers` C extension cannot be substituted at runtime (Python C extensions are dynamically linked at first import).

## Unblock — fresh Colab notebook
See `outputs/logs/deepseek_unblock_instructions.md` and `outputs/tables/deepseek_blocker_reproduction_checklist.csv` for the exact step-by-step recipe.

## Honest classification
Mandatory model from the proposal — **not evaluated in any kernel of this project** because of an environmental ABI mismatch. **3 of 4 mandatory models evaluated** (Qwen-Coder-7B, Qwen-Instruct-7B, Llama-3.1-8B). The DeepSeek data-point would be an additional MoE comparison; its absence does not change the headline conclusion that `B0 + Qwen2.5-Coder-7B-Instruct` is the strongest configuration found.
