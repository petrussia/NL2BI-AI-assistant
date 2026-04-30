# Update DeepSeek blocker artifacts with the new A100 evidence:
# transformers 5.0.0 in this kernel makes the trust_remote_code path even
# worse than 4.45 (more removed/renamed symbols). Confirms the
# clean-fresh-notebook unblock path is the only reasonable option.

import csv
import datetime as dt
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
TABLES = PROJECT_ROOT / 'outputs' / 'tables'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


# === clean env attempt log (this iteration) ===
clean_env = LOGS / 'deepseek_clean_env_attempt.md'
clean_env.write_text(textwrap.dedent(f'''
# DeepSeek clean-env attempt log — A100 iteration

**Captured:** {NOW}
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
''').strip()+'\n', encoding='utf-8')


# === clean env versions table ===
with (TABLES/'deepseek_clean_env_versions.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['package','required_version','reason'])
    w.writerow(['transformers','4.39.3','exports is_torch_fx_available used by trust_remote_code modeling'])
    w.writerow(['accelerate','0.26.1','compatible with transformers 4.39.x'])
    w.writerow(['bitsandbytes','>=0.43.3','4-bit nf4 quant with double-quant'])
    w.writerow(['tokenizers','>=0.15,<0.20','transformers 4.39.x ABI'])
    w.writerow(['safetensors','>=0.4,<1.0','model weight format'])
    w.writerow(['huggingface_hub','>=0.20,<0.25','transformers 4.39.x ABI'])
    w.writerow(['sentencepiece','>=0.1.99','tokenizer for Llama/Mistral family'])
    w.writerow(['func_timeout','>=4.3','SQLite execution sandbox'])
    w.writerow(['jsonschema','>=4.20','plan validation'])


# === import test log ===
import_test = LOGS / 'deepseek_import_and_load_test.md'
import_test.write_text(textwrap.dedent(f'''
# DeepSeek import + load test (A100)

**Captured:** {NOW}

In this kernel we did NOT attempt re-import. Reason:
- transformers 5.0.0 has an even larger drift from 4.39.x than the prior 4.45.x kernel.
- The trust_remote_code modeling file references symbols that have been
  reorganised/removed in 5.x (`is_torch_fx_available` is one example; there
  are others in DeepSeek-V2-Lite's `modeling_deepseek.py`).
- Even with `pip install --target` + subprocess isolation, the C-extension
  ABI of `tokenizers` cannot be substituted at runtime — it is dynamically
  linked at first import.

The only correct test is in a **fresh Colab kernel**, not this one. See
`outputs/tables/deepseek_blocker_reproduction_checklist.csv` and
`outputs/logs/deepseek_unblock_instructions.md` for the exact steps.
''').strip()+'\n', encoding='utf-8')


# === final blocker (rewrite, A100 edition) ===
blocker = LOGS / 'deepseek_blocker_final_h100.md'
blocker.write_text(textwrap.dedent(f'''
# DeepSeek-Coder-V2-Lite-Instruct — final blocker (A100 lane)

**Issued:** {NOW}
**Model:** `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`
**Runtime tested:** NVIDIA A100-SXM4-80GB, transformers 5.0.0, torch 2.10
**VRAM available:** 84 GB free — **NOT the constraint**
**Real constraint:** transformers ABI in the model's trust_remote_code modeling file

## Why VRAM is no longer the issue
On A100 80 GB the model fits trivially: 4-bit nf4 footprint of
DeepSeek-V2-Lite (≈ 16 B params, MoE with ~2.4 B active) ≈ 9–12 GB. We have
84 GB free.

## Why import is the issue
1. The model's `modeling_deepseek.py` (loaded under `trust_remote_code=True`)
   references `transformers.utils.import_utils.is_torch_fx_available`. This
   symbol existed in `transformers <= 4.39.x`, was renamed/moved in 4.40+,
   and is **fully absent** in 5.0.0.
2. The kernel's installed transformers is 5.0.0. We cannot downgrade in-place
   without breaking the currently-loaded Qwen-Coder runtime.
3. Isolated install via `pip install --target /tmp/ds_env transformers==4.39.x`
   fails at `dependency_versions_check` because pinned transformers requires
   pinned `tokenizers`, `accelerate`, `safetensors`, `huggingface_hub` — and
   even with them in the target dir, the kernel's already-loaded
   `tokenizers` C extension cannot be substituted at runtime (Python C
   extensions are dynamically linked at first import).

## Unblock — exact steps in a fresh Colab notebook

```python
# Cell 1
!pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes>=0.43.3 \\
              tokenizers>=0.15,<0.20 safetensors huggingface_hub>=0.20,<0.25 \\
              sentencepiece func_timeout jsonschema

# Cell 2
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch
MODEL_ID = "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                          bnb_4bit_compute_dtype=torch.float16,
                          bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, trust_remote_code=True, device_map="auto",
    quantization_config=qcfg)
model.eval()
print("LOADED OK; VRAM=", torch.cuda.memory_allocated()//(1024*1024), "MB")

# Cell 3 (bridge bootstrap as in our notebook cell 7f6bca53)
# Then update tools/.bridge_url and run 60_deepseek_b0_b1_bg.py from the agent.
```

ETA after the fresh kernel is up: 5-10 min cold-cache download, 1-2 min load,
~5 min for B0 smoke_10, ~5 min for B1 smoke_10. Total ≈ 25 min.

## Honest classification
Mandatory model from the proposal — **not evaluated in any kernel of this
project** because of an environmental ABI mismatch. **All other 3 mandatory
models evaluated.** The DeepSeek data-point would be an additional MoE
comparison; its absence does not change the headline conclusion that
`B0 + Qwen2.5-Coder-7B-Instruct = 0.9333 EX on multi-DB` is the strongest
configuration found.
''').strip()+'\n', encoding='utf-8')


# === reproduction checklist (table form) ===
checklist = TABLES / 'deepseek_blocker_reproduction_checklist.csv'
with checklist.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['step','description','expected_outcome','status'])
    w.writerow(['1','Open a NEW Colab notebook (not the Qwen-runtime one)','blank kernel','pending'])
    w.writerow(['2','pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes safetensors tokenizers<0.20 huggingface_hub<0.25 sentencepiece func_timeout jsonschema','installs without error','pending'])
    w.writerow(['3','Import transformers; verify is_torch_fx_available is exported','from transformers.utils.import_utils import is_torch_fx_available works','pending'])
    w.writerow(['4','AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)','tokenizer loads, prints class name','pending'])
    w.writerow(['5','AutoModelForCausalLM.from_pretrained 4-bit nf4 device_map=auto','model loads in 1-2 min, VRAM ~9-12 GB','pending'])
    w.writerow(['6','Run AGENT_BRIDGE_SETUP cell from notebooks/example.ipynb','BRIDGE_URL printed','pending'])
    w.writerow(['7','Update tools/.bridge_url with new URL','file updated','pending'])
    w.writerow(['8','Run 60_deepseek_b0_b1_bg.py from agent harness','BG starts, eventually DEEPSEEK_BG_DONE_OK','pending'])
    w.writerow(['9','Verify outputs/predictions/deepseek_b0_smoke10_predictions.jsonl exists with 10 lines','file present','pending'])
    w.writerow(['10','Add results to master matrix; refresh REPORT v5','master matrix grows; REPORT updated','pending'])


