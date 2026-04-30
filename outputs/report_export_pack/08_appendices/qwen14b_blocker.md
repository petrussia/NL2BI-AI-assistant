# Qwen2.5-Coder-14B-Instruct — runtime blocker on L4 24 GB

**Issued:** 2026-04-30T12:21:04.292787+00:00
**Model:** `Qwen/Qwen2.5-Coder-14B-Instruct`
**Runtime:** NVIDIA L4 (22.03 GiB visible to PyTorch, 23.66 GB nameplate)
**Quant config:** 4-bit nf4 bitsandbytes, double-quant, fp16 compute

## Outcome
- load_status = `failed`
- load_error_class = `OutOfMemoryError`
- load_error_message = `CUDA out of memory. Tried to allocate 136.00 MiB.
  GPU 0 has a total capacity of 22.03 GiB of which 45.12 MiB is free.
  Including non-PyTorch memory, this process has 21.98 GiB memory in use.`
- Elapsed: ~9 min (download succeeded; OOM hit during weight allocation /
  quantization staging).

## Why this is a hardware blocker, not a code blocker
The 4-bit footprint of a 14B-param model is ≈ 7–8 GB at steady state, but
the bitsandbytes nf4 loader needs additional staging memory during weight
quantization. On L4 24 GB, after fragmentation and CUDA reservation overhead,
the available contiguous block is < 22 GB and the staging spike pushes total
allocation past the limit.

## What it would take to unblock
- A100 40 GB (single GPU), OR
- H100 80 GB (single GPU, recommended), OR
- L4 24 GB with `device_map="sequential"` + `max_memory={0: "20GiB"}` + CPU offload
  (but inference becomes 5-10x slower; not productive for this evaluation),
- OR run in fp8 or int8 on L4 (but the bnb int8 path is also memory-heavier
  during quant staging).

The cleanest path is a different GPU. The user's earlier reference to "H100"
in the prompt would have unblocked this; the actual provisioned GPU was L4.

## Honest classification
Optional comparator model from the project's "approved candidates" list —
**not evaluated this iteration**. The Llama-3.1-8B run (B0=0.80, B1=0.90)
already supplies the larger-than-7B comparison data point.
