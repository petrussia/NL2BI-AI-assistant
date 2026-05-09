# Phase 8 (S1_v7) runner — DAIL-style demo retrieval over B6_v7 controller.
# FULL Spider dev only (DAIL is Spider-targeted). Indexes ~8659 train examples
# (train_spider.json + train_others.json) and retrieves top-3 same-db demos
# per dev question (BM25 + structural-feature jaccard + +0.5 same-db boost).
#
# Compute: same as B6_v7 Spider (rate ~6/min) plus slightly larger anchor
# prompt; expect ~6/min and ~3h on FULL 1034.
from __future__ import annotations

import gc, json, os, sys, time, traceback, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from func_timeout import FunctionTimedOut, func_timeout

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = ROOT / 'data' / 'spider'
PRED_DIR = ROOT / 'outputs' / 'predictions'
LOG_DIR = ROOT / 'outputs' / 'logs'
PRED_DIR.mkdir(parents=True, exist_ok=True); LOG_DIR.mkdir(parents=True, exist_ok=True)

TASK_LOG = LOG_DIR / 'phase_eight_s1v7_runner_log.txt'
HEARTBEAT = LOG_DIR / 'phase_eight_s1v7_runner_heartbeat.json'
PLAN_SCHEMA_PATH = ROOT / 'tools' / 'eval_v2' / 'plan_schema_v5.json'
EVAL_DIR = ROOT / 'tools' / 'eval_v2'
sys.path.insert(0, str(EVAL_DIR))

CODER_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'

def utcnow(): return datetime.now(timezone.utc).isoformat()
def task_log(msg):
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(f'[{utcnow()}] {msg}\n')

def append_jsonl(p, rec):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')

def already_done_count(p):
    return sum(1 for _ in p.open(encoding='utf-8')) if p.exists() else 0

def heartbeat(prefix, i, n, rate):
    HEARTBEAT.write_text(json.dumps({
        'prefix':prefix,'i':i,'n':n,'rate_per_min':round(rate,2),
        'updated':utcnow()}, indent=2))


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


