# Stages 5-6: run all five baselines (B0, B1, B2_v1, B1R, B2R) on multidb_30
# in a single BG thread. Saves per-baseline artefacts. Marker BG_DONE at end.

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
TASK_LOG = OUTPUTS / 'logs' / 'multidb30_all_bg_task_log.txt'

eval_path = str(REPO / 'src' / 'evaluation')
if eval_path not in sys.path:
    sys.path.insert(0, eval_path)
for mod in list(sys.modules):
    if mod in ('baselines_b2_v1', 'baselines_b1r', 'baselines_b2r', 'retrieval'):
        del sys.modules[mod]
import baselines_b2_v1 as b2v1
import baselines_b1r as b1r_mod
import retrieval as retr_mod

mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None) or globals().get(name)

model = _from_main('model'); tokenizer = _from_main('tokenizer')
tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
build_full_schema_prompt_context = _from_main('build_full_schema_prompt_context')
make_prompt = _from_main('make_prompt')           # B0 prompt
make_b1_prompt = _from_main('make_b1_prompt')     # B1 prompt
lexical_schema_linking = _from_main('lexical_schema_linking')
build_reduced_schema_context = _from_main('build_reduced_schema_context')
extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')
func_timeout = _from_main('func_timeout'); FunctionTimedOut = _from_main('FunctionTimedOut')

assert model is not None and tokenizer is not None

if 'MULTIDB30_BG_THREAD' in globals() and MULTIDB30_BG_THREAD.is_alive():
    print(f'BG already running thread={MULTIDB30_BG_THREAD.name}')
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


def evaluate(item, generated_sql, db_for_pred=None):
    """Evaluate predicted SQL. db_for_pred lets B1R/B2R execute against retrieved DB."""
    gold_sql = item['query']
    gold_db = item['db_id']
    pred_db = db_for_pred or gold_db
    executable, execution_match = False, False
    error_type, error_message = '', ''
    try:
        pred_rows = execute_sql(db_paths[pred_db], generated_sql)
        executable = True
        gold_rows = execute_sql(db_paths[gold_db], gold_sql)
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


def write_run(prefix, subset, records, started, extra_kvs):
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
    base = {'run_id': prefix, 'model': MODEL_ID, 'subset': subset, 'n': total,
            'execution_match_count': match_count, 'ex': ex, 'executable_count': exec_count}
    base.update(extra_kvs)
    with metrics_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(base.keys()))
        w.writeheader(); w.writerow(base)
    with summary_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['metric','value'])
        w.writeheader()
        for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),('total',total),
                    ('model',MODEL_ID),('subset',subset)] + list(extra_kvs.items()):
            w.writerow({'metric':k,'value':v})
    runlog_path.write_text(textwrap.dedent(f'''
    {prefix} run log
    checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
    model: {MODEL_ID}
    subset: {subset}
    total: {total}
    executable_count: {exec_count}
    execution_match_count: {match_count}
    EX: {ex}
    elapsed_seconds: {time.time() - started:.2f}
    extra: {json.dumps(extra_kvs, ensure_ascii=False)}
    ''').strip() + '\n', encoding='utf-8')
    cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type']
    if any('plan_valid' in r for r in records):
        cols.insert(3, 'plan_valid')
    if any('retrieved_db_id' in r for r in records):
        cols.insert(3, 'retrieved_db_id')
    err_rows = [r for r in records if not r['execution_match']]
    errors_path.write_text(f'# {prefix} Error Cases\n\n' + md_table(err_rows[:25], cols), encoding='utf-8')
    examples_path.write_text(f'# {prefix} Examples\n\n' + md_table(records[:5], cols), encoding='utf-8')
    return base


