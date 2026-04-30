# Kernel bootstrap: re-mount Drive, load Spider data, define helpers, load Qwen model.
# Idempotent: skips re-loads if already in scope.

import json
import re
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

print('=== KERNEL BOOTSTRAP START ===')

# ---------- Drive ----------
PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS_DIR = PROJECT_ROOT / 'outputs'
PRACTICE_DIR = PROJECT_ROOT / 'practice'
REPO_DIR = PROJECT_ROOT / 'repo'

if not Path('/content/drive/MyDrive').exists():
    try:
        from google.colab import drive
        drive.mount('/content/drive', force_remount=False)
        print('Drive mounted')
    except Exception as exc:
        print(f'Drive mount FAILED: {exc!r}')
        raise SystemExit(1)
else:
    print('Drive already mounted')

assert SPIDER_DIR.exists(), f'SPIDER_DIR missing: {SPIDER_DIR}'

# ---------- Pip deps ----------
def _ensure_pkgs():
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                    'func_timeout', 'transformers>=4.45.0', 'accelerate>=0.34.0',
                    'bitsandbytes>=0.43.3', 'sentencepiece', 'safetensors', 'jsonschema'],
                    check=True)

import importlib
need_ft = importlib.util.find_spec('func_timeout') is None
need_jss = importlib.util.find_spec('jsonschema') is None
if need_ft or need_jss:
    print('installing missing pkgs...')
    _ensure_pkgs()

from func_timeout import FunctionTimedOut, func_timeout

# ---------- Spider data ----------
print('loading Spider data...')
dev = json.loads((SPIDER_DIR / 'dev.json').read_text(encoding='utf-8'))
tables_map = {row['db_id']: row for row in json.loads((SPIDER_DIR / 'tables.json').read_text(encoding='utf-8'))}
db_paths = {p.stem: p for p in (SPIDER_DIR / 'database').rglob('*.sqlite')}
smoke10 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_10.json').read_text(encoding='utf-8'))
smoke25 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_25.json').read_text(encoding='utf-8'))
print(f'  dev N={len(dev)}, tables_map={len(tables_map)}, db_paths={len(db_paths)}, smoke10={len(smoke10)}, smoke25={len(smoke25)}')

# ---------- Helpers ----------
def build_full_schema_prompt_context(db_id):
    tables = tables_map[db_id]
    table_names = tables.get('table_names_original') or tables.get('table_names')
    column_names = tables.get('column_names_original') or tables.get('column_names')
    by_table = {i: [] for i in range(len(table_names))}
    for table_idx, col in column_names:
        if table_idx >= 0:
            by_table.setdefault(table_idx, []).append(col)
    lines = [f'Database: {db_id}', 'Tables and columns:']
    for idx, table in enumerate(table_names):
        lines.append(f'- {table}(' + ', '.join(by_table.get(idx, [])) + ')')
    return '\n'.join(lines)


STOP = {'a','an','the','of','in','on','at','for','to','from','by','with','is','are','was','were',
        'what','which','who','whom','whose','how','many','much','show','list','find','give','me','all','each','every','any','do','does','did'}

def _toks(s):
    parts = re.split(r'[\s_]+', str(s).lower())
    return {p for p in parts if p and p not in STOP and len(p) > 1}

def lexical_schema_linking(question, db_id, tables_map, top_k=None, min_score=0.5):
    tables = tables_map[db_id]
    table_names = tables.get('table_names_original') or tables.get('table_names')
    column_names = tables.get('column_names_original') or tables.get('column_names')
    q_tokens = _toks(question)
    scores = {i: 0.0 for i in range(len(table_names))}
    matched_cols = {i: [] for i in range(len(table_names))}
    for i, t in enumerate(table_names):
        ov = len(q_tokens & _toks(t))
        scores[i] += ov * 2.0
    for ti, col in column_names:
        if ti < 0:
            continue
        ov = len(q_tokens & _toks(col))
        if ov > 0:
            scores[ti] += ov * 1.0
            matched_cols[ti].append(col)
    above = [(i, s) for i, s in scores.items() if s >= min_score]
    above.sort(key=lambda x: -x[1])
    if not above:
        selected = list(range(len(table_names)))
        fallback = True
    else:
        selected = sorted([i for i, _ in (above[:top_k] if top_k else above)])
        fallback = False
    return {
        'db_id': db_id, 'q_tokens': sorted(q_tokens),
        'all_tables': table_names,
        'selected_table_indexes': selected,
        'selected_tables': [table_names[i] for i in selected],
        'table_scores': {table_names[i]: scores[i] for i in range(len(table_names))},
        'matched_columns': {table_names[i]: matched_cols[i] for i in range(len(table_names)) if matched_cols[i]},
        'reduction_ratio': len(selected) / len(table_names) if table_names else 1.0,
        'fallback_used': fallback,
    }

def build_reduced_schema_context(db_id, selected_idx, tables_map):
    tables = tables_map[db_id]
    table_names = tables.get('table_names_original') or tables.get('table_names')
    column_names = tables.get('column_names_original') or tables.get('column_names')
    by_table = {i: [] for i in range(len(table_names))}
    for ti, col in column_names:
        if ti >= 0:
            by_table.setdefault(ti, []).append(col)
    lines = [f'Database: {db_id}', 'Tables and columns (reduced via lexical schema linking):']
    for idx in selected_idx:
        lines.append(f'- {table_names[idx]}(' + ', '.join(by_table.get(idx, [])) + ')')
    return '\n'.join(lines)

def make_prompt(item):
    schema = build_full_schema_prompt_context(item['db_id'])
    return textwrap.dedent(f'''
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema}

    Question: {item['question']}
    SQL:
    ''').strip()

def make_b1_prompt(item, link):
    schema = build_reduced_schema_context(item['db_id'], link['selected_table_indexes'], tables_map)
    return textwrap.dedent(f'''
    You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
    Use only the given schema. Return SQL only, no markdown and no explanation.

    {schema}

    Question: {item['question']}
    SQL:
    ''').strip()

def extract_sql(text):
    text = text.strip()
    text = re.sub(r'^```(?:sql)?', '', text, flags=re.I).strip()
    text = re.sub(r'```$', '', text).strip()
    m = re.search(r'(?is)(select\b.*)', text)
    if m:
        text = m.group(1).strip()
    text = text.split('\n\n')[0].strip()
    if ';' in text:
        text = text.split(';', 1)[0].strip()
    return text.rstrip(';') + ';'

def execute_sql(db_path, sql, timeout=8):
    def _run():
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        con.close()
        return rows
    return func_timeout(timeout, _run)

# ---------- Model ----------
import torch
print('loading model (this may take 2-5 min on cold cache)...')
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
quant_cfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                               bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True,
                                             device_map='auto', quantization_config=quant_cfg)
model.eval()
print(f'model loaded; VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

# ---------- Promote into __main__ ----------
import sys as _sys
mm = _sys.modules['__main__']
for name in ['PROJECT_ROOT','SPIDER_DIR','OUTPUTS_DIR','PRACTICE_DIR','REPO_DIR',
             'dev','tables_map','db_paths','smoke10','smoke25',
             'build_full_schema_prompt_context','lexical_schema_linking','build_reduced_schema_context',
             'make_prompt','make_b1_prompt','extract_sql','execute_sql','func_timeout','FunctionTimedOut',
             'model','tokenizer']:
    setattr(mm, name, locals()[name])

print('=== KERNEL BOOTSTRAP DONE ===')
print('STATUS=DONE')
