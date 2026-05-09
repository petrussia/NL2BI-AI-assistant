# Stages 3+4 (b): unified BG inference for B3 + B4 on smoke10.

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
TASK_LOG = OUTPUTS / 'logs' / 'b3_b4_smoke10_bg_task_log.txt'

eval_path = str(REPO / 'src' / 'evaluation')
if eval_path not in sys.path:
    sys.path.insert(0, eval_path)
for mod in ('baselines_b2_v1','baselines_b3','baselines_b4'):
    if mod in sys.modules: del sys.modules[mod]
import baselines_b2_v1 as b2v1
import baselines_b3 as b3mod
import baselines_b4 as b4mod

mm = sys.modules['__main__']
def _from_main(name): return getattr(mm, name, None) or globals().get(name)

model = _from_main('model'); tokenizer = _from_main('tokenizer')
tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
lexical_schema_linking = _from_main('lexical_schema_linking')
build_reduced_schema_context = _from_main('build_reduced_schema_context')
extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')
func_timeout = _from_main('func_timeout'); FunctionTimedOut = _from_main('FunctionTimedOut')

assert model is not None and tokenizer is not None

if 'B3_B4_BG_THREAD' in globals() and B3_B4_BG_THREAD.is_alive():
    print('BG already running')
    raise SystemExit(0)


