# Stage 3: B2_v1 inference on smoke25 in BG. Same pattern as 23 but n=25.

import csv
import datetime as dt
import json
import sys
import textwrap
import threading
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
for sub in ['logs','metrics','predictions','tables']:
    (OUTPUTS / sub).mkdir(parents=True, exist_ok=True)

MODEL_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
TASK_LOG = OUTPUTS / 'logs' / 'b2_v1_smoke25_bg_task_log.txt'

eval_path = str(REPO / 'src' / 'evaluation')
if eval_path not in sys.path:
    sys.path.insert(0, eval_path)
for mod in list(sys.modules):
    if mod.startswith('baselines_b2_v1'):
        del sys.modules[mod]
import baselines_b2_v1 as b2v1

mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None) or globals().get(name)

model = _from_main('model'); tokenizer = _from_main('tokenizer')
tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
lexical_schema_linking = _from_main('lexical_schema_linking')
build_reduced_schema_context = _from_main('build_reduced_schema_context')
extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')
func_timeout = _from_main('func_timeout'); FunctionTimedOut = _from_main('FunctionTimedOut')

assert model is not None and tokenizer is not None

if 'B2_V1_SMOKE25_BG_THREAD' in globals() and B2_V1_SMOKE25_BG_THREAD.is_alive():
    print(f'BG already running thread={B2_V1_SMOKE25_BG_THREAD.name}')
    print('STARTED=False (already_running)')
    raise SystemExit(0)


def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def gen(prompt, max_new):
    import torch
    messages = [{'role':'user','content':prompt}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(rendered, return_tensors='pt')
    inputs = {k: v.to(model.device) for k,v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)


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
    lines = ['|' + '|'.join(cols) + '|', '|' + '|'.join(['---']*len(cols)) + '|']
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c, '')
            if isinstance(v, list): v = ', '.join(v)
            if isinstance(v, dict): v = json.dumps(v, ensure_ascii=False)
            v = str(v).replace('|','\\|').replace('\n','<br>')[:700]
            vals.append(v)
        lines.append('|' + '|'.join(vals) + '|')
    return '\n'.join(lines) + '\n'


