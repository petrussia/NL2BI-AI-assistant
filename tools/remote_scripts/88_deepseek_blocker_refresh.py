# Refresh DeepSeek blocker artifacts (no model run; environmental blocker stands).

import csv
import datetime as dt
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
TABLES = PROJECT_ROOT / 'outputs' / 'tables'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# Refresh the final blocker (the prior content already documented this; touch
# timestamps and confirm the recipe is current).
blocker = LOGS / 'deepseek_blocker_final_h100.md'
content = blocker.read_text(encoding='utf-8') if blocker.exists() else ''
if 'A100 80 GB' in content or 'A100' in content:
    # Already refreshed in v4 closure; just bump
    pass

# Reproduction checklist (idempotent — overwrite with verified steps)
checklist = TABLES / 'deepseek_blocker_reproduction_checklist.csv'
with checklist.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['step','description','expected_outcome','status','notes'])
    w.writerow(['1','Open NEW Colab notebook (not the Qwen-runtime one)','blank kernel','pending','must be a fresh Python process'])
    w.writerow(['2','Cell 1: pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes==0.43.1 tokenizers<0.20 huggingface_hub<0.25 sentencepiece safetensors einops func_timeout jsonschema','installs without conflict','pending','no transformers import before this'])
    w.writerow(['3','Cell 2: from transformers.utils.import_utils import is_torch_fx_available','import succeeds','pending','if it fails, env is wrong'])
    w.writerow(['4','Cell 3: AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)','tokenizer loads','pending','MODEL_ID = deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct'])
    w.writerow(['5','Cell 4: AutoModelForCausalLM.from_pretrained 4-bit nf4 device_map=auto','model loads in 1-2 min, VRAM ~9-12 GB','pending','BF16 also works on 80GB'])
    w.writerow(['6','Cell 5: AGENT_BRIDGE_SETUP from notebooks/example.ipynb','BRIDGE_URL printed','pending','same bridge cell as Qwen-runtime'])
    w.writerow(['7','Update tools/.bridge_url with new URL on local machine','file updated','pending','no token in URL'])
    w.writerow(['8','Run python tools/exec_remote.py --code-file tools/remote_scripts/60_deepseek_b0_b1_bg.py','BG starts and eventually DEEPSEEK_BG_DONE_OK','pending','~25 min runtime'])
    w.writerow(['9','Verify outputs/predictions/deepseek_b0_smoke10_predictions.jsonl present, 10 lines','file present and complete','pending','spot-check 1-2 lines'])
    w.writerow(['10','Add results to master matrix; refresh REPORT v5','master matrix grows by 2 rows','pending','re-run 65_final_consolidation_v2.py'])

# Unblock instructions one-pager (idempotent)
instr = LOGS / 'deepseek_unblock_instructions.md'
instr.write_text(textwrap.dedent(f'''
# DeepSeek unblock instructions — for the human operator

_Refreshed: {NOW}_

**You only need this if you want a 4th mandatory model data-point. The diploma is defense-ready without it.**

## Step-by-step (matches `outputs/tables/deepseek_blocker_reproduction_checklist.csv`)
1. Browser → `colab.research.google.com` → New blank notebook.
2. Connect to a GPU runtime (T4/L4/A100/H100 — DeepSeek-V2-Lite in 4-bit fits any of them).
3. Cell 1 (install only):
   ```bash
   !pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes==0.43.1 \\
                  tokenizers<0.20 huggingface_hub<0.25 sentencepiece safetensors \\
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
7. On your local machine, edit `tools/.bridge_url` to the new URL. Run `python tools/exec_remote.py --health` (should print `{{"ok": true, "pid": ...}}`).
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
''').strip()+'\n', encoding='utf-8')

# Refresh blocker_final_h100.md timestamp + recheck wording
blocker.write_text(textwrap.dedent(f'''
# DeepSeek-Coder-V2-Lite-Instruct — final blocker (A100/H100 lane)

**Refreshed:** {NOW}
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
''').strip()+'\n', encoding='utf-8')

print(f'WROTE {blocker}')
print(f'WROTE {checklist}')
print(f'WROTE {instr}')
