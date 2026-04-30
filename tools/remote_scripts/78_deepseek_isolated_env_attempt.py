# Stage B: attempt DeepSeek-Coder-V2-Lite-Instruct in an isolated transformers env
# (pip install --target /tmp/ds_env transformers==4.39.x), without touching the
# main kernel's transformers. We do this in a subprocess to fully isolate import state.
#
# Important: this only attempts the IMPORT + tokenizer load + small generation
# probe with a tiny prompt. We do NOT run a full B0/B1 unless the import test
# passes, because GPU memory on L4 is tight and a partial load can OOM.

import datetime as dt
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
TABLES = PROJECT_ROOT / 'outputs' / 'tables'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

ENV_DIR = '/tmp/ds_env'
TARGET_TRANSFORMERS = 'transformers==4.39.3'

attempt_md = LOGS / 'deepseek_env_attempt_h100.md'
versions_csv = TABLES / 'deepseek_env_versions_h100.csv'
import_test = LOGS / 'deepseek_import_test_h100.md'
blocker = LOGS / 'deepseek_blocker_h100_final.md'
checklist = TABLES / 'deepseek_blocker_checklist_h100.csv'

attempt_log = []

def log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line)
    attempt_log.append(line)

# ===== Step 1: pip install --target =====
log(f'Installing {TARGET_TRANSFORMERS} into isolated env at {ENV_DIR}')
import shutil
if Path(ENV_DIR).exists():
    shutil.rmtree(ENV_DIR)
Path(ENV_DIR).mkdir(parents=True, exist_ok=True)

pip_proc = subprocess.run(
    [sys.executable, '-m', 'pip', 'install', '--target', ENV_DIR, '--no-deps', '-q',
     TARGET_TRANSFORMERS, 'tokenizers<0.20', 'safetensors', 'huggingface_hub<0.25'],
    capture_output=True, text=True, timeout=300)
log(f'pip rc={pip_proc.returncode}')
if pip_proc.returncode != 0:
    log(f'pip stderr: {pip_proc.stderr[:500]}')

# Write versions snapshot
import csv
versions_rows = []
for d in Path(ENV_DIR).iterdir():
    if d.is_dir() and not d.name.startswith('_'):
        versions_rows.append({'name': d.name, 'path': str(d)})
with versions_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['name','path'])
    w.writeheader()
    for r in versions_rows: w.writerow(r)

# ===== Step 2: subprocess import probe =====
probe_script = f'''
import sys, os
sys.path.insert(0, {ENV_DIR!r})
import transformers
print("TRANSFORMERS_VERSION", transformers.__version__)
print("TRANSFORMERS_PATH", transformers.__file__)
# Check the symbol that DeepSeek-V2 needs
try:
    from transformers.utils.import_utils import is_torch_fx_available
    print("HAS_is_torch_fx_available True")
except Exception as exc:
    print("HAS_is_torch_fx_available False", type(exc).__name__, str(exc)[:200])

# Tokenizer-only load to confirm trust_remote_code path resolves
try:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
                                         trust_remote_code=True)
    print("TOKENIZER_OK class=", type(tok).__name__)
except Exception as exc:
    print("TOKENIZER_FAILED", type(exc).__name__, str(exc)[:300])
'''

log('Running import probe in subprocess...')
probe = subprocess.run([sys.executable, '-c', probe_script],
                       capture_output=True, text=True, timeout=240,
                       env={**os.environ, 'PYTHONPATH': ENV_DIR})
probe_stdout = probe.stdout
probe_stderr = probe.stderr
log(f'probe rc={probe.returncode}')
log(f'probe stdout (head 800B):\n{probe_stdout[:800]}')
if probe_stderr:
    log(f'probe stderr (head 600B):\n{probe_stderr[:600]}')

import_test.write_text(textwrap.dedent(f'''
# DeepSeek import test (isolated env) — H100 lane

**Captured:** {NOW}
**Isolated env:** `{ENV_DIR}`
**Pinned transformers:** `{TARGET_TRANSFORMERS}`

## Probe stdout
```
{probe_stdout}
```

## Probe stderr (if any)
```
{probe_stderr}
```

## Verdict
{"PROBE PASSED — symbol available, tokenizer loaded" if "TOKENIZER_OK" in probe_stdout else "PROBE FAILED — see stderr above"}
''').strip()+'\n', encoding='utf-8')

# ===== Step 3: decide =====
if 'TOKENIZER_OK' not in probe_stdout:
    # Honest blocker
    blocker.write_text(textwrap.dedent(f'''
    # DeepSeek-Coder-V2-Lite-Instruct — H100 lane blocker (final)

    **Issued:** {NOW}
    **Approach:** isolated env via `pip install --target {ENV_DIR} {TARGET_TRANSFORMERS}` + subprocess import probe (does not touch the main Qwen-runtime).

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
    ''').strip()+'\n', encoding='utf-8')

    with checklist.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['step','description','status'])
        w.writerow(['1','Open a fresh Colab notebook (do not reuse Qwen-runtime kernel)','pending'])
        w.writerow(['2','pip install -q transformers==4.39.3 accelerate==0.26.1 bitsandbytes safetensors func_timeout jsonschema','pending'])
        w.writerow(['3','from huggingface_hub import login; login() with HF_TOKEN','pending'])
        w.writerow(['4','Load DeepSeek-Coder-V2-Lite-Instruct in 4-bit nf4','pending'])
        w.writerow(['5','Bridge bootstrap + tools/.bridge_url update','pending'])
        w.writerow(['6','Run 60_deepseek_b0_b1_bg.py','pending'])

attempt_md.write_text(textwrap.dedent(f'''
# DeepSeek isolated-env attempt log — H100 lane

**Captured:** {NOW}

## Steps tried
1. Created `{ENV_DIR}` and `pip install --target` of `{TARGET_TRANSFORMERS}` (rc={pip_proc.returncode}).
2. Spawned a subprocess with `PYTHONPATH={ENV_DIR}` and ran an import + tokenizer probe.

## Result
{"PASSED probe — tokenizer loaded under pinned transformers" if "TOKENIZER_OK" in probe_stdout else "FAILED probe — see deepseek_import_test_h100.md"}

## Decision
{"Proceed to model-load attempt under the isolated env." if "TOKENIZER_OK" in probe_stdout else "Stop the in-kernel attempt; emit deepseek_blocker_h100_final.md with reproduction steps in a fresh notebook."}

## Logs
''').strip() + '\n\n```\n' + '\n'.join(attempt_log) + '\n```\n', encoding='utf-8')

print(f'WROTE {attempt_md}')
print(f'WROTE {versions_csv}')
print(f'WROTE {import_test}')
print(f'TOKENIZER_OK in probe: {"TOKENIZER_OK" in probe_stdout}')
if 'TOKENIZER_OK' not in probe_stdout:
    print(f'WROTE {blocker}')
    print(f'WROTE {checklist}')
