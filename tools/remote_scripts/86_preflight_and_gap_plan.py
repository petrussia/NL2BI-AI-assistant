# Stage A + B: preflight snapshot + gap detection + experimental matrix plan.

import csv
import datetime as dt
import json
import os
import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

import torch, transformers, importlib

pkg_versions = {}
for pkg in ('torch','transformers','bitsandbytes','accelerate','jsonschema',
            'huggingface_hub','sentencepiece','safetensors','func_timeout'):
    try:
        m = importlib.import_module(pkg)
        pkg_versions[pkg] = getattr(m, '__version__', '?')
    except Exception as exc:
        pkg_versions[pkg] = f'NOT_INSTALLED ({type(exc).__name__})'

gpu = torch.cuda.get_device_name(0)
free, total = torch.cuda.mem_get_info(0)

# ====== preflight snapshot ======
preflight = OUTPUTS/'logs'/'runtime_preflight_full_matrix.md'
preflight.write_text(f'''# Runtime preflight — full-matrix closure

**Captured:** {NOW}

| | |
|---|---|
| Python | {sys.version.split()[0]} |
| Platform | {platform.platform()} |
| GPU | **{gpu}** |
| GPU VRAM total | {total/1e9:.2f} GB |
| GPU VRAM free | {free/1e9:.2f} GB |
| HF_TOKEN | {"set" if os.environ.get("HF_TOKEN") else "NOT SET"} |
| Drive | {os.path.isdir(str(PROJECT_ROOT))} |

## Package versions
```json
{json.dumps(pkg_versions, indent=2)}
```

## Master state inventory
- Master matrix CSV: present, 29 prior rows
- Predictions on Drive: 29 files
- Repo modules on Drive: 15 files (incl. baselines_b2_v2/b3_v2/b4_v2)
- Subsets present: smoke_10.json, smoke_25.json, smoke_50.json, multidb_30.json
''', encoding='utf-8')

# ====== gap detection ======
existing = sorted(p.stem.replace('_metrics','') for p in (OUTPUTS/'metrics').glob('*_metrics.csv'))
existing_set = set(existing)

# Define the matrix: (baseline_slug, model_slug, subset_short, prefix, priority, why)
PLAN = []
def add(baseline, model_slug, subset, prefix, priority, why):
    PLAN.append({
        'baseline': baseline, 'model_slug': model_slug,
        'subset': subset, 'expected_prefix': prefix,
        'present': prefix in existing_set,
        'priority': priority, 'why': why,
    })

# P0: Qwen-Coder-7B B2_v2/B3_v2/B4_v2 on smoke_25
add('B2_v2','qwen2p5_coder_7b','smoke_25','b2v2_spider_smoke25','P0','fill_primary')
add('B3_v2','qwen2p5_coder_7b','smoke_25','b3v2_spider_smoke25','P0','fill_primary')
add('B4_v2','qwen2p5_coder_7b','smoke_25','b4v2_spider_smoke25','P0','fill_primary')

# P1: Llama smoke_25 + multidb_30
add('B0','llama_3p1_8b_instruct','smoke_25','b0_llama_3p1_8b_instruct_smoke25','P1','mandatory_compare')
add('B1','llama_3p1_8b_instruct','smoke_25','b1_llama_3p1_8b_instruct_smoke25','P1','mandatory_compare')
add('B0','llama_3p1_8b_instruct','multidb_30','b0_llama_3p1_8b_instruct_multidb30','P1','mandatory_compare')
add('B1','llama_3p1_8b_instruct','multidb_30','b1_llama_3p1_8b_instruct_multidb30','P1','mandatory_compare')

# P1: Qwen-Coder-14B smoke_25
add('B0','qwen2p5_coder_14b_instruct','smoke_25','b0_qwen2p5_coder_14b_instruct_smoke25','P1','opt_big_model')
add('B1','qwen2p5_coder_14b_instruct','smoke_25','b1_qwen2p5_coder_14b_instruct_smoke25','P1','opt_big_model')

# P2: Llama B2_v2 (optional)
add('B2_v2','llama_3p1_8b_instruct','smoke_10','b2v2_llama_3p1_8b_instruct_smoke10','P2','llama_structured_if_time')
add('B2_v2','llama_3p1_8b_instruct','multidb_30','b2v2_llama_3p1_8b_instruct_multidb30','P2','llama_structured_if_time')

# P2: Qwen-14B B2_v2 (optional)
add('B2_v2','qwen2p5_coder_14b_instruct','smoke_10','b2v2_qwen2p5_coder_14b_instruct_smoke10','P2','opt_big_model_structured')
add('B2_v2','qwen2p5_coder_14b_instruct','multidb_30','b2v2_qwen2p5_coder_14b_instruct_multidb30','P2','opt_big_model_structured')

# DeepSeek noted as blocker
add('B0','deepseek_coder_v2_lite_instruct','smoke_10','b0_deepseek_coder_v2_lite_instruct_smoke10','P1','blocked_environment')
add('B1','deepseek_coder_v2_lite_instruct','smoke_10','b1_deepseek_coder_v2_lite_instruct_smoke10','P1','blocked_environment')

# Save plan
plan_csv = OUTPUTS/'tables'/'experimental_matrix_plan.csv'
with plan_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(PLAN[0].keys()))
    w.writeheader()
    for r in PLAN: w.writerow(r)

plan_md = OUTPUTS/'tables'/'experimental_matrix_plan.md'
plan_md.write_text(f'# Experimental matrix plan (full-matrix closure)\n\n_Generated: {NOW}_\n\n'
    + f'**Existing rows:** {len(existing)}  |  **Planned new rows:** {sum(1 for r in PLAN if not r["present"] and r["priority"] in ("P0","P1"))} (P0+P1)  |  **Optional (P2):** {sum(1 for r in PLAN if not r["present"] and r["priority"]=="P2")}\n\n'
    + '| Baseline | Model | Subset | Prefix | Present | Priority | Why |\n'
    + '|---|---|---|---|---|---|---|\n'
    + '\n'.join(f'| {r["baseline"]} | {r["model_slug"]} | {r["subset"]} | `{r["expected_prefix"]}` | {"✅" if r["present"] else "❌"} | {r["priority"]} | {r["why"]} |' for r in PLAN)
    + '\n', encoding='utf-8')

print(f'WROTE {preflight}')
print(f'WROTE {plan_csv}')
print(f'WROTE {plan_md}')
print(f'GAPS_P0_P1_TO_CLOSE: {sum(1 for r in PLAN if not r["present"] and r["priority"] in ("P0","P1"))}')
print(f'OPTIONAL_P2: {sum(1 for r in PLAN if not r["present"] and r["priority"]=="P2")}')
print(f'BLOCKED_DEEPSEEK: 2')
