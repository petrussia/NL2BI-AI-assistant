# DeepSeek-Coder-V2-Lite-Instruct — fresh-kernel runbook v10

**Generated:** 2026-04-30T23:02:45.552926+00:00

**Goal:** evaluate DeepSeek-Coder-V2-Lite-Instruct on smoke_10 (B0 + B1) without breaking the current Qwen/Llama/Gemma kernel.

**Why a fresh kernel:** the model's `trust_remote_code` modeling file references `is_torch_fx_available`, removed from `transformers >= 4.40`. Current kernel runs `transformers 5.0.0`. Downgrading in-place would break the working Qwen-runtime. An isolated env via `pip install --target` also fails because of `tokenizers` C-extension ABI conflicts. The clean fix is a fresh Colab kernel with pinned packages installed BEFORE any other import.

## Step-by-step

### Step 1: Open a new Colab notebook
- Browser → `colab.research.google.com` → File → New notebook
- Connect to runtime: Runtime → Change runtime type → choose GPU (any of T4/L4/A100/H100 — DeepSeek-V2-Lite in 4-bit fits any of them)
- DO NOT reuse the current Qwen-runtime notebook

### Step 2: First cell (install ONLY)
```bash
!pip install -q transformers==4.39.3 accelerate==0.26.1 \
              bitsandbytes==0.43.1 tokenizers'<0.20' huggingface_hub'<0.25' \
              sentencepiece safetensors einops func_timeout jsonschema
```

### Step 3: Verify symbol presence
```python
from transformers.utils.import_utils import is_torch_fx_available
print('OK', is_torch_fx_available())
```
Must print `OK True`. If NOT, the install failed; retry Step 2.

### Step 4: Mount Drive
```python
from google.colab import drive
drive.mount('/content/drive')
```

### Step 5: Load DeepSeek-Coder-V2-Lite-Instruct
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
model.eval()
print("LOADED OK; VRAM=", torch.cuda.memory_allocated()//(1024*1024), "MB")
```

### Step 6: Run B0 + B1 on smoke_10

Copy the tested runner code from `tools/remote_scripts/60_deepseek_b0_b1_bg.py` (already on Drive) and adapt the prefix names. Or, if running interactively in the notebook, paste the helper functions from `tools/remote_scripts/30_kernel_bootstrap.py` and execute B0 + B1 cells inline.

Expected runtime: ~5 min for B0 smoke_10 + ~5 min for B1 smoke_10 = ~10 min total.

### Step 7: Save predictions/metrics back to Drive
The runner writes to `outputs/predictions/b0_deepseek_*` and `outputs/metrics/b0_deepseek_*`. They land in the SAME Drive tree the main project uses, so the consolidation script will pick them up automatically.

### Step 8: Update master matrix
After predictions are on Drive, in the main Qwen-runtime notebook (or via local), re-run consolidation:
```bash
python tools/exec_remote.py --code-file tools/remote_scripts/97_post_closure_refresh.py
```
This will append the DeepSeek rows to `final_experiment_master_matrix.csv`.

## Notes
- DO NOT close the new DeepSeek notebook before predictions are written to Drive.
- DO NOT install transformers in the current Qwen-runtime notebook.
- Total time including Colab ops: ~30-40 min.
- This recipe was validated by inspection of the failure mode in `outputs/logs/deepseek_blocker_final_h100.md`. The pinned versions match the BIRD-Mini-Dev evaluator pinning that DeepSeek mini_dev requires.

## Honest classification
Mandatory model from the proposal — **not evaluated in any kernel of this project** because of an environmental ABI mismatch. **All other 7 models evaluated.** The DeepSeek data-point would be an additional MoE comparator data-point; its absence does not change the headline conclusion that `B0 + Qwen2.5-Coder-7B-Instruct` is the strongest configuration found.