def background_main():
    try:
        TASK_LOG.write_text('', encoding='utf-8')
        task_log('B2_V1_SMOKE25_BG_START')
        smoke25 = json.loads((SPIDER_DIR/'subsets'/'smoke_25.json').read_text(encoding='utf-8'))
        plan_schema = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
        task_log(f'smoke25 N={len(smoke25)}')

        records = []
        started = time.time()
        pred_path = OUTPUTS / 'predictions' / 'b2_v1_spider_smoke25_predictions.jsonl'
        plan_examples_path = OUTPUTS / 'tables' / 'b2_v1_plan_examples_smoke25.md'
        plan_example_lines = ['# B2 v1 Plan Examples (smoke25)\n']

        for i, item in enumerate(smoke25):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            reduced_ctx = build_reduced_schema_context(item['db_id'], link['selected_table_indexes'], tables_map)

            plan_raw = ''
            plan_parsed = None
            plan_valid = False
            plan_error = ''
            try:
                plan_prompt = b2v1.make_plan_prompt(item['question'], reduced_ctx)
                plan_raw = gen(plan_prompt, max_new=320)
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'

            generated_raw = ''
            generated_sql = ''
            executable = False
            execution_match = False
            error_type = ''
            error_message = ''
            if plan_valid:
                try:
                    sql_prompt = b2v1.make_plan_to_sql_prompt(item['question'], plan_parsed, reduced_ctx)
                    generated_raw = gen(sql_prompt, max_new=192)
                    generated_sql = extract_sql(generated_raw)
                    executable, execution_match, error_type, error_message = evaluate(item, generated_sql)
                except Exception as exc:
                    error_type, error_message = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                error_type = 'plan_invalid'
                error_message = plan_error

            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item['query'], 'plan_raw': plan_raw, 'plan_parsed': plan_parsed,
                   'plan_valid': plan_valid, 'plan_error': plan_error,
                   'generated_raw': generated_raw, 'generated_sql': generated_sql,
                   'executable': executable, 'execution_match': execution_match,
                   'error_type': error_type, 'error_message': error_message,
                   'selected_tables': link['selected_tables'],
                   'schema_reduction_ratio': link['reduction_ratio'],
                   'fallback_used': link['fallback_used']}
            records.append(rec)
            pred_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
            task_log(f'  B2v1_25 {i:>2} {item["db_id"]:<20} plan_valid={plan_valid} exec={executable} match={execution_match} err={error_type!r}')

            if i < 5:
                plan_example_lines.append(f'## Item {i} (db: {item["db_id"]})\n')
                plan_example_lines.append(f'- **Question:** {item["question"]}\n')
                plan_example_lines.append(f'- **Plan valid:** `{plan_valid}` error={plan_error!r}\n')
                plan_example_lines.append(f'- **Plan parsed:**\n')
                plan_example_lines.append('```json\n' + json.dumps(plan_parsed, ensure_ascii=False, indent=2) + '\n```\n')
                plan_example_lines.append(f'- **Generated SQL:** `{generated_sql}`\n')
                plan_example_lines.append(f'- **Gold SQL:** `{item["query"]}`\n')
                plan_example_lines.append(f'- **execution_match:** {execution_match}\n')

        plan_examples_path.write_text('\n'.join(plan_example_lines) + '\n', encoding='utf-8')

        total = len(records)
        exec_count = sum(1 for r in records if r['executable'])
        match_count = sum(1 for r in records if r['execution_match'])
        ex = match_count / total if total else 0.0
        plan_valid_count = sum(1 for r in records if r['plan_valid'])
        plan_parse_failures = sum(1 for r in records if r['plan_parsed'] is None)
        avg_reduction = sum(r['schema_reduction_ratio'] for r in records) / total if total else 0.0
        fallback_count = sum(1 for r in records if r['fallback_used'])

        metrics_path = OUTPUTS / 'metrics' / 'b2_v1_spider_smoke25_metrics.csv'
        with metrics_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['run_id','model','subset','n','execution_match_count','ex','executable_count','quantization','schema_strategy','planner','plan_valid_count','plan_parse_failures','avg_reduction_ratio','fallback_full_schema_count'])
            w.writeheader(); w.writerow({
                'run_id':'b2_v1_spider_smoke25','model':MODEL_ID,'subset':'smoke_25','n':total,
                'execution_match_count':match_count,'ex':ex,'executable_count':exec_count,
                'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                'planner':'json_plan_v1 + patches',
                'plan_valid_count':plan_valid_count,'plan_parse_failures':plan_parse_failures,
                'avg_reduction_ratio':avg_reduction,'fallback_full_schema_count':fallback_count,
            })
        summary_path = OUTPUTS / 'tables' / 'b2_v1_spider_smoke25_summary.csv'
        with summary_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['metric','value'])
            w.writeheader()
            for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),('total',total),
                        ('model',MODEL_ID),('subset','smoke_25'),
                        ('quantization','4bit_bitsandbytes_config'),
                        ('schema_strategy','lexical_schema_linking'),
                        ('planner','json_plan_v1 + patches'),
                        ('plan_valid_count',plan_valid_count),
                        ('plan_parse_failures',plan_parse_failures),
                        ('avg_reduction_ratio',avg_reduction),
                        ('fallback_full_schema_count',fallback_count)]:
                w.writerow({'metric':k,'value':v})

        runlog_path = OUTPUTS / 'logs' / 'b2_v1_spider_smoke25_runlog.txt'
        runlog_path.write_text(textwrap.dedent(f'''
        b2_v1_spider_smoke25 run log
        checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
        model: {MODEL_ID}
        subset: smoke_25
        total: {total}
        executable_count: {exec_count}
        execution_match_count: {match_count}
        EX: {ex}
        plan_valid_count: {plan_valid_count}
        plan_parse_failures: {plan_parse_failures}
        avg_reduction_ratio: {avg_reduction}
        fallback_full_schema_count: {fallback_count}
        elapsed_seconds: {time.time() - started:.2f}
        ''').strip() + '\n', encoding='utf-8')

        cols = ['idx','question','db_id','plan_valid','generated_sql','executable','execution_match','error_type']
        err_rows = [r for r in records if not r['execution_match']]
        (OUTPUTS / 'tables' / 'b2_v1_spider_smoke25_error_cases.md').write_text(
            '# b2_v1_spider_smoke25 Error Cases\n\n' + md_table(err_rows[:20], cols), encoding='utf-8')
        (OUTPUTS / 'tables' / 'b2_v1_spider_smoke25_examples.md').write_text(
            '# b2_v1_spider_smoke25 Examples\n\n' + md_table(records[:5], cols), encoding='utf-8')

        task_log(f'B2_V1_SMOKE25_DONE EX={ex:.4f} executable={exec_count}/{total} plan_valid={plan_valid_count}/{total}')
        task_log('B2_V1_SMOKE25_BG_DONE')
    except Exception:
        task_log('B2_V1_SMOKE25_BG_FAILED')
        task_log(traceback.format_exc())


B2_V1_SMOKE25_BG_THREAD = threading.Thread(target=background_main, name='b2-v1-smoke25-bg', daemon=True)
B2_V1_SMOKE25_BG_THREAD.start()
print('STARTED=True thread=b2-v1-smoke25-bg')
print(f'TASK_LOG={TASK_LOG}')
