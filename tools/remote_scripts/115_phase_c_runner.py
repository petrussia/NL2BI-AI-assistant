# Phase C runner — full controller (b4_v5: candidates → verifier → repair).
# Cells: Qwen2.5-Coder-7B × b4_v5 × full Spider dev (1034) + full BIRD Mini-Dev (500).
# Reuses v11 B0 anchor + Phase A b1_v5/b2_v5 + Phase B b3_v5 for paired stats.
from __future__ import annotations

import gc, json, os, sys, time, traceback, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from func_timeout import FunctionTimedOut, func_timeout

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
EXT = ROOT / 'external_benchmarks'
SPIDER_DIR = ROOT / 'data' / 'spider'
PRED_DIR = ROOT / 'outputs' / 'predictions'
LOG_DIR = ROOT / 'outputs' / 'logs'
PRED_DIR.mkdir(parents=True, exist_ok=True); LOG_DIR.mkdir(parents=True, exist_ok=True)

TASK_LOG = LOG_DIR / 'phase_c_runner_log.txt'
HEARTBEAT = LOG_DIR / 'phase_c_runner_heartbeat.json'
PLAN_SCHEMA_PATH = ROOT / 'tools' / 'eval_v2' / 'plan_schema_v5.json'
EVAL_DIR = ROOT / 'tools' / 'eval_v2'
sys.path.insert(0, str(EVAL_DIR))

def utcnow(): return datetime.now(timezone.utc).isoformat()
def task_log(msg):
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(f'[{utcnow()}] {msg}\n')

def append_jsonl(p, rec):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')

def already_done_count(p):
    if not p.exists(): return 0
    return sum(1 for _ in p.open(encoding='utf-8'))

def heartbeat(prefix, i, n, rate):
    HEARTBEAT.write_text(json.dumps({
        'prefix':prefix,'i':i,'n':n,'rate_per_min':round(rate,2),
        'updated':utcnow()}, indent=2))


