# DeepSeek clean-env attempt log — A100 iteration

**Captured:** 2026-04-30T14:17:35.984368+00:00
**Runtime:** NVIDIA A100-SXM4-80GB, transformers 5.0.0, torch 2.10.0+cu128

## What we tried in this iteration
1. **Did NOT re-attempt in-kernel pip surgery.** The previous iteration's
   `pip install --target /tmp/ds_env transformers==4.39.3` approach failed at
   `dependency_versions_check` because pinned transformers requires matching
   pinned versions of `tokenizers`, `accelerate`, `safetensors`,
   `huggingface_hub`. Even with all of them in the target dir, the kernel's
   own `tokenizers` C extension (already loaded) wins over the target dir,
   producing ABI mismatches.
2. **Did NOT in-kernel downgrade of transformers.** That would break the
   currently-loaded Qwen-Coder runtime and force a reload of all cached
   models — an unfavourable cost-benefit for one extra DeepSeek data-point.
3. **Decision:** the only clean path remaining is a **fresh Colab notebook**
   that starts with `pip install transformers==4.39.3 accelerate==0.26.1
   bitsandbytes safetensors func_timeout jsonschema` *before* importing
   anything else. We document this with a step-by-step checklist.

## Why this is final on this kernel
On A100 80 GB the **VRAM is no longer the constraint** — DeepSeek-V2-Lite
in 4-bit fits with ~70+ GB to spare. The blocker is purely the transformers
ABI in the trust_remote_code modeling code, not hardware.