def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def gen(prompt, max_new=192, num_return_sequences=1, do_sample=False, temperature=1.0, top_p=1.0):
    import torch
    messages = [{'role':'user','content':prompt}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(rendered, return_tensors='pt')
    inputs = {k: v.to(model.device) for k,v in inputs.items()}
    kwargs = dict(max_new_tokens=max_new, pad_token_id=tokenizer.eos_token_id)
    if do_sample:
        kwargs.update(do_sample=True, temperature=temperature, top_p=top_p, num_return_sequences=num_return_sequences)
    else:
        kwargs.update(do_sample=False)
    with torch.no_grad():
        out = model.generate(**inputs, **kwargs)
    n_in = inputs['input_ids'].shape[1]
    return [tokenizer.decode(seq[n_in:], skip_special_tokens=True) for seq in out]


def evaluate_one(item, generated_sql):
    gold_sql = item['query']
    executable, execution_match = False, False
    error_type, error_message = '', ''
    pred_rows = None
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
    return executable, execution_match, error_type, error_message, pred_rows


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
    err_rows = [r for r in records if not r['execution_match']]
    errors_path.write_text(f'# {prefix} Error Cases\n\n' + md_table(err_rows[:25], cols), encoding='utf-8')
    examples_path.write_text(f'# {prefix} Examples\n\n' + md_table(records[:5], cols), encoding='utf-8')
    return base


def background_main():
    try:
        TASK_LOG.write_text('', encoding='utf-8')
        task_log('B3_B4_BG_START')
        smoke10 = json.loads((SPIDER_DIR/'subsets'/'smoke_10.json').read_text(encoding='utf-8'))
        plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
        task_log(f'smoke10 N={len(smoke10)}')

        # ===== B3 smoke10 =====
        task_log('=== B3 smoke10 ===')
        b3_records = []; t0 = time.time()
        b3_retr_audit = []
        b3_retr_examples = []
        for i, item in enumerate(smoke10):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            tobj = tables_map[item['db_id']]
            kindex = b3mod.build_knowledge_index(item['db_id'], tobj)
            know_top = b3mod.retrieve_knowledge(item['question'], kindex, top_k=3)
            b3_ctx = b3mod.build_b3_context(item['db_id'], link, tobj, top_k_knowledge=3)
            b3_retr_audit.append({
                'idx': i, 'db_id': item['db_id'],
                'schema_selected_tables': link['selected_tables'],
                'schema_reduction_ratio': link['reduction_ratio'],
                'knowledge_top3': [(ti, score) for ti, _, score in know_top],
            })
            if i < 5:
                b3_retr_examples.append((item, b3_ctx, link, know_top))

            plan_raw = ''; plan_parsed = None; plan_valid = False; plan_error = ''
            try:
                pp = b3mod.make_b3_plan_prompt(item['question'], b3_ctx)
                plan_raw = gen(pp, max_new=320)[0]
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'

            generated_raw = ''; generated_sql = ''
            executable = False; execution_match = False
            error_type = ''; error_message = ''
            if plan_valid:
                try:
                    sp = b3mod.make_b3_sql_prompt(item['question'], plan_parsed, b3_ctx)
                    generated_raw = gen(sp, max_new=192)[0]
                    generated_sql = extract_sql(generated_raw)
                    executable, execution_match, error_type, error_message, _ = evaluate_one(item, generated_sql)
                except Exception as exc:
                    error_type, error_message = 'sql_gen_failed', f'{type(exc).__name__}: {exc}'
            else:
                error_type = 'plan_invalid'; error_message = plan_error

            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_raw':generated_raw,'generated_sql':generated_sql,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio'],
                   'knowledge_top3_table_idx':[ti for ti,_,_ in know_top]}
            b3_records.append(rec)
            (OUTPUTS/'predictions'/'b3_spider_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in b3_records), encoding='utf-8')
            task_log(f'  B3 {i:>2} {item["db_id"]:<20} plan_valid={plan_valid} exec={executable} match={execution_match} err={error_type!r}')

        # B3 retrieval audit
        b3_audit_md = ['# B3 Retrieval Audit (smoke10)\n', '',
                       'PROXY DOCS — synthetic per-table descriptions derived from schema metadata. Not real enterprise documentation.',
                       '',
                       '| idx | db_id | schema_selected | reduction | knowledge_top3 (table_idx, score) |',
                       '|---|---|---|---|---|']
        for a in b3_retr_audit:
            b3_audit_md.append(f"| {a['idx']} | `{a['db_id']}` | {a['schema_selected_tables']} | {a['schema_reduction_ratio']:.2f} | {a['knowledge_top3']} |")
        (OUTPUTS/'logs'/'b3_retrieval_audit.md').write_text('\n'.join(b3_audit_md) + '\n', encoding='utf-8')

        # B3 retrieval examples (for top 5)
        ex_md = ['# B3 Retrieval Examples (smoke10, first 5)\n']
        for item, ctx, link, know_top in b3_retr_examples:
            ex_md.append(f"## Item idx={item.get('idx', '?')} db={item['db_id']}\n")
            ex_md.append(f"- **Question:** {item['question']}\n")
            ex_md.append(f"- **Schema-selected tables:** {link['selected_tables']}\n")
            ex_md.append(f"- **Knowledge top-3 (table_idx, score):** {[(ti,s) for ti,_,s in know_top]}\n")
            ex_md.append(f"- **Full B3 context (proxy + schema):**\n")
            ex_md.append(f'```\n{ctx[:1500]}\n```\n')
        (OUTPUTS/'tables'/'b3_retrieval_examples.md').write_text('\n'.join(ex_md), encoding='utf-8')

        b3_summary = write_run('b3_spider_smoke10', 'smoke_10', b3_records, t0,
                               {'quantization':'4bit_bitsandbytes_config',
                                'schema_strategy':'lexical_schema_linking+knowledge_proxy_dual_retrieval',
                                'planner':'json_plan_v1 + patches',
                                'plan_valid_count':sum(1 for r in b3_records if r['plan_valid']),
                                'plan_parse_failures':sum(1 for r in b3_records if r['plan_parsed'] is None),
                                'avg_reduction_ratio':sum(r['schema_reduction_ratio'] for r in b3_records)/len(b3_records)})
        task_log(f'B3_smoke10_DONE EX={b3_summary["ex"]:.4f}')

        # ===== B4 smoke10 =====
        task_log('=== B4 smoke10 ===')
        b4_records = []; t0 = time.time()
        b4_select_examples = []
        repaired_count = 0
        rejected_unsafe_total = 0
        for i, item in enumerate(smoke10):
            link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
            tobj = tables_map[item['db_id']]
            b3_ctx = b3mod.build_b3_context(item['db_id'], link, tobj, top_k_knowledge=3)

            plan_raw = ''; plan_parsed = None; plan_valid = False; plan_error = ''
            try:
                pp = b3mod.make_b3_plan_prompt(item['question'], b3_ctx)
                plan_raw = gen(pp, max_new=320)[0]
                plan_parsed, plan_valid, plan_error = b2v1.parse_and_validate_plan(plan_raw, plan_schema_v1)
            except Exception as exc:
                plan_error = f'planner_failed: {type(exc).__name__}: {exc}'

            cand_results = []     # list of (sql, executable, rows, error_type)
            cand_safe_flags = []  # list of (sql, ok, reason)
            generated_sql = ''
            executable = False; execution_match = False
            error_type = ''; error_message = ''
            repaired = False
            selection_reason = ''

            if plan_valid:
                try:
                    sp = b3mod.make_b3_sql_prompt(item['question'], plan_parsed, b3_ctx)
                    raw_candidates = gen(sp, max_new=192, num_return_sequences=3, do_sample=True, temperature=0.7, top_p=0.95)
                    parsed_candidates = [extract_sql(r) for r in raw_candidates]

                    safe_candidates = []
                    for sql in parsed_candidates:
                        ok, reason = b4mod.is_safe_select(sql)
                        cand_safe_flags.append({'sql': sql[:200], 'ok': ok, 'reason': reason})
                        if not ok:
                            rejected_unsafe_total += 1
                            continue
                        safe_candidates.append(sql)

                    for sql in safe_candidates:
                        ex_, em_, et_, emsg_, rows = evaluate_one(item, sql)
                        cand_results.append((sql, ex_, rows or [], et_))

                    chosen, selection_reason = b4mod.consistency_pick(cand_results)
                    generated_sql = chosen or ''

                    if not any(ex_ for _, ex_, _, _ in cand_results):
                        # bounded repair (1 retry)
                        if cand_results:
                            prev_sql = cand_results[0][0]
                            err = cand_results[0][3] or 'no_executable_candidate'
                        else:
                            prev_sql = (parsed_candidates[0] if parsed_candidates else '')
                            err = 'all_candidates_unsafe'
                        repair_prompt = b4mod.make_repair_prompt(item['question'], plan_parsed, b3_ctx, prev_sql, err)
                        repair_raw = gen(repair_prompt, max_new=192, num_return_sequences=1, do_sample=False)[0]
                        repair_sql = extract_sql(repair_raw)
                        ok, reason = b4mod.is_safe_select(repair_sql)
                        if ok:
                            ex_, em_, et_, emsg_, _ = evaluate_one(item, repair_sql)
                            if ex_:
                                generated_sql = repair_sql; executable = True; execution_match = em_
                                error_type = et_ if not em_ else ''
                                error_message = emsg_
                                repaired = True
                                selection_reason = 'repair_succeeded'
                                repaired_count += 1
                            else:
                                executable = False; execution_match = False
                                error_type = 'no_executable_after_repair'
                                error_message = emsg_
                        else:
                            executable = False
                            error_type = f'repair_unsafe:{reason}'
                            error_message = ''
                    else:
                        # one of the original candidates is executable; selection picked one
                        ex_, em_, et_, emsg_, _ = evaluate_one(item, generated_sql)
                        executable = ex_; execution_match = em_
                        error_type = et_; error_message = emsg_
                except Exception as exc:
                    error_type = 'sql_gen_failed'
                    error_message = f'{type(exc).__name__}: {exc}'
            else:
                error_type = 'plan_invalid'; error_message = plan_error

            if i < 5:
                b4_select_examples.append({'idx': i, 'db_id': item['db_id'], 'question': item['question'],
                                           'cand_safe_flags': cand_safe_flags,
                                           'cand_results': [{'sql': s[:200], 'executable': ex_, 'error_type': et_}
                                                            for s, ex_, _, et_ in cand_results],
                                           'chosen_sql': generated_sql[:200],
                                           'selection_reason': selection_reason,
                                           'repaired': repaired})

            rec = {'idx':i,'question':item['question'],'db_id':item['db_id'],
                   'gold_sql':item['query'],
                   'plan_raw':plan_raw,'plan_parsed':plan_parsed,'plan_valid':plan_valid,'plan_error':plan_error,
                   'generated_sql':generated_sql,
                   'cand_safe_flags':cand_safe_flags,
                   'cand_results':[{'sql':s[:200],'executable':ex_,'error_type':et_} for s,ex_,_,et_ in cand_results],
                   'selection_reason':selection_reason,
                   'repaired':repaired,
                   'executable':executable,'execution_match':execution_match,
                   'error_type':error_type,'error_message':error_message,
                   'selected_tables':link['selected_tables'],
                   'schema_reduction_ratio':link['reduction_ratio']}
            b4_records.append(rec)
            (OUTPUTS/'predictions'/'b4_spider_smoke10_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in b4_records), encoding='utf-8')
            task_log(f'  B4 {i:>2} {item["db_id"]:<20} plan_valid={plan_valid} cand={len(cand_results)} chosen={selection_reason!r} exec={executable} match={execution_match} err={error_type!r}')

        # B4 candidate-selection examples
        sel_md = ['# B4 Candidate Selection Examples (smoke10, first 5)\n']
        for ex in b4_select_examples:
            sel_md.append(f"## idx={ex['idx']} db={ex['db_id']}\n")
            sel_md.append(f"- Question: {ex['question']}\n")
            sel_md.append(f"- Candidate safety flags:")
            for cs in ex['cand_safe_flags']:
                sel_md.append(f"  - ok={cs['ok']} reason={cs['reason']!r} sql=`{cs['sql']}`")
            sel_md.append(f"- Candidate execution results:")
            for cr in ex['cand_results']:
                sel_md.append(f"  - executable={cr['executable']} error_type={cr['error_type']!r} sql=`{cr['sql']}`")
            sel_md.append(f"- Chosen: `{ex['chosen_sql']}`")
            sel_md.append(f"- Selection reason: `{ex['selection_reason']}`")
            sel_md.append(f"- Repaired: `{ex['repaired']}`")
            sel_md.append('')
        (OUTPUTS/'tables'/'b4_candidate_selection_examples.md').write_text('\n'.join(sel_md), encoding='utf-8')

        b4_summary = write_run('b4_spider_smoke10', 'smoke_10', b4_records, t0,
                               {'quantization':'4bit_bitsandbytes_config',
                                'schema_strategy':'B3_dual_retrieval',
                                'planner':'json_plan_v1 + patches',
                                'plan_valid_count':sum(1 for r in b4_records if r['plan_valid']),
                                'plan_parse_failures':sum(1 for r in b4_records if r['plan_parsed'] is None),
                                'multi_candidate':3, 'repair_max':1,
                                'repaired_count':repaired_count,
                                'rejected_unsafe_total':rejected_unsafe_total,
                                'avg_reduction_ratio':sum(r['schema_reduction_ratio'] for r in b4_records)/len(b4_records)})
        task_log(f'B4_smoke10_DONE EX={b4_summary["ex"]:.4f} repaired={repaired_count} rejected_unsafe={rejected_unsafe_total}')

        task_log('B3_B4_BG_DONE')
    except Exception:
        task_log('B3_B4_BG_FAILED')
        task_log(traceback.format_exc())


B3_B4_BG_THREAD = threading.Thread(target=background_main, name='b3-b4-smoke10-bg', daemon=True)
B3_B4_BG_THREAD.start()
print('STARTED=True thread=b3-b4-smoke10-bg')
print(f'TASK_LOG={TASK_LOG}')
