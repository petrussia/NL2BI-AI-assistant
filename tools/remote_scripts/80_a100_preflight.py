# A100 pre-flight: runtime snapshot + master state recheck.

import csv
import datetime as dt
import importlib
import json
import os
import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
LOGS = OUTPUTS / 'logs'
TABLES = OUTPUTS / 'tables'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

import torch
gpu_name = torch.cuda.get_device_name(0)
free, total = torch.cuda.mem_get_info(0)
cuda_v = torch.version.cuda

pkg_versions = {}
for pkg in ('torch','transformers','bitsandbytes','accelerate','jsonschema',
            'huggingface_hub','sentencepiece','safetensors','func_timeout'):
    try:
        m = importlib.import_module(pkg)
        pkg_versions[pkg] = getattr(m, '__version__', '?')
    except Exception as exc:
        pkg_versions[pkg] = f'NOT_INSTALLED ({type(exc).__name__})'

# preflight
preflight = LOGS/'runtime_preflight_h100_final.md'
preflight.write_text(f'''# A100 pre-flight (final iteration)

**Captured:** {NOW}

| | |
|---|---|
| Python | {sys.version.split()[0]} |
| Platform | {platform.platform()} |
| GPU | **{gpu_name}** |
| GPU VRAM total | {total/1e9:.2f} GB |
| GPU VRAM free | {free/1e9:.2f} GB |
| CUDA | {cuda_v} |
| HF_TOKEN | {"set" if os.environ.get("HF_TOKEN") else "NOT set (Llama gated reload would fail; existing Llama numbers reused from local mirror)"} |

## Decision tree
- GPU is A100 80 GB → **Qwen-Coder-14B in 4-bit is fully feasible** (ETA ~10-15 min total for 4 runs).
- DeepSeek environmental blocker is the same regardless of GPU (transformers ABI, not VRAM); transformers 5.0.0 in this kernel makes the trust_remote_code path even worse than 4.45 — clean-notebook unblock path stands.

## Package versions
{json.dumps(pkg_versions, indent=2)}
''', encoding='utf-8')

# versions table
with (TABLES/'runtime_versions_h100_final.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['key','value'])
    for k, v in pkg_versions.items(): w.writerow([k, v])
    w.writerow(['gpu', gpu_name]); w.writerow(['vram_total_gb', f'{total/1e9:.2f}'])
    w.writerow(['vram_free_gb', f'{free/1e9:.2f}']); w.writerow(['cuda', cuda_v])
    w.writerow(['python', sys.version.split()[0]])
    w.writerow(['hf_token_set', bool(os.environ.get('HF_TOKEN'))])

# master state
inv = {}
for d in ['outputs/predictions','outputs/metrics','outputs/tables','outputs/plots',
          'outputs/docs','outputs/logs','outputs/thesis_pack_shubin',
          'repo/src/evaluation','repo/docs','exports']:
    p = PROJECT_ROOT/d
    inv[d] = sorted(x.name for x in p.iterdir()) if p.exists() else []

state = LOGS/'master_state_recheck_h100_final.md'
lines = [f'# Master state recheck (A100 final iteration)', f'**Captured:** {NOW}', '']
for k, v in inv.items():
    lines.append(f'## {k} ({len(v)})')
    for x in v[:60]: lines.append(f'- {x}')
    if len(v) > 60: lines.append(f'- … and {len(v)-60} more')
    lines.append('')
state.write_text('\n'.join(lines), encoding='utf-8')

print(f'GPU={gpu_name} VRAM_total={total/1e9:.2f}GB VRAM_free={free/1e9:.2f}GB')
print(f'transformers={pkg_versions.get("transformers")} torch={pkg_versions.get("torch")}')
print(f'predictions={len(inv["outputs/predictions"])} repo_modules={len(inv["repo/src/evaluation"])} thesis_pack={len(inv["outputs/thesis_pack_shubin"])}')
print(f'WROTE {preflight}')
print(f'WROTE {state}')
