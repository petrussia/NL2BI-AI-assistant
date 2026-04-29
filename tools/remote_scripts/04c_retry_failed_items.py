# Step 4c: retry only the items whose error_type == 'gen_failed' in either
# B0 or B1 smoke25 predictions. Updates the JSONL in place and re-emits metrics.

import csv
import datetime as dt
import json
import textwrap
import time
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'
MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'

import sys
mm = sys.modules['__main__']

def _from_main(name):
    return getattr(mm, name, None) or globals().get(name)

model = _from_main('model'); tokenizer = _from_main('tokenizer')
tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
make_prompt = _from_main('make_prompt'); make_b1_prompt = _from_main('make_b1_prompt')
extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')
lexical_schema_linking = _from_main('lexical_schema_linking')
func_timeout = _from_main('func_timeout'); FunctionTimedOut = _from_main('FunctionTimedOut')

assert model is not None and tokenizer is not None
import torch

def gen_sql(prompt):
    messages = [{'role': 'user', 'content': prompt}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(rendered, return_tensors='pt')
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=192, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    raw = tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    return raw


def evaluate(item, generated_sql):
    gold_sql = item['query']
    executable, execution_match = False, False
    error_type, error_message = '', ''
    try:
        pred_rows = execute_sql(db_paths[item['db_id']], generated_sql)
        executable = True
        gold_rows = execute_sql(db_paths[item['db_id']], gold_sql)
        execution_match = sorted(pred_rows) == sorted(gold_rows)
        if not execution_match:
            error_type = 'result_mismatch'
    except FunctionTimedOut as exc:
        error_type, error_message = 'timeout', repr(exc)
    except Exception as exc:
        error_type, error_message = type(exc).__name__, str(exc)
    return executable, execution_match, error_type, error_message


def md_table(rows, cols):
    lines = ['|' + '|'.join(cols) + '|', '|' + '|'.join(['---'] * len(cols)) + '|']
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c, '')
            if isinstance(v, list): v = ', '.join(v)
            v = str(v).replace('|', '\\|').replace('\n', '<br>')[:700]
            vals.append(v)
        lines.append('|' + '|'.join(vals) + '|')
    return '\n'.join(lines) + '\n'


def rewrite_artifacts(prefix, model_id, subset_name, records, started, extra_kvs=None):
    pred_path = OUTPUTS / 'predictions' / f'{prefix}_predictions.jsonl'
    metrics_path = OUTPUTS / 'metrics' / f'{prefix}_metrics.csv'
    summary_path = OUTPUTS / 'tables' / f'{prefix}_summary.csv'
    runlog_path = OUTPUTS / 'logs' / f'{prefix}_runlog.txt'
    errors_path = OUTPUTS / 'tables' / f'{prefix}_error_cases.md'
    examples_path = OUTPUTS / 'tables' / f'{prefix}_examples.md'

    pred_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')

    total = len(records)
    exec_count = sum(1 for r in records if r['executable'])
    match_count = sum(1 for r in records if r['execution_match'])
    ex = match_count / total if total else 0.0
    extra_kvs = extra_kvs or {}
    base = {'run_id': prefix, 'model': model_id, 'subset': subset_name, 'n': total,
            'execution_match_count': match_count, 'ex': ex, 'executable_count': exec_count}
    base.update(extra_kvs)
    with metrics_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(base.keys()))
        w.writeheader(); w.writerow(base)
    with summary_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['metric', 'value'])
        w.writeheader()
        for k, v in [('completed', 'true'), ('EX', ex), ('executable_count', exec_count),
                     ('total', total), ('model', model_id), ('subset', subset_name)] + list(extra_kvs.items()):
            w.writerow({'metric': k, 'value': v})
    runlog_path.write_text(textwrap.dedent(f'''
    {prefix} run log (after retry pass)
    checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
    model: {model_id}
    subset: {subset_name}
    total: {total}
    executable_count: {exec_count}
    execution_match_count: {match_count}
    EX: {ex}
    elapsed_seconds_retry: {time.time() - started:.2f}
    extra: {json.dumps(extra_kvs, ensure_ascii=False)}
    ''').strip() + '\n', encoding='utf-8')
    base_cols = ['idx', 'question', 'db_id', 'gold_sql', 'generated_sql', 'executable', 'execution_match', 'error_type']
    if any('selected_tables' in r for r in records):
        base_cols.insert(3, 'selected_tables')
    err_rows = [r for r in records if not r['execution_match']]
    errors_path.write_text(f'# {prefix} Error Cases\n\n' + md_table(err_rows[:20], base_cols), encoding='utf-8')
    examples_path.write_text(f'# {prefix} Examples\n\n' + md_table(records[:5], base_cols), encoding='utf-8')