def main():
    task_log('PHASE_C_RUNNER_START')
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        spider_dev = json.loads((SPIDER_DIR/'dev.json').read_text(encoding='utf-8'))
        spider_tables = {t['db_id']: t for t in
                          json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
        bird_full = json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/mini_dev_sqlite.json').read_text(encoding='utf-8'))
        bird_tables = {t['db_id']: t for t in
                        json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_tables.json').read_text(encoding='utf-8'))}
        task_log(f'data: spider_dev={len(spider_dev)} bird_full={len(bird_full)}')

        import schema_ir_v2, dialect_utils_v2
        import baselines_b4_v5
        task_log('v2/v5 modules imported ok')

        spider_db_dir = SPIDER_DIR / 'database'
        bird_db_root = EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_databases'

        spider_irs = {db_id: schema_ir_v2.from_spider_tables_entry(
            entry, sqlite_path=str((spider_db_dir/db_id/f'{db_id}.sqlite'))
                  if (spider_db_dir/db_id/f'{db_id}.sqlite').exists() else None,
            dialect='sqlite', source='spider')
                       for db_id, entry in spider_tables.items()}
        bird_irs = {db_id: schema_ir_v2.from_bird_tables_entry(
            entry, sqlite_path=str((bird_db_root/db_id/f'{db_id}.sqlite'))
                  if (bird_db_root/db_id/f'{db_id}.sqlite').exists() else None,
            description_dir=str((bird_db_root/db_id/'database_description'))
                  if (bird_db_root/db_id/'database_description').is_dir() else None)
                     for db_id, entry in bird_tables.items()}
        task_log(f'IRs built: spider={len(spider_irs)} bird={len(bird_irs)}')

        import evidence_store_v2
        evstore = evidence_store_v2.EvidenceStore()
        evidence_store_v2.load_bird(evstore, bird_full)
        evidence_store_v2.load_spider_from_ir(evstore, spider_irs.values())

        model_id = 'Qwen/Qwen2.5-Coder-7B-Instruct'
        free_gb = torch.cuda.mem_get_info()[0]/(1<<30); total_gb = torch.cuda.mem_get_info()[1]/(1<<30)
        task_log(f'loading {model_id}: gpu_free={free_gb:.2f} GB total={total_gb:.2f} GB')
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map='cuda')
        model.eval()
        task_log(f'LOADED {model_id} in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1<<20)} MB')

        LAST = {'lm_calls':0,'lm_time':0.0,'lm_completion':0}
        def gen(prompt, max_new=256):
            messages = [{'role':'user','content':prompt}]
            try: rendered = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            except Exception: rendered = prompt
            with torch.inference_mode():
                ids = tok(rendered, return_tensors='pt', truncation=True, max_length=8000).to('cuda')
                t0 = time.time()
                out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                     pad_token_id=tok.eos_token_id)
                lat = (time.time()-t0)*1000
                gen_tok = out.shape[1] - ids['input_ids'].shape[1]
                LAST['lm_calls'] += 1; LAST['lm_time'] += lat; LAST['lm_completion'] += int(gen_tok)
                return tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True)

        def make_executor(db_path: str):
            def _ex(sql, timeout_s=8):
                def _run():
                    with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as con:
                        con.text_factory = bytes
                        cur = con.cursor(); cur.execute(sql); return cur.fetchall()
                try:
                    rows = func_timeout(timeout_s, _run)
                    return True, rows, '', ''
                except FunctionTimedOut as exc:
                    return False, None, 'timeout', repr(exc)
                except Exception as exc:
                    return False, None, type(exc).__name__, str(exc)
            return _ex

        def evaluate_spider(item, sql):
            executable, match = False, False; err_t, err_m = '', ''
            try:
                db_id = item['db_id']
                sp = spider_db_dir/db_id/f'{db_id}.sqlite'
                ex = make_executor(str(sp))
                ok_a, rows_a, et_a, em_a = ex(sql)
                if not ok_a:
                    return False, False, et_a, em_a
                executable = True
                ok_g, rows_g, _, _ = ex(item.get('query',''))
                if rows_g is not None:
                    match = sorted(rows_a) == sorted(rows_g)
                    if not match: err_t = 'result_mismatch'
            except Exception as exc:
                err_t, err_m = type(exc).__name__, str(exc)
            return executable, match, err_t, err_m

        def evaluate_bird(item, sql):
            executable, match = False, False; err_t, err_m = '', ''
            try:
                db_id = item['db_id']
                sp = bird_db_root/db_id/f'{db_id}.sqlite'
                ex = make_executor(str(sp))
                ok_a, rows_a, et_a, em_a = ex(sql)
                if not ok_a:
                    return False, False, et_a, em_a
                executable = True
                gold_text = item.get('SQL') or item.get('gold_sql') or item.get('query')
                if gold_text:
                    ok_g, rows_g, _, _ = ex(gold_text)
                    if rows_g is not None:
                        match = sorted(rows_a) == sorted(rows_g)
                        if not match: err_t = 'result_mismatch'
                else:
                    err_t = 'no_gold'
            except Exception as exc:
                err_t, err_m = type(exc).__name__, str(exc)
            return executable, match, err_t, err_m

        def run_cell(bench_kind, items, irs_by_db, prefix):
            preds_path = PRED_DIR/f'{prefix}_predictions.jsonl'
            done = already_done_count(preds_path); n = len(items)
            task_log(f'>>> b4_v5 {bench_kind} ({prefix}): {done}/{n} already done')
            if done >= n: task_log('  SKIP'); return
            t0 = time.time(); processed = 0
            for i, item in enumerate(items):
                if i < done: continue
                db_id = item['db_id']
                ir = irs_by_db.get(db_id)
                if ir is None:
                    rec = {'idx':i,'benchmark':bench_kind,'db_id':db_id,
                           'baseline':'B4_v5','model':model_id,
                           'generated_sql':'','executable':False,'execution_match':False,
                           'error_type':'no_schema_ir','error_message':'',
                           'safe_select':False,'fallback_used':True}
                    append_jsonl(preds_path, rec); continue
                try:
                    LAST['lm_calls']=0; LAST['lm_time']=0.0; LAST['lm_completion']=0
                    per_item_ev = (item.get('evidence') or '').strip() if bench_kind=='bird' else ''
                    # Provide a verifier executor (sandboxed read-only)
                    if bench_kind == 'spider':
                        sp = spider_db_dir/db_id/f'{db_id}.sqlite'
                    else:
                        sp = bird_db_root/db_id/f'{db_id}.sqlite'
                    verifier_ex = make_executor(str(sp)) if sp.exists() else None

                    step = baselines_b4_v5.run_b4v5_step(
                        item['question'], ir, gen=gen, executor=verifier_ex,
                        evidence_store=evstore, per_item_evidence=per_item_ev,
                        plan_schema_path=str(PLAN_SCHEMA_PATH) if PLAN_SCHEMA_PATH.exists() else None,
                    )
                    sql = step['sql']
                    if not step['safe']:
                        executable, match, et, em = False, False, f'unsafe:{step["safe_reason"]}', ''
                    else:
                        if bench_kind == 'spider':
                            executable, match, et, em = evaluate_spider(item, sql)
                        else:
                            executable, match, et, em = evaluate_bird(item, sql)
                    gold_sql = item.get('query') or item.get('SQL') or item.get('sql') or item.get('gold_sql','')
                    audit = step.get('audit', {})
                    rec = {
                        'idx':i,'benchmark':bench_kind,'db_id':db_id,
                        'question':item.get('question',''),'gold_sql':gold_sql,
                        'model':model_id,'baseline':'B4_v5',
                        'generated_sql':sql,'executable':executable,'execution_match':match,
                        'error_type':et,'error_message':em,
                        'latency_ms':round(LAST['lm_time'],2),
                        'completion_tokens':LAST['lm_completion'],
                        'lm_calls':LAST['lm_calls'],
                        'selected_candidate_source':step.get('selected_candidate_source',''),
                        'candidate_count':step.get('candidate_count',0),
                        'consensus_size':step.get('consensus_size',0),
                        'verifier_top_score':step.get('verifier_top_score',0.0),
                        'verifier_top2_margin':step.get('verifier_top2_margin',0.0),
                        'planner_used':step.get('planner_used',False),
                        'plan_valid':step.get('plan_valid',False),
                        'compiler_status':step.get('compiler_status',''),
                        'fallback_used':step.get('fallback_used',False),
                        'fallback_reason':step.get('fallback_reason',''),
                        'repair_used':step.get('repair_used',False),
                        'repair_rounds':step.get('repair_rounds',0),
                        'difficulty':audit.get('difficulty',{}).get('difficulty',''),
                        'difficulty_score':audit.get('difficulty',{}).get('score',0.0),
                        'candidate_breakdown':audit.get('candidates',[]),
                        'rationale':audit.get('rationale',[]),
                        'safe_select':step.get('safe',False),
                    }
                    append_jsonl(preds_path, rec); processed += 1
                    if (i+1) % 10 == 0:
                        rate = processed / max(0.001,(time.time()-t0)/60)
                        eta = (n-(i+1))/max(0.001,rate)
                        task_log(f'  b4_v5 {i+1}/{n} db={db_id[:18]:18s} src={step.get("selected_candidate_source","")[:24]:24s} '
                                 f'cand={step.get("candidate_count",0)} cons={step.get("consensus_size",0)} '
                                 f'exec={executable} match={match} lm={LAST["lm_calls"]}× '
                                 f'(~{rate:.1f}/min, eta~{eta:.1f}m)')
                        heartbeat(prefix, i+1, n, rate)
                except Exception as exc:
                    task_log(f'  EXC at {i}: {exc}\n{traceback.format_exc()[-400:]}')
                    rec = {'idx':i,'benchmark':bench_kind,'db_id':db_id,
                           'baseline':'B4_v5','model':model_id,
                           'generated_sql':'','executable':False,'execution_match':False,
                           'error_type':f'pipeline_exception:{type(exc).__name__}',
                           'error_message':str(exc)[:300],'safe_select':False}
                    append_jsonl(preds_path, rec)
            elapsed = time.time()-t0
            rows = [json.loads(l) for l in preds_path.open(encoding='utf-8')]
            ex = sum(1 for r in rows if r.get('execution_match'))
            from collections import Counter
            src_cnt = Counter(r.get('selected_candidate_source','?') for r in rows)
            task_log(f'  {prefix} DONE: EX={ex/len(rows):.4f} ({ex}/{len(rows)}) sources={dict(src_cnt)} elapsed={elapsed:.0f}s')

        cells = [
            ('spider', spider_dev, spider_irs, 'b4v5_qwen2p5_coder_7b_spider_dev_full'),
            ('bird',   bird_full,   bird_irs,   'b4v5_qwen2p5_coder_7b_bird_full'),
        ]
        for k, (bk, items, irs, prefix) in enumerate(cells, 1):
            task_log(f'>>> CELL [{k}/{len(cells)}] bench={bk} prefix={prefix}')
            run_cell(bk, items, irs, prefix)
        task_log('PHASE_C_RUNNER_DONE')
    except Exception as exc:
        task_log('PHASE_C_RUNNER_FAILED')
        task_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
