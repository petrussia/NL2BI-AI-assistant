# Step 4: B0 + B1 inference on Spider smoke25, reusing already-loaded model.
# Mirrors smoke10 cells (b0-inference-eval and B1_INFERENCE_EVAL).

import csv
import datetime as dt
import json
import re
import sqlite3
import textwrap
import time
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'
for sub in ['logs', 'metrics', 'predictions', 'tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
SUBSET_NAME = 'smoke_25'

import torch
import sys
mm = sys.modules['__main__']
# Take from main if available, else from our own globals (already imported in step 1)
def _from_main(name):
    return getattr(mm, name, None) if hasattr(mm, name) else globals().get(name)

model = _from_main('model') or globals().get('model')
tokenizer = _from_main('tokenizer') or globals().get('tokenizer')
tables_map = _from_main('tables_map') or globals().get('tables_map')
db_paths = _from_main('db_paths') or globals().get('db_paths')
build_full_schema_prompt_context = _from_main('build_full_schema_prompt_context') or globals().get('build_full_schema_prompt_context')
extract_sql = _from_main('extract_sql') or globals().get('extract_sql')
execute_sql = _from_main('execute_sql') or globals().get('execute_sql')
make_prompt = _from_main('make_prompt') or globals().get('make_prompt')
lexical_schema_linking = _from_main('lexical_schema_linking') or globals().get('lexical_schema_linking')
build_reduced_schema_context = _from_main('build_reduced_schema_context') or globals().get('build_reduced_schema_context')
make_b1_prompt = _from_main('make_b1_prompt') or globals().get('make_b1_prompt')
func_timeout = _from_main('func_timeout') or globals().get('func_timeout')
FunctionTimedOut = _from_main('FunctionTimedOut') or globals().get('FunctionTimedOut')

assert model is not None and tokenizer is not None, 'model/tokenizer not in scope'
assert callable(make_prompt) and callable(make_b1_prompt), 'prompt builders missing'
assert callable(lexical_schema_linking), 'lexical_schema_linking missing'

smoke25 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_25.json').read_text(encoding='utf-8'))
print(f'smoke25 N={len(smoke25)}')


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
            if isinstance(v, list):
                v = ', '.join(v)
            v = str(v).replace('|', '\\|').replace('\n', '<br>')[:700]
            vals.append(v)
        lines.append('|' + '|'.join(vals) + '|')
    return '\n'.join(lines) + '\n'


def write_run_artifacts(prefix, model_id, subset_name, records, started, extra_kvs=None):
    """Write predictions/metrics/summary/runlog/errors/examples for a run."""
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
    base_metrics = {
        'run_id': prefix,
        'model': model_id,
        'subset': subset_name,
        'n': total,
        'execution_match_count': match_count,
        'ex': ex,
        'executable_count': exec_count,
    }
    base_metrics.update(extra_kvs)
    with metrics_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(base_metrics.keys()))
        w.writeheader(); w.writerow(base_metrics)

    with summary_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['metric', 'value'])
        w.writeheader()
        for k, v in [('completed', 'true'), ('EX', ex), ('executable_count', exec_count),
                     ('total', total), ('model', model_id), ('subset', subset_name)] + list(extra_kvs.items()):
            w.writerow({'metric': k, 'value': v})

    runlog_path.write_text(textwrap.dedent(f'''
    {prefix} run log
    checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
    model: {model_id}
    subset: {subset_name}
    total: {total}
    executable_count: {exec_count}
    execution_match_count: {match_count}
    EX: {ex}
    elapsed_seconds: {time.time() - started:.2f}
    extra: {json.dumps(extra_kvs, ensure_ascii=False)}
    ''').strip() + '\n', encoding='utf-8')

    base_cols = ['idx', 'question', 'db_id', 'gold_sql', 'generated_sql', 'executable', 'execution_match', 'error_type']
    if any('selected_tables' in r for r in records):
        base_cols.insert(3, 'selected_tables')
    err_rows = [r for r in records if not r['execution_match']]
    errors_path.write_text(f'# {prefix} Error Cases\n\n' + md_table(err_rows[:20], base_cols), encoding='utf-8')
    examples_path.write_text(f'# {prefix} Examples\n\n' + md_table(records[:5], base_cols), encoding='utf-8')

    return {
        'prefix': prefix,
        'EX': ex,
        'executable_count': exec_count,
        'match_count': match_count,
        'total': total,
        'predictions_path': str(pred_path),
        'metrics_path': str(metrics_path),
        'summary_path': str(summary_path),
        'runlog_path': str(runlog_path),
        'errors_path': str(errors_path),
        'examples_path': str(examples_path),
    }


