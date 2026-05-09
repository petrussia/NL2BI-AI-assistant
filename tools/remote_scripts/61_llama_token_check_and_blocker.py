# Definitive Llama-3.1-8B-Instruct token + access probe + blocker artifact.
# Tries every reasonable place a token might live, then if absent emits a final
# blocker. If a token is found, also smoke-tests gated repo access.

import datetime as dt
import json
import os
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
LOGS = PROJECT_ROOT / 'outputs' / 'logs'
LOGS.mkdir(parents=True, exist_ok=True)
TOKEN_LOG = LOGS / 'llama_token_check.md'
BLOCKER = LOGS / 'llama_blocker_final.md'

MODEL_ID = 'meta-llama/Llama-3.1-8B-Instruct'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()

# ---- env vars ----
env_keys = ['HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'HUGGINGFACE_HUB_TOKEN',
            'HF_API_TOKEN', 'HUGGINGFACE_TOKEN']
env_findings = {k: bool(os.environ.get(k)) for k in env_keys}

# ---- token file ----
hf_token_file = Path(os.path.expanduser('~/.cache/huggingface/token'))
hf_token_file_present = hf_token_file.exists()

# ---- Colab userdata ----
colab_findings = {}
try:
    from google.colab import userdata  # type: ignore
    for k in ('HF_TOKEN', 'HUGGINGFACE_TOKEN', 'HF_API_TOKEN'):
        try:
            v = userdata.get(k)
            colab_findings[k] = 'present' if v else 'absent'
        except Exception as exc:
            colab_findings[k] = f'error_{type(exc).__name__}'
except Exception as exc:
    colab_findings['_module_error'] = f'{type(exc).__name__}: {exc}'

# ---- final decision ----
have_token = any(env_findings.values()) or hf_token_file_present or \
             any(v == 'present' for v in colab_findings.values())

# ---- if token, attempt to access gated repo ----
gated_probe = {}
if have_token:
    try:
        from huggingface_hub import HfApi
        token = (os.environ.get('HF_TOKEN') or
                 os.environ.get('HUGGING_FACE_HUB_TOKEN') or
                 os.environ.get('HUGGINGFACE_HUB_TOKEN') or
                 (hf_token_file.read_text().strip() if hf_token_file_present else ''))
        api = HfApi(token=token or None)
        info = api.model_info(MODEL_ID)
        gated_probe = {'access': 'ok', 'sha': info.sha, 'gated': info.gated}
    except Exception as exc:
        gated_probe = {'access': 'failed',
                       'error_class': type(exc).__name__,
                       'error_message': str(exc)[:300]}

# ---- write token check log ----
TOKEN_LOG.write_text(textwrap.dedent(f'''
# Llama-3.1-8B-Instruct — HF_TOKEN check

**Probed at:** {NOW}
**Target model:** `{MODEL_ID}`

## Env-var presence
{json.dumps(env_findings, indent=2)}

## Token file
- Path: `{hf_token_file}`
- Present: **{hf_token_file_present}**

## Colab userdata (Secrets)
{json.dumps(colab_findings, indent=2)}

## Final decision
- have_token = **{have_token}**
- gated_repo_probe: {json.dumps(gated_probe, indent=2)}
''').strip()+'\n', encoding='utf-8')

# ---- write blocker if no token ----
if not have_token:
    BLOCKER.write_text(textwrap.dedent(f'''
    # Llama-3.1-8B-Instruct — final blocker (HF_TOKEN absent)

    **Issued:** {NOW}
    **Model:** `{MODEL_ID}` (gated repo on Hugging Face Hub)

    ## Why we cannot run it
    1. No `HF_TOKEN` (or any of `HUGGING_FACE_HUB_TOKEN`, `HUGGINGFACE_HUB_TOKEN`,
       `HF_API_TOKEN`, `HUGGINGFACE_TOKEN`) is set in the runtime environment.
    2. `~/.cache/huggingface/token` does not exist on this Colab kernel.
    3. Colab Secrets (`google.colab.userdata`) probe returned no token either.
    4. The Llama-3.1-8B-Instruct repo on the Hub is **gated** — license must be
       accepted by the Hugging Face account *and* a personal access token must be
       attached to the runtime.

    ## What it would take to unblock — exact, minimal steps
    1. Visit `https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct` while
       logged in with a Hugging Face account that has accepted the license.
    2. Generate a *read* personal access token at
       `https://huggingface.co/settings/tokens` (scope: *Read access to public
       gated repos*).
    3. In this Colab notebook, add the token via **Notebook ▸ Secrets ▸
       Add new secret**, name it `HF_TOKEN`, value = the token, and tick
       *Notebook access*. Then rerun the bridge bootstrap cell so the kernel
       picks it up.
    4. After that, re-trigger the Llama BG script — it will load the model
       in 4-bit nf4 (≈ 6 GB VRAM on L4) and run B0/B1 smoke10 in ~25 min.

    ## Honest classification
    Mandatory model from the proposal — **not evaluated this iteration** because
    the runtime is missing the credentials required to download a gated repo.
    Documented as a *credential blocker*, not skipped silently.
    ''').strip()+'\n', encoding='utf-8')
    print('LLAMA_TOKEN_ABSENT_BLOCKER_WRITTEN')
else:
    print('LLAMA_TOKEN_PRESENT', json.dumps(gated_probe, ensure_ascii=False))
print(f'TOKEN_LOG={TOKEN_LOG}')
print(f'BLOCKER={BLOCKER if not have_token else "(not_written; have_token)"}')
