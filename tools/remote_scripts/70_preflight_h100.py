# Stage A pre-flight: bridge sanity + H100 confirm + runtime snapshot + master state.

import csv
import datetime as dt
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
LOGS = OUTPUTS / 'logs'
TABLES = OUTPUTS / 'tables'
LOGS.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# === A1 bridge sanity (already verified by exec_remote, just record it) ===
preflight = LOGS / 'runtime_preflight_h100.md'
preflight.write_text('', encoding='utf-8')

# === A2 runtime snapshot ===
import torch
gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'
free, total = torch.cuda.mem_get_info(0) if torch.cuda.is_available() else (0, 0)
cuda_v = torch.version.cuda

pkg_versions = {}
for pkg in ('torch', 'transformers', 'bitsandbytes', 'accelerate',
            'jsonschema', 'huggingface_hub', 'sentencepiece', 'safetensors',
            'func_timeout'):
    try:
        m = importlib.import_module(pkg)
        pkg_versions[pkg] = getattr(m, '__version__', '?')
    except Exception as exc:
        pkg_versions[pkg] = f'NOT_INSTALLED ({type(exc).__name__})'

snapshot = LOGS / 'runtime_snapshot_h100.md'
snapshot.write_text(f'''# Runtime snapshot — H100 lane (or current)

**Captured:** {NOW}

| | |
|---|---|
| Python | {sys.version.split()[0]} |
| Platform | {platform.platform()} |
| GPU | {gpu_name} |
| GPU VRAM total | {total/1e9:.2f} GB |
| GPU VRAM free | {free/1e9:.2f} GB |
| CUDA | {cuda_v} |

## Package versions
{json.dumps(pkg_versions, indent=2)}
''', encoding='utf-8')

with (TABLES / 'runtime_packages_h100.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['package', 'version'])
    for k, v in pkg_versions.items():
        w.writerow([k, v])
    w.writerow(['gpu', gpu_name])
    w.writerow(['gpu_vram_total_gb', f'{total/1e9:.2f}'])
    w.writerow(['gpu_vram_free_gb', f'{free/1e9:.2f}'])
    w.writerow(['cuda', cuda_v])
    w.writerow(['python', sys.version.split()[0]])

# Bridge preflight log finalize
preflight.write_text(f'''# Runtime preflight — H100 lane

**Captured:** {NOW}

- Bridge: live (exec_remote.py end-to-end verified by caller)
- GPU detected: **{gpu_name}** ({total/1e9:.2f} GB total)
- Drive mounted: {os.path.exists('/content/drive/MyDrive/diploma_plan_sql')}
- Project root size (top-level dirs):
{json.dumps({d.name: 'present' if d.exists() else 'missing' for d in [PROJECT_ROOT/x for x in ('data','outputs','repo','exports')]}, indent=2)}

## Decision
- If GPU is H100 80GB → proceed with heavy runs (Qwen2.5-Coder-14B, optional DeepSeek attempt with isolated env).
- If GPU is L4 24GB → still proceed with B2_v2/Qwen-14B 4-bit (~8GB), skip DeepSeek-via-isolated-env.
- HF_TOKEN: present in env (do not log).
''', encoding='utf-8')

# === A3 master state recheck ===
inventory = {
    'predictions': sorted(p.name for p in (OUTPUTS/'predictions').glob('*.jsonl')),
    'metrics': sorted(p.name for p in (OUTPUTS/'metrics').glob('*.csv')),
    'tables': sorted(p.name for p in (OUTPUTS/'tables').glob('*')),
    'plots': sorted(p.name for p in (OUTPUTS/'plots').glob('*')),
    'docs': sorted(p.name for p in (OUTPUTS/'docs').glob('*')),
    'logs': sorted(p.name for p in (OUTPUTS/'logs').glob('*')),
    'repo_eval_modules': sorted(p.name for p in (PROJECT_ROOT/'repo'/'src'/'evaluation').glob('*.py')),
    'plan_schemas': sorted(p.name for p in (PROJECT_ROOT/'repo'/'docs').glob('*.json')) if (PROJECT_ROOT/'repo'/'docs').exists() else [],
}
state = LOGS / 'master_state_recheck_h100.md'
lines = ['# Master state recheck — H100 lane', f'**Captured:** {NOW}', '']
for k, v in inventory.items():
    lines.append(f'## {k} ({len(v)})')
    lines.extend([f'- {x}' for x in v[:80]])
    if len(v) > 80:
        lines.append(f'- … and {len(v)-80} more')
    lines.append('')
state.write_text('\n'.join(lines), encoding='utf-8')

print(f'GPU={gpu_name} VRAM={total/1e9:.2f}GB free={free/1e9:.2f}GB CUDA={cuda_v}')
print(f'transformers={pkg_versions.get("transformers")} torch={pkg_versions.get("torch")}')
print(f'predictions={len(inventory["predictions"])} metrics={len(inventory["metrics"])} '
      f'plots={len(inventory["plots"])} repo_modules={len(inventory["repo_eval_modules"])}')
print(f'WROTE {preflight}')
print(f'WROTE {snapshot}')
print(f'WROTE {state}')
