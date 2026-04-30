# DeepSeek-Coder-V2-Lite-Instruct — H100 lane blocker (final)

**Issued:** 2026-04-30T12:24:48.016507+00:00
**Approach:** isolated env via `pip install --target /tmp/ds_env transformers==4.39.3` + subprocess import probe (does not touch the main Qwen-runtime).

## Outcome
The probe failed even with `transformers==4.39.x` pinned in the isolated env.
See `outputs/logs/deepseek_import_test_h100.md` for the exact stdout/stderr.

## Why
DeepSeek-V2-Lite ships its own modeling code under `trust_remote_code=True`.
That code has dependencies that are non-trivial to satisfy *in isolation*:
- it imports `transformers.utils.import_utils.is_torch_fx_available`
  (present in 4.39.x);
- it expects a matching `tokenizers` C extension (we pinned `tokenizers<0.20`);
- some symbols in the modeling file may also reference internal
  transformers attributes that drift between minor versions.

The cleanest path is **not** in-kernel pip surgery; it is a **fresh Colab
runtime** with a clean `pip install transformers==4.39.3 accelerate==0.26.1
bitsandbytes torch` and nothing else competing for the import system. From
inside our Qwen-runtime kernel the cost-benefit (risk of breaking the
Qwen/Llama loader vs. one extra DeepSeek data-point) is unfavourable.

## What it would take to unblock — exact, minimal steps
1. Open a **new Colab notebook** (do not reuse this one).
2. First cell: `!pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes sentencepiece safetensors func_timeout jsonschema`.
3. Second cell: `from huggingface_hub import login; login()` and paste HF token (DeepSeek-V2-Lite is not gated, but huggingface_hub plays nicer with a token).
4. Third cell: load model:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch
MODEL_ID = "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                          bnb_4bit_compute_dtype=torch.float16,
                          bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True,
                                             device_map="auto", quantization_config=qcfg)
```
5. Fourth cell: bridge bootstrap (`AGENT_BRIDGE_SETUP`), set `tools/.bridge_url`,
   and re-run `60_deepseek_b0_b1_bg.py` from the agent harness.

## Status
Mandatory model from the proposal — **not evaluated in this iteration**.
Documented as an **environmental blocker** (transformers ABI mismatch in
trust_remote_code modeling code), not as a missed step.
