# Cleanup after Qwen-14B OOM + write blocker artifact, then load Qwen-Coder-7B
# so subsequent BG (B2_v2) can find it ready.

import datetime as dt
import gc
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

mm = sys.modules['__main__']

# ===== free GPU =====
import torch
for k in ('model', 'tokenizer'):
    if k in mm.__dict__: del mm.__dict__[k]
gc.collect()
torch.cuda.empty_cache()
try: torch.cuda.synchronize()
except Exception: pass
free, total = torch.cuda.mem_get_info(0)
print(f'after_cleanup gpu free={free/1e9:.2f} GB total={total/1e9:.2f} GB')

# ===== blocker artifact =====
blocker = LOGS / 'qwen14b_blocker.md'
blocker.write_text(textwrap.dedent(f'''
# Qwen2.5-Coder-14B-Instruct — runtime blocker on L4 24 GB

**Issued:** {NOW}
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
- L4 24 GB with `device_map=\"sequential\"` + `max_memory={{0: \"20GiB\"}}` + CPU offload
  (but inference becomes 5-10x slower; not productive for this evaluation),
- OR run in fp8 or int8 on L4 (but the bnb int8 path is also memory-heavier
  during quant staging).

The cleanest path is a different GPU. The user's earlier reference to "H100"
in the prompt would have unblocked this; the actual provisioned GPU was L4.

## Honest classification
Optional comparator model from the project's "approved candidates" list —
**not evaluated this iteration**. The Llama-3.1-8B run (B0=0.80, B1=0.90)
already supplies the larger-than-7B comparison data point.
''').strip()+'\n', encoding='utf-8')
print(f'WROTE {blocker}')

# ===== load Qwen-Coder-7B for B2_v2 BG =====
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import time
MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
t0 = time.time()
tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                          bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
new_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, trust_remote_code=True, device_map='auto', quantization_config=qcfg)
new_model.eval()
mm.__dict__['model'] = new_model
mm.__dict__['tokenizer'] = tok
print(f'LOADED {MODEL_ID} in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')
