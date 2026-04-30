# A100 pre-flight (final iteration)

**Captured:** 2026-04-30T14:12:33.199288+00:00

| | |
|---|---|
| Python | 3.12.13 |
| Platform | Linux-6.6.113+-x86_64-with-glibc2.35 |
| GPU | **NVIDIA A100-SXM4-80GB** |
| GPU VRAM total | 85.09 GB |
| GPU VRAM free | 84.65 GB |
| CUDA | 12.8 |
| HF_TOKEN | NOT set (Llama gated reload would fail; existing Llama numbers reused from local mirror) |

## Decision tree
- GPU is A100 80 GB → **Qwen-Coder-14B in 4-bit is fully feasible** (ETA ~10-15 min total for 4 runs).
- DeepSeek environmental blocker is the same regardless of GPU (transformers ABI, not VRAM); transformers 5.0.0 in this kernel makes the trust_remote_code path even worse than 4.45 — clean-notebook unblock path stands.

## Package versions
{
  "torch": "2.10.0+cu128",
  "transformers": "5.0.0",
  "bitsandbytes": "NOT_INSTALLED (ModuleNotFoundError)",
  "accelerate": "1.13.0",
  "jsonschema": "4.26.0",
  "huggingface_hub": "1.11.0",
  "sentencepiece": "0.2.1",
  "safetensors": "0.7.0",
  "func_timeout": "NOT_INSTALLED (ModuleNotFoundError)"
}
