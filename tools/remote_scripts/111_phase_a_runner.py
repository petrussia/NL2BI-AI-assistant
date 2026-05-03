# Phase A — retrieval ablation runner.
#
# Generates predictions for two new baselines on top of the v2 retrieval stack:
#   - b1_v5  = hybrid retrieval direct (no evidence)
#   - b2_v5  = hybrid retrieval + evidence direct
#
# Model: Qwen/Qwen2.5-Coder-7B-Instruct (BF16, A100).
# Benchmarks: full Spider dev (1034) + full BIRD Mini-Dev (500).
# Reuses v11 B0 anchor JSONLs for paired stats — does NOT re-run them.
# Per-item resumable writer; subprocess BG.
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

TASK_LOG = LOG_DIR / 'phase_a_runner_log.txt'
HEARTBEAT = LOG_DIR / 'phase_a_runner_heartbeat.json'

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def task_log(msg):
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(f'[{utcnow()}] {msg}\n')

# ---- v2 modules location ----
EVAL_DIR = ROOT / 'tools' / 'eval_v2'
sys.path.insert(0, str(EVAL_DIR))

def append_jsonl(p: Path, rec: dict):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')

def already_done_count(p: Path) -> int:
    if not p.exists(): return 0
    n = 0
    with p.open(encoding='utf-8') as f:
        for _ in f: n += 1
    return n

def heartbeat(prefix, i, n, rate):
    HEARTBEAT.write_text(json.dumps({
        'prefix': prefix, 'i': i, 'n': n, 'rate_per_min': round(rate, 2),
        'updated': utcnow(),
    }, indent=2))

