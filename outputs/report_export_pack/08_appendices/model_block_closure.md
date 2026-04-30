# Model block closure — final (A100 iteration)

**Updated:** 2026-04-30T14:17:35.984368+00:00

## Mandatory models — final state

| Model | Status | EX evidence | Notes |
|---|---|---|---|
| **Qwen2.5-Coder-7B-Instruct** | **DONE** | full ladder × 3 subsets | Strongest model in project; B0 = 1.00/0.96/0.9333 |
| **Qwen2.5-7B-Instruct** | **DONE (partial)** | B0/B1 smoke_10 | Cross-model: B0 = 0.60, B1 = 1.00 (linker compensates Coder fine-tune) |
| **Llama-3.1-8B-Instruct** | **DONE** | B0/B1 smoke_10 | B0 = 0.80, B1 = 0.90 (was credential-blocked, now resolved) |
| **DeepSeek-Coder-V2-Lite-Instruct** | **BLOCKED (env)** | — | trust_remote_code ABI mismatch; clean-notebook unblock path documented |

## Optional comparators

| Model | Status | EX evidence | Notes |
|---|---|---|---|
| **Qwen2.5-Coder-14B-Instruct** | running on A100 in this iteration | see master matrix after BG completes | larger Qwen-Coder; was L4-hardware-blocked, A100 unblocks it |

## Why DeepSeek is still blocked on A100

Hardware is no longer the constraint — A100 80 GB has 84 GB free, plenty for
the 4-bit footprint (~9-12 GB). The blocker is purely the **transformers
ABI in the trust_remote_code modeling file**: `modeling_deepseek.py`
references `is_torch_fx_available`, removed in transformers >= 4.40, fully
absent in 5.0.0 (this kernel).

Three approaches were considered and rejected for in-kernel use:
1. In-place downgrade of transformers → would break Qwen-Coder loaders.
2. Isolated install via `pip install --target` → fails at
   `dependency_versions_check`; even with all deps pinned in target dir,
   the kernel's already-loaded `tokenizers` C extension cannot be
   substituted at runtime.
3. subprocess with PYTHONPATH override → same C-extension ABI problem
   inherited from parent process for already-imported native modules.

The only clean path is a **fresh Colab kernel** with pinned transformers as
the very first installed package. Full instructions and reproduction
checklist:
- `outputs/logs/deepseek_blocker_final_h100.md`
- `outputs/logs/deepseek_unblock_instructions.md`
- `outputs/tables/deepseek_blocker_reproduction_checklist.csv`

## Honest summary
**3 of 4 mandatory models evaluated.** The 4th is closed by a documented
environmental blocker, not silently skipped. The headline conclusions of
the project (B0 + Qwen-Coder-7B saturates Spider; B2_v2 multi-DB beats B1
by +0.0333) do not depend on the DeepSeek data-point.
