"""Run Coder-7B inference for one Spider2-DBT task. The prompt content
is shipped via a /tmp file (base64). The output is returned as base64.
"""
import base64, json, os, sys, time
from pathlib import Path

PROMPT_B64 = '__PROMPT_B64__'
TASK_ID = '__TASK_ID__'
MAX_NEW = __MAX_NEW__
MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'

prompt = base64.b64decode(PROMPT_B64).decode('utf-8')
print(f'TASK_ID={TASK_ID} prompt_chars={len(prompt)}')

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Reuse if already loaded
g = globals()
if g.get('_TOK') is None or g.get('_MODEL') is None:
    print('LOADING coder...')
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID,
                                                   torch_dtype=torch.bfloat16,
                                                   device_map='cuda')
    model.eval()
    g['_TOK'] = tok; g['_MODEL'] = model
    print(f'LOADED in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1<<20)} MB')
else:
    tok = g['_TOK']; model = g['_MODEL']
    print('REUSING cached model')

t0 = time.time()
messages = [{'role': 'user', 'content': prompt}]
try:
    rendered = tok.apply_chat_template(messages, tokenize=False,
                                         add_generation_prompt=True)
except Exception:
    rendered = prompt

with torch.inference_mode():
    ids = tok(rendered, return_tensors='pt', truncation=True,
               max_length=14000).to('cuda')
    out = model.generate(**ids, max_new_tokens=MAX_NEW, do_sample=False,
                           pad_token_id=tok.eos_token_id)
    n_gen = out.shape[1] - ids['input_ids'].shape[1]
    response = tok.decode(out[0][ids['input_ids'].shape[1]:],
                            skip_special_tokens=True)
elapsed = time.time() - t0
print(f'GEN_OK n_gen_tokens={n_gen} elapsed={elapsed:.1f}s response_chars={len(response)}')
print(f'\nFIRST 500 chars:\n{response[:500]}')

# Save response to /tmp file + dump base64 marker
out_path = Path(f'/tmp/_dbt_response_{TASK_ID}.txt')
out_path.write_text(response, encoding='utf-8')
print(f'\nWROTE {out_path}')
print('---RESPONSE_B64_BEGIN---')
print(base64.b64encode(response.encode('utf-8')).decode('ascii'))
print('---RESPONSE_B64_END---')
