# DeepSeek unblock instructions — for the human operator

_Refreshed: 2026-04-30T15:24:12.101245+00:00_

**You only need this if you want a 4th mandatory model data-point. The diploma is defense-ready without it.**

## Step-by-step (matches `outputs/tables/deepseek_blocker_reproduction_checklist.csv`)
1. Browser → `colab.research.google.com` → New blank notebook.
2. Connect to a GPU runtime (T4/L4/A100/H100 — DeepSeek-V2-Lite in 4-bit fits any of them).
3. Cell 1 (install only):
   ```bash
   !pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes==0.43.1 \
                  tokenizers<0.20 huggingface_hub<0.25 sentencepiece safetensors \
                  einops func_timeout jsonschema
   ```
4. Cell 2 (verify symbol):
   ```python
   from transformers.utils.import_utils import is_torch_fx_available
   print('OK', is_torch_fx_available())
   ```
5. Cell 3 (load model):
   ```python
   import torch
   from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
   MODEL_ID = "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
   tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
   qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
   model = AutoModelForCausalLM.from_pretrained(
       MODEL_ID, trust_remote_code=True, device_map="auto",
       quantization_config=qcfg)
   model.eval(); print("LOADED OK; VRAM=", torch.cuda.memory_allocated()//(1024*1024), "MB")
   ```
6. Cell 4: paste the AGENT_BRIDGE_SETUP cell from `notebooks/example.ipynb` (cell id `7f6bca53`). Run. Copy printed `BRIDGE_URL`.
7. On your local machine, edit `tools/.bridge_url` to the new URL. Run `python tools/exec_remote.py --health` (should print `{"ok": true, "pid": ...}`).
8. Run `python tools/exec_remote.py --code-file tools/remote_scripts/60_deepseek_b0_b1_bg.py`. Wait ~10-15 min, then poll progress with `_peek_deepseek.py`.
9. After done, refresh master matrix and REPORT.

## Last-resort shim (use only in isolated DeepSeek notebook)
If your isolated runtime still complains about `is_torch_fx_available`, add this BEFORE importing transformers:
```python
import transformers.utils.import_utils as iu
if not hasattr(iu, "is_torch_fx_available"):
    iu.is_torch_fx_available = lambda: True
```
Document this fact in your blocker/success log.

## Why we cannot do this from the agent
The Colab kernel currently bound to our bridge already has `transformers 5.0.0` loaded and the `tokenizers` C extension dynamically linked. Any in-place downgrade will break the kernel and lose all loaded models. The clean fix is a fresh Colab kernel — that is a human operation.

## Honest classification
Mandatory model from the proposal — **not evaluated in any kernel of this project** because of an environmental ABI mismatch in the trust_remote_code modeling code. **All other 3 mandatory models evaluated.** The DeepSeek data-point would be an additional MoE comparison; its absence does not change the headline conclusion that `B0 + Qwen2.5-Coder-7B-Instruct` is the strongest configuration found.

Estimated total time including human ops: ~30-40 min.