# === B0 smoke25 ===
print('\n=== B0 smoke25 inference ===')
b0_records = []
b0_started = time.time()
for i, item in enumerate(smoke25):
    prompt = make_prompt(item)
    raw = gen_sql(prompt)
    sql = extract_sql(raw)
    executable, execution_match, error_type, error_message = evaluate(item, sql)
    rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
           'gold_sql': item['query'], 'generated_raw': raw, 'generated_sql': sql,
           'executable': executable, 'execution_match': execution_match,
           'error_type': error_type, 'error_message': error_message}
    b0_records.append(rec)
    print(f'  B0 {i:>2} {item["db_id"]:<20} exec={executable} match={execution_match} err={error_type!r}')

b0_summary = write_run_artifacts(
    'b0_spider_smoke25', MODEL_ID, 'smoke_25', b0_records, b0_started,
    extra_kvs={'quantization': '4bit_bitsandbytes_config'},
)
print('B0_smoke25_RESULT', json.dumps(b0_summary, ensure_ascii=False))

# === B1 smoke25 ===
print('\n=== B1 smoke25 schema linking pre-pass ===')
linkings = [lexical_schema_linking(it['question'], it['db_id'], tables_map) for it in smoke25]

ex_lines = ['# B1 Schema Linking Examples (smoke25)\n',
            '| # | db_id | total_tables | selected | reduction | fallback | selected_tables | matched_cols |',
            '|---|---|---|---|---|---|---|---|']
for i, (item, lk) in enumerate(zip(smoke25, linkings)):
    sel_names = ', '.join(lk['selected_tables'])
    mcols = '; '.join(f"{t}: {','.join(c)}" for t, c in lk['matched_columns'].items()) or '--'
    ex_lines.append(f"| {i} | {item['db_id']} | {len(lk['all_tables'])} | {len(lk['selected_table_indexes'])} | {lk['reduction_ratio']:.2f} | {lk['fallback_used']} | {sel_names} | {mcols} |")
(OUTPUTS / 'tables' / 'b1_schema_linking_smoke25_examples.md').write_text('\n'.join(ex_lines) + '\n', encoding='utf-8')

linking_audit = {
    'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    'method': 'lexical token overlap (table_name x2, column_name x1, min_score=0.5, stopwords removed)',
    'subset': 'spider/smoke_25',
    'n_questions': len(linkings),
    'avg_total_tables_per_db': sum(len(lk['all_tables']) for lk in linkings) / len(linkings),
    'avg_selected_tables': sum(len(lk['selected_table_indexes']) for lk in linkings) / len(linkings),
    'avg_reduction_ratio': sum(lk['reduction_ratio'] for lk in linkings) / len(linkings),
    'fallback_full_schema_count': sum(1 for lk in linkings if lk['fallback_used']),
}
(OUTPUTS / 'logs' / 'b1_schema_linking_smoke25_audit.md').write_text(
    '# B1 Schema Linking Audit (smoke25)\n\n```json\n' + json.dumps(linking_audit, ensure_ascii=False, indent=2) + '\n```\n',
    encoding='utf-8',
)
print('LINKING_AUDIT_smoke25', json.dumps(linking_audit, ensure_ascii=False))

print('\n=== B1 smoke25 inference ===')
b1_records = []
b1_started = time.time()
for i, item in enumerate(smoke25):
    link = linkings[i]
    prompt = make_b1_prompt(item, link)
    raw = gen_sql(prompt)
    sql = extract_sql(raw)
    executable, execution_match, error_type, error_message = evaluate(item, sql)
    rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
           'gold_sql': item['query'], 'generated_raw': raw, 'generated_sql': sql,
           'executable': executable, 'execution_match': execution_match,
           'error_type': error_type, 'error_message': error_message,
           'selected_tables': link['selected_tables'],
           'schema_reduction_ratio': link['reduction_ratio'],
           'fallback_used': link['fallback_used']}
    b1_records.append(rec)
    print(f'  B1 {i:>2} {item["db_id"]:<20} sel={len(link["selected_tables"])}/{len(link["all_tables"])} exec={executable} match={execution_match} err={error_type!r}')

b1_summary = write_run_artifacts(
    'b1_spider_smoke25', MODEL_ID, 'smoke_25', b1_records, b1_started,
    extra_kvs={'quantization': '4bit_bitsandbytes_config',
               'schema_strategy': 'lexical_schema_linking',
               'avg_reduction_ratio': linking_audit['avg_reduction_ratio'],
               'fallback_full_schema_count': linking_audit['fallback_full_schema_count']},
)
print('B1_smoke25_RESULT', json.dumps(b1_summary, ensure_ascii=False))
print('\nSTATUS=DONE')
