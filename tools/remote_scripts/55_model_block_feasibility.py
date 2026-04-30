# Stage 7: HF_TOKEN check + Llama feasibility + DeepSeek feasibility.
# Does NOT actually load models (would interfere with BG inference). Just probes.

import csv
import datetime as dt
import json
import os
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()

# ----- HF_TOKEN detection -----
hf_token_env = os.environ.get('HF_TOKEN', '') or os.environ.get('HUGGINGFACE_HUB_TOKEN', '')
hf_token_present = bool(hf_token_env)
hf_token_source = 'HF_TOKEN env' if os.environ.get('HF_TOKEN') else (
                  'HUGGINGFACE_HUB_TOKEN env' if os.environ.get('HUGGINGFACE_HUB_TOKEN') else 'none')

# Try to validate token if present (HEAD request to gated repo)
token_valid = None
token_check_msg = ''
if hf_token_present:
    try:
        import urllib.request
        req = urllib.request.Request(
            'https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct',
            headers={'Authorization': f'Bearer {hf_token_env}'})
        with urllib.request.urlopen(req, timeout=10) as r:
            token_valid = (r.status == 200)
            token_check_msg = f'HEAD ok status={r.status}'
    except Exception as exc:
        token_valid = False
        token_check_msg = f'HEAD failed: {type(exc).__name__}: {str(exc)[:200]}'
else:
    token_check_msg = 'no token to check'

# ----- Try import bnb config to verify availability -----
import torch
free_vram_mb = (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated()) // (1024*1024)
total_vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024*1024)
gpu_name = torch.cuda.get_device_name(0)

# Estimates (4-bit nf4)
estimates = {
    'Qwen/Qwen2.5-Coder-7B-Instruct': 5400,    # MB VRAM observed
    'Qwen/Qwen2.5-7B-Instruct':       5400,
    'meta-llama/Llama-3.1-8B-Instruct': 6200,  # estimate
    'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct': 13000,  # 16B MoE; conservative
    'Qwen/Qwen3-8B': 6000,
    'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B': 5400,
}

# ----- Feasibility table -----
feasibility = []
for mid, vram_est in estimates.items():
    fits = vram_est < total_vram_mb - 500   # leave 500 MB buffer
    issues = []
    if mid.startswith('meta-llama/'):
        if not hf_token_present:
            issues.append('gated_repo:no_HF_TOKEN')
        elif token_valid is False:
            issues.append('gated_repo:token_invalid_for_repo')
    if mid.startswith('deepseek-ai/'):
        if vram_est >= total_vram_mb - 1000:
            issues.append(f'tight_vram (estimate {vram_est} MB on {total_vram_mb} MB total)')
    feasibility.append({
        'model_id': mid,
        'estimated_vram_mb': vram_est,
        'fits_total_vram': fits,
        'gated': mid.startswith('meta-llama/') or mid.startswith('mistralai/'),
        'issues': '; '.join(issues) if issues else 'none',
    })

# ----- Write CSV + MD -----
csv_path = OUTPUTS / 'tables' / 'model_runtime_feasibility.csv'
with csv_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['model_id','estimated_vram_mb','fits_total_vram','gated','issues'])
    for r in feasibility:
        w.writerow([r['model_id'], r['estimated_vram_mb'], r['fits_total_vram'], r['gated'], r['issues']])

# Final model matrix CSV — what we actually have artefacts for
matrix_path = OUTPUTS / 'tables' / 'final_model_matrix.csv'
have_artefacts = {}
metrics_dir = OUTPUTS / 'metrics'
if metrics_dir.exists():
    import re as _re
    for p in metrics_dir.iterdir():
        # parse: b{0,1}_<modelslug>_smoke10_metrics.csv  OR  b{0,1,2,3,4}_spider_smoke{10,25}_metrics.csv
        m = _re.match(r'^(b[0-9a-z_]+?)_(spider|qwen[^_]*|llama[^_]*|deepseek[^_]*|.+)_smoke(\d+)_metrics\.csv$', p.name)
        if m:
            baseline = m.group(1).upper()
            slug = m.group(2)
            n = int(m.group(3))
            try:
                row = next(csv.DictReader(p.open(encoding='utf-8')))
                ex = float(row.get('ex', 0)) if row.get('ex') else None
                model_in_csv = row.get('model', slug)
                have_artefacts.setdefault(model_in_csv, []).append((baseline, f'smoke_{n}', ex))
            except Exception: pass