def background_main():
    try:
        TASK_LOG.write_text('', encoding='utf-8')
        task_log('MULTIDB30_BG_START')
        items = json.loads((SPIDER_DIR/'subsets'/'multidb_30.json').read_text(encoding='utf-8'))
        plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
        task_log(f'multidb_30 N={len(items)}')

        # Build B1R retrieval audit table once for ALL items (used by both B1R and B2R)
        retrieval_records = []
        for i, item in enumerate(items):
            top3, qt = retr_mod.retrieve_db(item['question'], tables_map, top_k=3)
            top1 = top3[0]
            hit = (top1['db_id'] == item['db_id'])
            retrieval_records.append({
                'idx': i, 'gold_db_id': item['db_id'], 'retrieved_db_id': top1['db_id'],
                'retrieved_score': top1['score'], 'hit': hit,
                'top3': [(t['db_id'], t['score']) for t in top3],
                'q_tokens': sorted(qt),
            })
            task_log(f'  retr {i:>2} gold={item["db_id"]:<25} retrieved={top1["db_id"]:<25} score={top1["score"]} hit={hit}')

        retr_audit_md = ['# B1R/B2R Retrieval Audit (multidb_30)\n', '',
                         f'Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}',
                         f'Subset: multidb_30 (n={len(items)})',
                         f'Top-1 retrieval hit rate: {sum(1 for r in retrieval_records if r["hit"])}/{len(items)}',
                         '',
                         '| idx | gold_db_id | retrieved_db_id | score | hit | top3 |',
                         '|---|---|---|---|---|---|']
        for r in retrieval_records:
            top3_str = ', '.join(f"{db}({s})" for db,s in r['top3'])
            retr_audit_md.append(f"| {r['idx']} | `{r['gold_db_id']}` | `{r['retrieved_db_id']}` | {r['retrieved_score']} | {r['hit']} | {top3_str} |")
        (OUTPUTS / 'logs' / 'b1r_multidb30_retrieval_audit.md').write_text('\n'.join(retr_audit_md) + '\n', encoding='utf-8')
        # B2R uses the same retrieval result; copy to its own audit file
        (OUTPUTS / 'logs' / 'b2r_multidb30_retrieval_audit.md').write_text('\n'.join(retr_audit_md) + '\n', encoding='utf-8')

        # ============ Baseline B0 multidb_30 ============
        task_log('=== B0 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            try:
                prompt = make_prompt(item)
                raw = gen(prompt, max_new=192)
                sql = extract_sql(raw)
                executable, execution_match, error_type, error_message = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                executable, execution_match = False, False
                error_type, error_message = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],'generated_raw':raw,'generated_sql':sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message}
            recs.append(rec)
            (OUTPUTS / 'predictions' / 'b0_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"]:<25} exec={executable} match={execution_match} err={error_type!r}')
        b0_summary = write_run('b0_multidb30', 'multidb_30', recs, t0,
                               {'quantization':'4bit_bitsandbytes_config','schema_strategy':'full_schema'})
        task_log(f'B0_multidb30_DONE EX={b0_summary["ex"]:.4f}')

        # ============ Baseline B1 multidb_30 ============
        task_log('=== B1 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            try:
                prompt = make_b1_prompt(item, link)
                raw = gen(prompt, max_new=192)
                sql = extract_sql(raw)
                executable, execution_match, error_type, error_message = evaluate(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                executable, execution_match = False, False
                error_type, error_message = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],'generated_raw':raw,'generated_sql':sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'fallback_used':link['fallback_used']}
            recs.append(rec)
            (OUTPUTS / 'predictions' / 'b1_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
            task_log(f'  B1 {i:>2} {item["db_id"]:<25} sel={len(link["selected_tables"])} exec={executable} match={execution_match} err={error_type!r}')
        avg_red = sum(r['schema_reduction_ratio'] for r in recs) / len(recs) if recs else 0.0
        b1_summary = write_run('b1_multidb30', 'multidb_30', recs, t0,
                               {'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                                'avg_reduction_ratio': avg_red})
        task_log(f'B1_multidb30_DONE EX={b1_summary["ex"]:.4f}')

        # ============ Baseline B2_v1 multidb_30 ============
        task_log('=== B2_v1 multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            reduced_ctx = build_reduced_schema_context(item['db_id'], link['selected_table_indexes'], tables_map)
            plan_raw = ''; plan_parsed = None; plan_valid = False; plan_error = ''
            try:
                plan_prompt = b2v1.make_plan_prompt(item['question'], reduced_ctx)
                plan_raw = gen(plan_prompt, max_new=320)
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'
            generated_raw = ''; generated_sql = ''
            executable = False; execution_match = False
            error_type = ''; error_message = ''
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
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'fallback_used':link['fallback_used']}
            recs.append(rec)
            (OUTPUTS / 'predictions' / 'b2_v1_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
            task_log(f'  B2v1 {i:>2} {item["db_id"]:<25} plan_valid={plan_valid} exec={executable} match={execution_match} err={error_type!r}')
        avg_red = sum(r['schema_reduction_ratio'] for r in recs) / len(recs) if recs else 0.0
        plan_valid_count = sum(1 for r in recs if r['plan_valid'])
        plan_parse_failures = sum(1 for r in recs if r['plan_parsed'] is None)
        b2v1_summary = write_run('b2_v1_multidb30', 'multidb_30', recs, t0,
                                 {'quantization':'4bit_bitsandbytes_config','schema_strategy':'lexical_schema_linking',
                                  'planner':'json_plan_v1 + patches',
                                  'plan_valid_count':plan_valid_count,'plan_parse_failures':plan_parse_failures,
                                  'avg_reduction_ratio':avg_red})
        task_log(f'B2_V1_multidb30_DONE EX={b2v1_summary["ex"]:.4f} plan_valid={plan_valid_count}/{len(recs)}')

        # ============ Baseline B1R multidb_30 ============
        task_log('=== B1R multidb_30 ===')
        recs = []; t0 = time.time()
        for i, item in enumerate(items):
            r_audit = retrieval_records[i]
            retrieved_db = r_audit['retrieved_db_id']
            # Schema linking *within* retrieved DB
            link = lexical_schema_linking(item['question'], retrieved_db, tables_map)
            reduced_ctx = build_reduced_schema_context(retrieved_db, link['selected_table_indexes'], tables_map)
            try:
                prompt = b1r_mod.make_b1r_prompt(item['question'], reduced_ctx)
                raw = gen(prompt, max_new=192)
                sql = extract_sql(raw)
                executable, execution_match, error_type, error_message = evaluate(item, sql, db_for_pred=retrieved_db)
            except Exception as exc:
                raw, sql = '', ''
                executable, execution_match = False, False
                error_type, error_message = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'retrieved_db_id':retrieved_db,'retrieval_hit':r_audit['hit'],
                   'retrieval_score':r_audit['retrieved_score'],
                   'gold_sql':item['query'],'generated_raw':raw,'generated_sql':sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'fallback_used':link['fallback_used']}
            recs.append(rec)
            (OUTPUTS / 'predictions' / 'b1r_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
            task_log(f'  B1R {i:>2} gold={item["db_id"]:<25} retrieved={retrieved_db:<25} hit={r_audit["hit"]} exec={executable} match={execution_match} err={error_type!r}')
        avg_red = sum(r['schema_reduction_ratio'] for r in recs) / len(recs) if recs else 0.0
        retr_hits = sum(1 for r in recs if r['retrieval_hit'])
        b1r_summary = write_run('b1r_multidb30', 'multidb_30', recs, t0,
                                {'quantization':'4bit_bitsandbytes_config','schema_strategy':'cross_db_lexical_retrieval+lexical_schema_linking',
                                 'retrieval_hit_count':retr_hits,
                                 'avg_reduction_ratio':avg_red})
        task_log(f'B1R_multidb30_DONE EX={b1r_summary["ex"]:.4f} retrieval_hit={retr_hits}/{len(recs)}')

        # ============ Baseline B2R multidb_30 ============
        task_log('=== B2R multidb_30 ===')
        recs = []; t0 = time.time()
        plan_examples_path = OUTPUTS / 'tables' / 'b2r_plan_examples_multidb30.md'
        plan_example_lines = ['# B2R Plan Examples (multidb_30)\n']
        for i, item in enumerate(items):
            r_audit = retrieval_records[i]
            retrieved_db = r_audit['retrieved_db_id']
            link = lexical_schema_linking(item['question'], retrieved_db, tables_map)
            reduced_ctx = build_reduced_schema_context(retrieved_db, link['selected_table_indexes'], tables_map)
            plan_raw = ''; plan_parsed = None; plan_valid = False; plan_error = ''
            try:
                plan_prompt = b2v1.make_plan_prompt(item['question'], reduced_ctx)
                plan_raw = gen(plan_prompt, max_new=320)
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'
            generated_raw = ''; generated_sql = ''
            executable = False; execution_match = False
            error_type = ''; error_message = ''
            if plan_valid:
                try:
                    sql_prompt = b2v1.make_plan_to_sql_prompt(item['question'], plan_parsed, reduced_ctx)
                    generated_raw = gen(sql_prompt, max_new=192)
                    generated_sql = extract_sql(generated_raw)
                    executable, execution_match, error_type, error_message = evaluate(item, generated_sql, db_for_pred=retrieved_db)
                except Exception as exc:
                    error_type, error_message = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                error_type = 'plan_invalid'
                error_message = plan_error
            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'retrieved_db_id':retrieved_db,'retrieval_hit':r_audit['hit'],
                   'retrieval_score':r_audit['retrieved_score'],
                   'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'fallback_used':link['fallback_used']}
            recs.append(rec)
            (OUTPUTS / 'predictions' / 'b2r_multidb30_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
            task_log(f'  B2R {i:>2} gold={item["db_id"]:<25} retrieved={retrieved_db:<25} hit={r_audit["hit"]} plan_valid={plan_valid} exec={executable} match={execution_match} err={error_type!r}')
            if i < 5:
                plan_example_lines.append(f'## Item {i} (gold db: {item["db_id"]}, retrieved: {retrieved_db})\n')
                plan_example_lines.append(f'- **Question:** {item["question"]}\n')
                plan_example_lines.append(f'- **Plan valid:** `{plan_valid}` error={plan_error!r}\n')
                plan_example_lines.append('```json\n' + json.dumps(plan_parsed, ensure_ascii=False, indent=2) + '\n```\n')
                plan_example_lines.append(f'- **Generated SQL:** `{generated_sql}`\n')
                plan_example_lines.append(f'- **Gold SQL:** `{item["query"]}`\n')
                plan_example_lines.append(f'- **execution_match:** {execution_match}\n')
        plan_examples_path.write_text('\n'.join(plan_example_lines) + '\n', encoding='utf-8')
        avg_red = sum(r['schema_reduction_ratio'] for r in recs) / len(recs) if recs else 0.0
        plan_valid_count = sum(1 for r in recs if r['plan_valid'])
        plan_parse_failures = sum(1 for r in recs if r['plan_parsed'] is None)
        retr_hits = sum(1 for r in recs if r['retrieval_hit'])
        b2r_summary = write_run('b2r_multidb30', 'multidb_30', recs, t0,
                                {'quantization':'4bit_bitsandbytes_config',
                                 'schema_strategy':'cross_db_lexical_retrieval+lexical_schema_linking',
                                 'planner':'json_plan_v1 + patches',
                                 'plan_valid_count':plan_valid_count,
                                 'plan_parse_failures':plan_parse_failures,
                                 'retrieval_hit_count':retr_hits,
                                 'avg_reduction_ratio':avg_red})
        task_log(f'B2R_multidb30_DONE EX={b2r_summary["ex"]:.4f} retrieval_hit={retr_hits}/{len(recs)} plan_valid={plan_valid_count}/{len(recs)}')

        task_log('MULTIDB30_BG_DONE')
    except Exception:
        task_log('MULTIDB30_BG_FAILED')
        task_log(traceback.format_exc())


MULTIDB30_BG_THREAD = threading.Thread(target=background_main, name='multidb30-all-bg', daemon=True)
MULTIDB30_BG_THREAD.start()
print('STARTED=True thread=multidb30-all-bg')
print(f'TASK_LOG={TASK_LOG}')