# ---- main ----
def main():
    task_log('PHASE_A_RUNNER_START')
    try:
        # Lazy imports
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        # Load benchmark data
        import importlib.util
        spider_dev = json.loads((SPIDER_DIR/'dev.json').read_text(encoding='utf-8'))
        spider_tables = {t['db_id']: t for t in
                          json.loads((SPIDER_DIR/'tables.json').read_text(encoding='utf-8'))}
        bird_full = json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/mini_dev_sqlite.json').read_text(encoding='utf-8'))
        bird_tables = {t['db_id']: t for t in
                        json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_tables.json').read_text(encoding='utf-8'))}
        task_log(f'data: spider_dev={len(spider_dev)} bird_full={len(bird_full)}')

        # ---- import v2 modules ----
        import schema_ir_v2, dialect_utils_v2
        import retrieval_hybrid_v2, schema_linker_bidirectional_v2
        import evidence_store_v2, baselines_b1_v5, baselines_b2_v5
        task_log('v2 modules imported ok')

        # ---- build SchemaIR cache + evidence store ----
        spider_db_dir = SPIDER_DIR/'database'
        bird_db_root = EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_databases'
        bird_descr_root = bird_db_root  # database_description lives next to .sqlite

        spider_irs: dict[str, object] = {}
        for db_id, entry in spider_tables.items():
            sp = spider_db_dir / db_id / f'{db_id}.sqlite'
            spider_irs[db_id] = schema_ir_v2.from_spider_tables_entry(
                entry, sqlite_path=str(sp) if sp.exists() else None,
                dialect='sqlite', source='spider')
        bird_irs: dict[str, object] = {}
        for db_id, entry in bird_tables.items():
            sp = bird_db_root / db_id / f'{db_id}.sqlite'
            descr = bird_db_root / db_id / 'database_description'
            bird_irs[db_id] = schema_ir_v2.from_bird_tables_entry(
                entry, sqlite_path=str(sp) if sp.exists() else None,
                description_dir=str(descr) if descr.is_dir() else None)
        task_log(f'IRs built: spider={len(spider_irs)} bird={len(bird_irs)}')

        # Evidence store
        evstore = evidence_store_v2.EvidenceStore()
        n_ev = evidence_store_v2.load_bird(evstore, bird_full)
        evidence_store_v2.load_spider_from_ir(evstore, spider_irs.values())
        task_log(f'evidence loaded: bird_items={n_ev}')

        # ---- model + executor ----
        model_id = 'Qwen/Qwen2.5-Coder-7B-Instruct'
        free_gb = torch.cuda.mem_get_info()[0]/(1<<30)
        total_gb = torch.cuda.mem_get_info()[1]/(1<<30)
        task_log(f'loading {model_id}: gpu_free={free_gb:.2f} GB total={total_gb:.2f} GB')
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map='cuda')
        model.eval()
        task_log(f'LOADED {model_id} in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1<<20)} MB')

        LAST = {'metrics': {}}
        def gen(prompt, max_new=256):
            # Qwen2.5-Coder-Instruct requires ChatML wrapping.
            messages = [{'role': 'user', 'content': prompt}]
            try:
                rendered = tok.apply_chat_template(messages, tokenize=False,
                                                    add_generation_prompt=True)
            except Exception:
                rendered = prompt
            with torch.inference_mode():
                ids = tok(rendered, return_tensors='pt', truncation=True, max_length=8000).to('cuda')
                t0 = time.time()
                out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                     pad_token_id=tok.eos_token_id)
                lat = (time.time()-t0)*1000
                gen_tok = out.shape[1] - ids['input_ids'].shape[1]
                LAST['metrics'] = {
                    'latency_ms': lat,
                    'prompt_tokens': int(ids['input_ids'].shape[1]),
                    'completion_tokens': int(gen_tok),
                    'prompt_chars': len(prompt),
                }
                return tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True)

        # Executor (same as v11 runner)
        def execute_sql_for(sqlite_path, sql, timeout_s=8):
            def _run():
                with sqlite3.connect(f'file:{sqlite_path}?mode=ro', uri=True) as con:
                    con.text_factory = bytes
                    cur = con.cursor()
                    cur.execute(sql)
                    return cur.fetchall()
            return func_timeout(timeout_s, _run)

        def evaluate_spider(item, sql):
            executable, match = False, False
            err_t, err_m = '', ''; rows = None
            try:
                db_id = item['db_id']
                sp = spider_db_dir / db_id / f'{db_id}.sqlite'
                rows = execute_sql_for(str(sp), sql); executable = True
                gold = execute_sql_for(str(sp), item.get('query',''))
                match = sorted(rows) == sorted(gold)
                if not match: err_t = 'result_mismatch'
            except FunctionTimedOut as exc:
                err_t, err_m = 'timeout', repr(exc)
            except Exception as exc:
                err_t, err_m = type(exc).__name__, str(exc)
            return executable, match, err_t, err_m

        def evaluate_bird(item, sql):
            executable, match = False, False
            err_t, err_m = '', ''; rows = None
            try:
                db_id = item['db_id']
                sp = bird_db_root / db_id / f'{db_id}.sqlite'
                rows = execute_sql_for(str(sp), sql); executable = True
                gold_text = item.get('SQL') or item.get('gold_sql') or item.get('query')
                if gold_text:
                    gold = execute_sql_for(str(sp), gold_text)
                    match = sorted(rows) == sorted(gold)
                    if not match: err_t = 'result_mismatch'
                else:
                    err_t = 'no_gold'
            except FunctionTimedOut as exc:
                err_t, err_m = 'timeout', repr(exc)
            except Exception as exc:
                err_t, err_m = type(exc).__name__, str(exc)
            return executable, match, err_t, err_m

        # ---- per-cell loop ----
        def run_cell(baseline, bench_kind, items, irs_by_db, prefix):
            preds_path = PRED_DIR / f'{prefix}_predictions.jsonl'
            done = already_done_count(preds_path)
            n = len(items)
            task_log(f'>>> {baseline} {bench_kind} ({prefix}): {done}/{n} already done')
            if done >= n:
                task_log('  SKIP — already complete'); return
            t0 = time.time(); processed = 0
            for i, item in enumerate(items):
                if i < done: continue
                db_id = item['db_id']
                ir = irs_by_db.get(db_id)
                if ir is None:
                    rec = {'idx': i, 'benchmark': bench_kind, 'db_id': db_id,
                           'baseline': baseline, 'model': model_id,
                           'generated_sql': '', 'executable': False, 'execution_match': False,
                           'error_type': 'no_schema_ir', 'error_message': '',
                           'latency_ms': 0, 'prompt_tokens': 0, 'completion_tokens': 0,
                           'prompt_chars': 0, 'safe_select': False, 'fallback_used': True}
                    append_jsonl(preds_path, rec); continue
                try:
                    if baseline == 'B1_v5':
                        step = baselines_b1_v5.run_b1v5_step(item['question'], ir, gen=gen)
                    elif baseline == 'B2_v5':
                        per_item_ev = (item.get('evidence') or '').strip() if bench_kind == 'bird' else ''
                        step = baselines_b2_v5.run_b2v5_step(item['question'], ir, gen=gen,
                                                              evidence_store=evstore,
                                                              per_item_evidence=per_item_ev,
                                                              k_evidence=3)
                    else:
                        raise ValueError(f'unknown baseline {baseline}')
                    sql = step['sql']
                    if not step['safe']:
                        executable, match, et, em = False, False, f'unsafe:{step["safe_reason"]}', ''
                    else:
                        if bench_kind == 'spider':
                            executable, match, et, em = evaluate_spider(item, sql)
                        else:
                            executable, match, et, em = evaluate_bird(item, sql)
                    gold_sql = item.get('query') or item.get('SQL') or item.get('sql') or item.get('gold_sql', '')
                    rec = {
                        'idx': i, 'benchmark': bench_kind, 'db_id': db_id,
                        'question': item.get('question',''), 'gold_sql': gold_sql,
                        'model': model_id, 'baseline': baseline,
                        'generated_sql': sql, 'executable': executable, 'execution_match': match,
                        'error_type': et, 'error_message': em,
                        'latency_ms': round(LAST['metrics'].get('latency_ms',0),2),
                        'prompt_tokens': LAST['metrics'].get('prompt_tokens',0),
                        'completion_tokens': LAST['metrics'].get('completion_tokens',0),
                        'prompt_chars': LAST['metrics'].get('prompt_chars',0),
                        'selected_tables': step.get('selected_tables', []),
                        'selected_columns': [list(c) for c in step.get('selected_columns', [])],
                        'link_confidence': step.get('link_confidence', 0.0),
                        'selected_schema_ratio': step.get('reduction_ratio', 1.0),
                        'fallback_used': step.get('fallback_used', False),
                        'evidence_used': step.get('evidence_used', False),
                        'evidence_chars': step.get('evidence_chars', 0),
                        'safe_select': step.get('safe', False),
                        'rationale': step.get('rationale', []),
                    }
                    append_jsonl(preds_path, rec)
                    processed += 1
                    if (i+1) % 10 == 0:
                        rate = processed / max(0.001, (time.time() - t0) / 60)
                        eta_min = (n - (i+1)) / max(0.001, rate)
                        task_log(f'  {baseline} {i+1}/{n} db={db_id[:20]:20s} exec={executable} '
                                 f'match={match} err={repr(et)[:30]:30s} lat={LAST["metrics"].get("latency_ms",0):.0f}ms '
                                 f'(~{rate:.1f}/min, eta~{eta_min:.1f}m)')
                        heartbeat(prefix, i+1, n, rate)
                except Exception as exc:
                    task_log(f'  EXC at {baseline} idx={i}: {exc}\n{traceback.format_exc()[-400:]}')
                    rec = {'idx': i, 'benchmark': bench_kind, 'db_id': db_id,
                           'baseline': baseline, 'model': model_id,
                           'generated_sql': '', 'executable': False, 'execution_match': False,
                           'error_type': f'pipeline_exception:{type(exc).__name__}',
                           'error_message': str(exc)[:300],
                           'latency_ms': 0, 'prompt_tokens': 0, 'completion_tokens': 0,
                           'prompt_chars': 0, 'safe_select': False}
                    append_jsonl(preds_path, rec)
            elapsed = time.time() - t0
            # final stats
            rows = [json.loads(l) for l in preds_path.open(encoding='utf-8')]
            ex = sum(1 for r in rows if r.get('execution_match'))
            lats = sorted(float(r.get('latency_ms',0) or 0) for r in rows)
            p50 = lats[len(lats)//2] if lats else 0
            p95 = lats[int(len(lats)*0.95)] if lats else 0
            fb = sum(1 for r in rows if r.get('fallback_used')) / max(1, len(rows))
            task_log(f'  {prefix} DONE: EX={ex/len(rows):.4f} ({ex}/{len(rows)}) '
                     f'lat_p50={p50:.1f}ms p95={p95:.1f}ms fallback={fb:.2f} elapsed={elapsed:.0f}s')

        # ---- 4 cells ----
        cells = [
            ('B1_v5', 'spider', spider_dev, spider_irs, 'b1v5_qwen2p5_coder_7b_spider_dev_full'),
            ('B2_v5', 'spider', spider_dev, spider_irs, 'b2v5_qwen2p5_coder_7b_spider_dev_full'),
            ('B1_v5', 'bird',   bird_full,   bird_irs,   'b1v5_qwen2p5_coder_7b_bird_full'),
            ('B2_v5', 'bird',   bird_full,   bird_irs,   'b2v5_qwen2p5_coder_7b_bird_full'),
        ]
        for k, (bl, bk, items, irs, prefix) in enumerate(cells, 1):
            task_log(f'>>> CELL [{k}/{len(cells)}] baseline={bl} bench={bk} prefix={prefix}')
            run_cell(bl, bk, items, irs, prefix)
        task_log('PHASE_A_RUNNER_DONE')
    except Exception as exc:
        task_log('PHASE_A_RUNNER_FAILED')
        task_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