def retry_run(jsonl_name, prefix, prompt_fn_name, extra_factory=None, extra_kvs=None):
    """Reload predictions, retry items with gen_failed, rewrite artifacts."""
    pred_path = OUTPUTS / 'predictions' / jsonl_name
    if not pred_path.exists():
        print(f'  {prefix}: predictions file missing, skip')
        return
    records = [json.loads(l) for l in pred_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    failed_idx = [i for i, r in enumerate(records) if r.get('error_type') == 'gen_failed']
    if not failed_idx:
        print(f'  {prefix}: no gen_failed items, skip retry')
        return
    print(f'  {prefix}: retrying {len(failed_idx)} item(s) at idx {failed_idx}')
    smoke25 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_25.json').read_text(encoding='utf-8'))
    started = time.time()
    for idx in failed_idx:
        item = smoke25[idx]
        try:
            extra = extra_factory(item) if extra_factory else None
            if prompt_fn_name == 'make_prompt':
                prompt = make_prompt(item)
            elif prompt_fn_name == 'make_b1_prompt':
                prompt = make_b1_prompt(item, extra)
            raw = gen_sql(prompt)
            sql = extract_sql(raw)
            executable, execution_match, error_type, error_message = evaluate(item, sql)
        except Exception as exc:
            raw, sql = '', ''
            executable, execution_match = False, False
            error_type, error_message = 'gen_failed_retry', f'{type(exc).__name__}: {exc}'
        new_rec = {**records[idx], 'generated_raw': raw, 'generated_sql': sql,
                   'executable': executable, 'execution_match': execution_match,
                   'error_type': error_type, 'error_message': error_message}
        if extra:
            new_rec['selected_tables'] = extra['selected_tables']
            new_rec['schema_reduction_ratio'] = extra['reduction_ratio']
            new_rec['fallback_used'] = extra['fallback_used']
        records[idx] = new_rec
        print(f'    retry {idx}: exec={executable} match={execution_match} err={error_type!r}')
    rewrite_artifacts(prefix, MODEL_ID, 'smoke_25', records, started, extra_kvs=extra_kvs)
    print(f'  {prefix}: rewritten')


print('=== retry pass for gen_failed items ===')
retry_run('b0_spider_smoke25_predictions.jsonl', 'b0_spider_smoke25', 'make_prompt',
          extra_factory=None, extra_kvs={'quantization': '4bit_bitsandbytes_config'})

# For B1 we need the linking re-computed
def b1_extra(item):
    return lexical_schema_linking(item['question'], item['db_id'], tables_map)

# B1 needs the smoke25 linking audit values to keep extra_kvs consistent — load from log if present
b1_audit_path = OUTPUTS / 'logs' / 'b1_schema_linking_smoke25_audit.md'
b1_extra_kvs = {'quantization': '4bit_bitsandbytes_config', 'schema_strategy': 'lexical_schema_linking'}
if b1_audit_path.exists():
    txt = b1_audit_path.read_text(encoding='utf-8')
    import re
    m = re.search(r'"avg_reduction_ratio":\s*([\d.]+)', txt)
    if m:
        b1_extra_kvs['avg_reduction_ratio'] = float(m.group(1))
    m = re.search(r'"fallback_full_schema_count":\s*(\d+)', txt)
    if m:
        b1_extra_kvs['fallback_full_schema_count'] = int(m.group(1))

retry_run('b1_spider_smoke25_predictions.jsonl', 'b1_spider_smoke25', 'make_b1_prompt',
          extra_factory=b1_extra, extra_kvs=b1_extra_kvs)
print('STATUS=DONE')