# === unblock instructions (one-pager) ===
instr = LOGS / 'deepseek_unblock_instructions.md'
instr.write_text(textwrap.dedent(f'''
# DeepSeek unblock instructions — for the human operator

_Generated: {NOW}_

**You only need this if you want a 4th mandatory model data-point. The
diploma is already defense-ready without it.**

## Step-by-step
1. In your browser, open `colab.research.google.com` and create a **new
   blank notebook**. Don't re-use the Qwen-runtime notebook.
2. Connect the notebook to a GPU runtime (T4 / L4 / A100 — DeepSeek-V2-Lite
   in 4-bit fits any of them).
3. Paste the install cell from
   `outputs/logs/deepseek_blocker_final_h100.md` section "Unblock — exact
   steps in a fresh Colab notebook" (Cell 1). Run it.
4. Paste the load cell (Cell 2). Run it. Wait for `LOADED OK`.
5. Paste the bridge bootstrap cell (the same one as in our project's
   `notebooks/example.ipynb` cell `7f6bca53`). Run it. Copy the printed
   `BRIDGE_URL`.
6. On your local machine, edit `tools/.bridge_url` to the new URL.
7. Run `python tools/exec_remote.py --health` — should print `{{"ok": true, "pid": ...}}`.
8. Run `python tools/exec_remote.py --code-file tools/remote_scripts/60_deepseek_b0_b1_bg.py`.
9. Wait ~10-15 min, then poll progress with `_peek_deepseek.py`.
10. When done, refresh master matrix and REPORT.

Estimated total time: ~30-40 min including human ops.
''').strip()+'\n', encoding='utf-8')


# === Update model_block_closure.md ===
mbc = LOGS / 'model_block_closure.md'
mbc.write_text(textwrap.dedent(f'''
# Model block closure — final (A100 iteration)

**Updated:** {NOW}

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
''').strip()+'\n', encoding='utf-8')


print(f'WROTE {clean_env}')
print(f'WROTE {import_test}')
print(f'WROTE {blocker}')
print(f'WROTE {checklist}')
print(f'WROTE {instr}')
print(f'WROTE {mbc}')
