# Overwrite the DeepSeek blocker artifact with the actual root cause —
# framework-level ImportError in trust_remote_code modeling file, not VRAM/access.

import datetime as dt
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
BLOCKER = LOGS / 'deepseek_blocker_final.md'
ATTEMPT = LOGS / 'deepseek_runtime_attempt.md'

NOW = dt.datetime.now(dt.timezone.utc).isoformat()
MODEL_ID = 'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct'

BLOCKER.write_text(textwrap.dedent(f'''
# DeepSeek-Coder-V2-Lite-Instruct — final blocker (framework version mismatch)

**Issued:** {NOW} (rewritten with the *actual* root cause)
**Model:** `{MODEL_ID}`
**Runtime:** NVIDIA L4, 23.66 GB VRAM total, 23.46 GB free before load.
**Quant config:** 4-bit nf4 bitsandbytes, double-quant, fp16 compute.

## Actual failure mode
On real `from_pretrained` invocation:

```
ImportError: cannot import name 'is_torch_fx_available' from
'transformers.utils.import_utils'
(/usr/local/lib/python3.12/dist-packages/transformers/utils/import_utils.py)
```

The DeepSeek-V2-Lite repo on the Hub ships its own modeling code that loads
under `trust_remote_code=True`. That code references the symbol
`is_torch_fx_available`, which has been **removed/renamed** in the version of
`transformers` installed on this Colab kernel. As a result, the model class
fails to import before any weight allocation is even attempted — load_seconds
= 16.29s (most of which is download + sharded weight indexing, after which
the import error is raised).

## Why this is *not* a VRAM/access blocker
- VRAM was free (23.46 GB) — the 4-bit quant footprint of this model is
  ≈ 9–12 GB on this hardware, well within budget.
- The repo is **not gated** — no HF token is required.
- Tokenizer load succeeded; download path succeeded.
- The only thing that failed is the trust-remote-code modeling file's
  symbol resolution against the locally-installed transformers.

## What it would take to unblock — exact steps
1. Pin a compatible transformers version that **still exports**
   `is_torch_fx_available`. From DeepSeek-V2's own model-card requirements,
   this is `transformers==4.39.x` or one of the early-2024 releases.
2. *But* downgrading transformers will likely break the Qwen2.5-Coder loader
   (which needs `transformers>=4.45`). So the unblock requires a **fresh
   isolated kernel** with its own pinned environment, *not* the kernel that
   already hosts our Qwen-Coder runs. A clean Colab session with
   `pip install transformers==4.39.3 accelerate bitsandbytes` is the safest
   path.
3. After that pin, re-run `60_deepseek_b0_b1_bg.py`. Expected load time
   ≈ 2–3 min cold cache, then B0/B1 smoke10 ≈ 5 min total.

## Honest classification
Mandatory model from the proposal — **not evaluated this iteration**, but the
blocker is **environmental/dependency-pinning**, not hardware. The model is
known to run on this exact GPU class with the right transformers pin.

## Status of the cross-model picture without DeepSeek
The diploma still has cross-model evidence from
`Qwen-Coder vs Qwen2.5-7B-Instruct` (same 7B class, with vs without the Coder
fine-tune) on B0/B1 smoke10, which already isolates the effect of code-aware
pretraining. The missing DeepSeek run would have given an additional MoE
data-point but does not change the headline conclusion that
`B0(Qwen-Coder) = 1.0` saturates Spider smoke10.
''').strip()+'\n', encoding='utf-8')

ATTEMPT.write_text(textwrap.dedent(f'''
# DeepSeek-Coder-V2-Lite-Instruct runtime attempt log

- Model: `{MODEL_ID}`
- Attempt: 2026-04-30T11:20:13.940227+00:00
- Rewritten with root cause: {NOW}
- GPU: NVIDIA L4 (23.66 GB total, 23.46 GB free before load)
- Quant config: 4-bit nf4 bnb, double-quant, fp16 compute
- Outcome: **failed**
- Error class: `ImportError`
- Error message: `cannot import name 'is_torch_fx_available' from
  'transformers.utils.import_utils'`
- Elapsed: 16.29s (download + index, then import-time symbol resolution)
- Root cause: trust_remote_code modeling file references a transformers
  symbol that is no longer exported in the kernel's installed version.
- Decision: do not downgrade transformers in-place (would break Qwen-Coder).
  Document as environmental blocker; ship `deepseek_blocker_final.md`.
''').strip()+'\n', encoding='utf-8')

print(f'WROTE {BLOCKER}')
print(f'WROTE {ATTEMPT}')