def main():
    task_log('PHASE_EIGHT_S1V7_RUNNER_START')
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        spider_dev = json.loads((SPIDER_DIR/'dev.json').read_text(encoding='utf-8'))
        spider_tables = {t['db_id']: t for t in
                          json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
        # Train pool: train_spider.json (7000) + train_others.json (1659)
        train_spider = json.loads((SPIDER_DIR/'train_spider.json').read_text(encoding='utf-8'))
        train_others = json.loads((SPIDER_DIR/'train_others.json').read_text(encoding='utf-8'))
        train_all = train_spider + train_others
        task_log(f'data: spider_dev={len(spider_dev)} train_pool={len(train_all)} '
                 f'(train_spider={len(train_spider)} train_others={len(train_others)})')

        import schema_ir_v2, evidence_store_v2
        import baselines_s1_v7
        import demo_retrieval_v7 as dr
        task_log('v2/v5/v7 modules imported ok')

        spider_db_dir = SPIDER_DIR / 'database'
        spider_irs = {db_id: schema_ir_v2.from_spider_tables_entry(
            entry, sqlite_path=str((spider_db_dir/db_id/f'{db_id}.sqlite'))
                  if (spider_db_dir/db_id/f'{db_id}.sqlite').exists() else None,
            dialect='sqlite', source='spider')
                       for db_id, entry in spider_tables.items()}
        task_log(f'IRs built spider={len(spider_irs)}')

        # Build demo retriever
        t0 = time.time()
        demo_retriever = dr.DemoRetriever(train_all)
        task_log(f'demo_retriever built in {time.time()-t0:.1f}s; '
                 f'global_corpus={len(demo_retriever._items)} dbs={len(demo_retriever._by_db)}')

        # Spider has no per-item evidence; evstore needed for evidence_store-driven C2 retrieval anyway
        evstore = evidence_store_v2.EvidenceStore()
        evidence_store_v2.load_spider_from_ir(evstore, spider_irs.values())

        # ---- load coder ----
        free_gb = torch.cuda.mem_get_info()[0]/(1<<30); total_gb = torch.cuda.mem_get_info()[1]/(1<<30)
        task_log(f'loading {CODER_ID}: gpu_free={free_gb:.2f}/{total_gb:.2f} GB')
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(CODER_ID)
        model = AutoModelForCausalLM.from_pretrained(CODER_ID, torch_dtype=torch.bfloat16, device_map='cuda')
        model.eval()
        task_log(f'LOADED coder in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1<<20)} MB')

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

        def evaluate_spider(item, sql):
            try:
                db_id = item['db_id']
                sp = spider_db_dir/db_id/f'{db_id}.sqlite'
                ex = make_executor(str(sp))
                ok_a, rows_a, et_a, em_a = ex(sql)
                if not ok_a: return False, False, et_a, em_a
                ok_g, rows_g, _, _ = ex(item.get('query',''))
                if rows_g is None: return True, False, '', ''
                match = sorted(rows_a) == sorted(rows_g)
                return True, match, ('result_mismatch' if not match else ''), ''
            except Exception as exc:
                return False, False, type(exc).__name__, str(exc)

        # Spider safe_mode policy (same as B6_v7 Spider) — protects B4_v5/B6_v7 baseline
        spider_policy = {
            'needs_judge': True,
            'judge_close_margin': 0.04,
            'judge_override_min_conf': 0.75,
            'judge_max_candidates': 4,
            'allow_anchor_override': True,
            'spider_safe_mode': True,
        }

        prefix = 's1v7_qwen2p5_coder_7b_spider_dev_full'
        preds_path = PRED_DIR/f'{prefix}_predictions.jsonl'
        done = already_done_count(preds_path); n = len(spider_dev)
        task_log(f'>>> {prefix}: {done}/{n} already done')
        if done >= n:
            task_log('  SKIP — already complete'); task_log('PHASE_EIGHT_S1V7_RUNNER_DONE'); return

        t0 = time.time(); processed = 0
        for i, item in enumerate(spider_dev):
            if i < done: continue
            db_id = item['db_id']; ir = spider_irs.get(db_id)
            if ir is None:
                rec = {'idx':i,'benchmark':'spider','db_id':db_id,
                       'baseline':'S1_v7','model':CODER_ID,
                       'generated_sql':'','executable':False,'execution_match':False,
                       'error_type':'no_schema_ir','error_message':'',
                       'safe_select':False,'fallback_used':True}
                append_jsonl(preds_path, rec); continue
            try:
                LAST['lm_calls']=0; LAST['lm_time']=0.0; LAST['lm_completion']=0
                sp = spider_db_dir/db_id/f'{db_id}.sqlite'
                verifier_ex = make_executor(str(sp)) if sp.exists() else None
                step = baselines_s1_v7.run_s1v7_step(
                    item['question'], ir, gen=gen, executor=verifier_ex,
                    demo_retriever=demo_retriever,
                    evidence_store=evstore, per_item_evidence='',
                    plan_schema_path=str(PLAN_SCHEMA_PATH) if PLAN_SCHEMA_PATH.exists() else None,
                    judge_gen=gen, judge_policy=spider_policy, benchmark='spider',
                    demo_k=3, demo_max_chars=900,
                )
                sql = step['sql']
                if not step['safe']:
                    executable, match, et, em = False, False, f'unsafe:{step["safe_reason"]}', ''
                else:
                    executable, match, et, em = evaluate_spider(item, sql)
                gold_sql = item.get('query') or ''
                audit = step.get('audit', {})
                rec = {
                    'idx':i,'benchmark':'spider','db_id':db_id,
                    'question':item.get('question',''),'gold_sql':gold_sql,
                    'model':CODER_ID,'baseline':'S1_v7',
                    'generated_sql':sql,'executable':executable,'execution_match':match,
                    'error_type':et,'error_message':em,
                    'latency_ms':round(LAST['lm_time'],2),
                    'completion_tokens':LAST['lm_completion'],
                    'lm_calls':LAST['lm_calls'],
                    'demo_chars_rendered':step.get('demo_chars_rendered', 0),
                    'demo_n':step.get('demo_n', 0),
                    'selected_candidate_source':step.get('selected_candidate_source',''),
                    'heuristic_top_source':step.get('heuristic_top_source',''),
                    'judge_invoked':step.get('judge_invoked', False),
                    'judge_overrode':step.get('judge_overrode', False),
                    'judge_chose_source':step.get('judge_chose_source',''),
                    'judge_confidence':step.get('judge_confidence', 0.0),
                    'candidate_count':step.get('candidate_count', 0),
                    'consensus_size':step.get('consensus_size', 0),
                    'verifier_top_score':step.get('verifier_top_score', 0.0),
                    'verifier_top2_margin':step.get('verifier_top2_margin', 0.0),
                    'planner_used':step.get('planner_used', False),
                    'plan_valid':step.get('plan_valid', False),
                    'fallback_used':step.get('fallback_used', False),
                    'fallback_reason':step.get('fallback_reason', ''),
                    'repair_used':step.get('repair_used', False),
                    'repair_rounds':step.get('repair_rounds', 0),
                    'difficulty':audit.get('difficulty',{}).get('difficulty', ''),
                    'difficulty_score':audit.get('difficulty',{}).get('score', 0.0),
                    'safe_select':step.get('safe', False),
                }
                append_jsonl(preds_path, rec); processed += 1
                if (i+1) % 10 == 0:
                    rate = processed / max(0.001,(time.time()-t0)/60)
                    eta = (n-(i+1))/max(0.001,rate)
                    task_log(f'  {prefix} {i+1}/{n} db={db_id[:18]:18s} '
                             f'src={step.get("selected_candidate_source","")[:24]:24s} '
                             f'judge={step.get("judge_invoked")} ovr={step.get("judge_overrode")} '
                             f'demo_chars={step.get("demo_chars_rendered",0)} '
                             f'exec={executable} match={match} '
                             f'(~{rate:.1f}/min, eta~{eta:.1f}m)')
                    heartbeat(prefix, i+1, n, rate)
            except Exception as exc:
                task_log(f'  EXC at {i}: {exc}\n{traceback.format_exc()[-400:]}')
                rec = {'idx':i,'benchmark':'spider','db_id':db_id,
                       'baseline':'S1_v7','model':CODER_ID,
                       'generated_sql':'','executable':False,'execution_match':False,
                       'error_type':f'pipeline_exception:{type(exc).__name__}',
                       'error_message':str(exc)[:300],'safe_select':False}
                append_jsonl(preds_path, rec)
        elapsed = time.time()-t0
        rows = [json.loads(l) for l in preds_path.open(encoding='utf-8')]
        ex_n = sum(1 for r in rows if r.get('execution_match'))
        from collections import Counter
        src_cnt = Counter(r.get('selected_candidate_source','?') for r in rows)
        j_inv = sum(1 for r in rows if r.get('judge_invoked'))
        j_ovr = sum(1 for r in rows if r.get('judge_overrode'))
        task_log(f'  {prefix} DONE: EX={ex_n/len(rows):.4f} ({ex_n}/{len(rows)}) '
                 f'judge_inv={j_inv} ovr={j_ovr} sources={dict(src_cnt)} elapsed={elapsed:.0f}s')

        task_log('PHASE_EIGHT_S1V7_RUNNER_DONE')
    except Exception as exc:
        task_log('PHASE_EIGHT_S1V7_RUNNER_FAILED')
        task_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
