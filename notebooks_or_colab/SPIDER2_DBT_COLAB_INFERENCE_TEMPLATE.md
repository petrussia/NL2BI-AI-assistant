# Spider2-DBT Colab inference template (manual / file-relay mode)

_The canonical, safe-by-default flow: your local machine holds the SSH
key to the server. Colab only does inference — generates
`model_response.txt`. The local machine relays the response to the
server and triggers dbt._

```
[Colab GPU] ──HTTP/Drive── [your local machine] ──SSH── [server: dbt + DuckDB]
   inference                relay + apply             evaluation
```

This avoids putting an SSH private key inside Colab. Direct
Colab→server SSH is described at the bottom as an opt-in; the default
flow does not need it.

---

## Step A — on your local machine: build prompt for one task

```bash
cd D:\HSE\Диплом\NL2BI-AI-assistant
python spider2_dbt_bridge/inspect_remote_spider2_dbt.py
# pick a task_id (e.g. asana001) from reports/spider2_dbt_tasks_index.json

python spider2_dbt_bridge/export_task_context.py --task-id asana001
python spider2_dbt_bridge/build_model_prompt.py  --task-id asana001
# -> data/spider2_dbt/tasks/asana001/prompt.txt
```

Upload `data/spider2_dbt/tasks/asana001/prompt.txt` to Drive (Colab
workspace), e.g. `/content/drive/MyDrive/spider2_dbt_inbox/asana001/prompt.txt`.

## Step B — in Colab: run the model on the prompt

```python
# Cell 1: load the model (Coder-7B BF16 on L4 — same as the v8 BG run)
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
tok = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16,
                                               device_map='cuda')
model.eval()

# Cell 2: read the prompt + run inference
TASK_ID = 'asana001'
INBOX = Path(f'/content/drive/MyDrive/spider2_dbt_inbox/{TASK_ID}')
prompt = (INBOX / 'prompt.txt').read_text(encoding='utf-8')

def gen(prompt: str, max_new: int = 1200) -> str:
    messages = [{'role': 'user', 'content': prompt}]
    rendered = tok.apply_chat_template(messages, tokenize=False,
                                         add_generation_prompt=True)
    with torch.inference_mode():
        ids = tok(rendered, return_tensors='pt', truncation=True,
                   max_length=14000).to('cuda')
        out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                               pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True)

response = gen(prompt, max_new=1500)
print(response[:1500])

# Cell 3: save the response next to the prompt
out_path = INBOX / 'model_response.txt'
out_path.write_text(response, encoding='utf-8')
print('SAVED:', out_path, 'chars=', len(response))
```

## Step C — on your local machine: relay response → server eval → collect

Download `model_response.txt` from Drive into the local project:

```bash
# (manual: download via Drive UI or `gdown` to:)
data/spider2_dbt/tasks/asana001/model_response.txt
```

Then run the rest of the pipeline:

```bash
python spider2_dbt_bridge/apply_model_output.py     --task-id asana001
python spider2_dbt_bridge/run_remote_evaluation.py  --task-id asana001
python spider2_dbt_bridge/collect_remote_result.py  --task-id asana001
cat data/spider2_dbt/tasks/asana001/result/result.json
```

Or one shot via the orchestrator (waits up to 5 min for
`model_response.txt` to appear before continuing):

```bash
python spider2_dbt_bridge/run_one_task_pipeline.py --task-id asana001 --mode manual
```

## Output you get back

```
data/spider2_dbt/tasks/asana001/
  context/
    context.json           # task instruction + paths + step_idx
    duckdb_tables.json     # DuckDB schemas
    task_files/            # snapshot of dbt project source files
  prompt.txt               # what was sent to the model
  model_response.txt       # what the model returned
  apply_manifest.json      # which files we shipped to the server
  result/
    result.json            # dbt status (deps_rc, run_rc, test_rc, overall_ok)
    summary.json           # bridge-side summary
    logs/                  # full dbt deps/run/test logs
    target/run_results.json
    target/manifest.json
    workspace_snapshot.tgz # full final workspace tar
```

## Optional: direct Colab→server SSH (NOT default)

Only if you really want Colab to skip the local relay step.

Cost: an SSH private key has to live in the Colab session. Treat it as
a **temporary key**:
1. Generate a new key pair on your laptop:
   `ssh-keygen -t ed25519 -f ~/.ssh/spider2_colab -C spider2_colab_temporary`
2. Append the public half to the server's `~/.ssh/authorized_keys` for `denis`.
3. Upload `~/.ssh/spider2_colab` to Colab's `/content/.ssh/` (Colab
   instances are ephemeral; the key dies with the runtime).
4. In the Colab notebook:
   ```bash
   !chmod 700 /content/.ssh && chmod 600 /content/.ssh/spider2_colab
   !ssh -i /content/.ssh/spider2_colab -o StrictHostKeyChecking=accept-new \
        denis@103.54.18.91 "echo OK"
   ```
5. Use scp/ssh from Colab to push `model_response.txt` and trigger dbt:
   ```bash
   !scp -i /content/.ssh/spider2_colab data/.../model_response.txt \
       denis@103.54.18.91:/home/denis/dbt/outputs/colab_bridge/tasks/asana001/incoming/
   !ssh -i /content/.ssh/spider2_colab denis@103.54.18.91 \
        "/home/denis/dbt/.venv/bin/python /home/denis/dbt/colab_bridge/server_run_task_eval.py --task-id asana001"
   ```
6. **When done, remove the public key from `authorized_keys`** so the
   ephemeral Colab key cannot be reused by anyone who recovers it.

The bridge does not enable this path automatically. The default
single-relay flow (Colab generates → Drive → local relays → server) is
preferred.

## Limits / safety

- One task per invocation. The bridge refuses `--all` by design.
- Server stays on `dbt-core 1.10.8 + dbt-duckdb 1.10.1`; no model weights,
  no API keys, no Spider2-side ReAct loop.
- Workspace is always under `outputs/colab_bridge/tasks/<TASK>/workspace/`,
  separate from the upstream example dir.
- Bridge writes raw `model_response.txt` into `incoming/` on the server
  for audit; deletes nothing without `--force`.