with matrix_path.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['model','baseline','subset','EX'])
    for model, runs in sorted(have_artefacts.items()):
        for baseline, subset, ex in runs:
            w.writerow([model, baseline, subset, f'{ex:.4f}' if ex is not None else ''])

# ----- model_block_closure.md -----
md = ['# Model Block Closure', '',
      f'Audited at: {ts}',
      f'GPU: {gpu_name}, total VRAM {total_vram_mb} MB, free {free_vram_mb} MB at probe time.',
      f'HF_TOKEN present: **{hf_token_present}** (source: {hf_token_source})',
      f'HF_TOKEN check vs Llama-3.1-8B-Instruct: **{token_valid}** ({token_check_msg})',
      '',
      '## Mandatory model triple status',
      '',
      '| Model | Status | Note |',
      '|---|---|---|']

# Determine status per mandatory
def status_for(model_id):
    if model_id in have_artefacts and any(b.startswith('B') for b,_,_ in have_artefacts[model_id]):
        return 'ARTEFACTS_PRESENT'
    if model_id == 'meta-llama/Llama-3.1-8B-Instruct':
        if not hf_token_present: return 'BLOCKED:no_HF_TOKEN'
        if token_valid is False: return 'BLOCKED:gated_token_invalid'
        return 'AVAILABLE_BUT_NOT_RUN'
    if model_id == 'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct':
        for r in feasibility:
            if r['model_id'] == model_id:
                return 'BLOCKED:vram_tight' if 'tight_vram' in r['issues'] else 'AVAILABLE_BUT_NOT_RUN'
    if model_id == 'Qwen/Qwen2.5-Coder-7B-Instruct':
        return 'ARTEFACTS_PRESENT' if any('Qwen' in m and 'Coder' in m for m in have_artefacts) else 'NOT_RUN'
    return 'UNKNOWN'

md.append(f"| `Qwen/Qwen2.5-Coder-7B-Instruct` | {status_for('Qwen/Qwen2.5-Coder-7B-Instruct')} | primary; multiple baselines on smoke10/25 |")
md.append(f"| `meta-llama/Llama-3.1-8B-Instruct` | {status_for('meta-llama/Llama-3.1-8B-Instruct')} | gated repo; needs HF_TOKEN configured in Colab kernel |")
md.append(f"| `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct` | {status_for('deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct')} | 16B MoE, ~13 GB in 4-bit, tight on L4 |")

md += ['',
       '## Honest blocker statements',
       '',
       '### Llama-3.1-8B-Instruct',
       f'- HF_TOKEN was {"PRESENT" if hf_token_present else "MISSING"} at the time of this check.',
       f'- Token validation against the gated repo: {token_valid}.',
       f'- {"Loadable on next iteration if token validated" if token_valid else "Cannot load until a valid HF_TOKEN is provided in the Colab kernel:" if not hf_token_present else "Token is present but does not pass HEAD against the model card; check accept-license + access grant in Hugging Face account"}.',
       '- **Workaround already in place:** comparator runs use `Qwen/Qwen2.5-7B-Instruct` (non-Coder, non-gated, same parameter count). See `outputs/metrics/b{0,1}_qwen_qwen2.5_7b_instruct_smoke10_metrics.csv`.',
       '',
       '### DeepSeek-Coder-V2-Lite-Instruct',
       f'- Estimated 4-bit VRAM: {estimates["deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"]} MB on {total_vram_mb} MB GPU.',
       f'- Buffer: {total_vram_mb - estimates["deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"]} MB after load (before inference KV cache).',
       '- Verdict: **tight on L4** (works in principle but risks OOM on long contexts). Not attempted in this session because the BG was busy with B2_v1/B3_v1/B4_final on Qwen-Coder.',
       '- **Recommendation:** load DeepSeek standalone in a fresh kernel (after freeing Qwen-Coder), B0 + B1 only on smoke10 (`make_prompt`/`make_b1_prompt` are model-agnostic).',
       '',
       '## Final model matrix',
       '',
       'See `outputs/tables/final_model_matrix.csv` for the actual baseline×subset×EX entries derived from metrics on Drive.',
       ]
(OUTPUTS / 'logs' / 'model_block_closure.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

print(f'HF_TOKEN present: {hf_token_present}')
print(f'token_valid: {token_valid}')
print(f'GPU: {gpu_name}, VRAM total {total_vram_mb} MB')
print(f'WROTE {csv_path}')
print(f'WROTE {matrix_path}')
print(f'WROTE {OUTPUTS / "logs" / "model_block_closure.md"}')
print('STATUS=DONE')
