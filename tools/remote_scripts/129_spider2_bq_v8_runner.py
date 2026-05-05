# Phase 10 (Spider2 BQ agent_v8) runner — A_bq lane only (205 items).
#
# Resumable per-item JSONL append; per-candidate JSONL; per-step traces.
# Heartbeat every 10 items. BQ exec capped at maximum_bytes_billed=1 GB.
from __future__ import annotations

import gc, json, os, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
S2_ROOT = ROOT / 'external_benchmarks' / 'spider2_lite' / 'raw' / 'Spider2' / 'spider2-lite'
PRED_DIR = ROOT / 'outputs' / 'predictions'
TRACE_DIR = ROOT / 'outputs' / 'traces'
LOG_DIR = ROOT / 'outputs' / 'logs'
EVAL_DIR = ROOT / 'tools' / 'eval_v2'
SECRETS = ROOT / 'secrets' / 'spider2_bq_sa.json'
for p in (PRED_DIR, TRACE_DIR, LOG_DIR): p.mkdir(parents=True, exist_ok=True)

PREFIX = 'spider2_bq_agent_v8'
PRED_PATH = PRED_DIR / f'{PREFIX}_predictions.jsonl'
CAND_PATH = PRED_DIR / f'{PREFIX}_candidates.jsonl'
TRACE_PATH = TRACE_DIR / f'{PREFIX}_traces.jsonl'
TASK_LOG = LOG_DIR / 'spider2_bq_v8_runner_log.txt'
HEARTBEAT = LOG_DIR / 'spider2_bq_v8_runner_heartbeat.json'

CODER_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
BQ_MAX_BYTES = 10**9  # 1 GB cap per query

sys.path.insert(0, str(EVAL_DIR))


def utcnow(): return datetime.now(timezone.utc).isoformat()
def task_log(msg):
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(f'[{utcnow()}] {msg}\n')


def append_jsonl(p, rec):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')


def already_done_ids(p):
    if not p.exists(): return set()
    out = set()
    for ln in p.open(encoding='utf-8'):
        try:
            r = json.loads(ln)
            iid = r.get('instance_id', '')
            if iid: out.add(iid)
        except Exception:
            continue
    return out


def heartbeat(i, n, rate, n_exec, n_em_attempted):
    HEARTBEAT.write_text(json.dumps({
        'prefix': PREFIX, 'i': i, 'n': n,
        'rate_per_min': round(rate, 2),
        'exec_ok_so_far': n_exec,
        'updated': utcnow()}, indent=2))


def main():
    task_log('PHASE_TEN_BQ_V8_RUNNER_START')
    try:
        # 1. deps
        try: import func_timeout  # noqa
        except ImportError:
            os.system('pip -q install func_timeout')

        # 2. import v7+v8 modules
        for m in list(sys.modules):
            if m.startswith('spider2_'): del sys.modules[m]
        import spider2_router_v7 as router
        import spider2_tools_v7 as tools
        from spider2_bq_schema_index_v8 import build_index_from_db_dir
        from spider2_agent_v8 import run_bq_agent_step

        # 3. load 547 items + filter A_bq
        items = [json.loads(l) for l in (S2_ROOT / 'spider2-lite.jsonl').open(encoding='utf-8')]
        sqlite_root = S2_ROOT / 'resource' / 'databases' / 'sqlite'
        a_bq_items = []
        for it in items:
            r = router.route_item(it, sqlite_root=sqlite_root,
                                    bq_creds_present=True, bq_dataset_whitelist=None)
            if r['lane'] == 'A_bq':
                a_bq_items.append((it, r))
        task_log(f'A_bq items: {len(a_bq_items)}')

        # 4. BQ executor
        proj = json.loads(SECRETS.read_text(encoding='utf-8'))['project_id']
        bq_ex = tools.build_bq_executor(str(SECRETS), project=proj,
                                          max_bytes=BQ_MAX_BYTES)
        task_log(f'BQ_EXECUTOR_OK project={proj} max_bytes={BQ_MAX_BYTES}')

        # 5. coder LM
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        free_gb = torch.cuda.mem_get_info()[0]/(1<<30)
        task_log(f'loading {CODER_ID}: gpu_free={free_gb:.2f} GB')
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(CODER_ID)
        model = AutoModelForCausalLM.from_pretrained(
            CODER_ID, torch_dtype=torch.bfloat16, device_map='cuda')
        model.eval()
        task_log(f'LOADED in {time.time()-t0:.1f}s VRAM='
                 f'{torch.cuda.memory_allocated()//(1<<20)} MB')

        LAST = {'lm_calls': 0, 'lm_time': 0.0, 'lm_completion': 0}
        def gen(prompt, max_new=256):
            messages = [{'role': 'user', 'content': prompt}]
            try: rendered = tok.apply_chat_template(messages, tokenize=False,
                                                      add_generation_prompt=True)
            except Exception: rendered = prompt
            with torch.inference_mode():
                ids = tok(rendered, return_tensors='pt', truncation=True,
                           max_length=11000).to('cuda')
                t = time.time()
                out = model.generate(**ids, max_new_tokens=max_new,
                                       do_sample=False,
                                       pad_token_id=tok.eos_token_id)
                lat = (time.time() - t) * 1000
                gen_tok = out.shape[1] - ids['input_ids'].shape[1]
                LAST['lm_calls'] += 1
                LAST['lm_time'] += lat
                LAST['lm_completion'] += int(gen_tok)
                return tok.decode(out[0][ids['input_ids'].shape[1]:],
                                    skip_special_tokens=True)

        # 6. schema index cache by db_id
        idx_cache: dict[str, object] = {}
        def get_idx(db_id: str):
            if db_id not in idx_cache:
                d = S2_ROOT / 'resource' / 'databases' / 'bigquery' / db_id
                idx_cache[db_id] = build_index_from_db_dir(db_id, d)
                task_log(f'BUILT_INDEX db={db_id} tables={len(idx_cache[db_id].tables)}')
            return idx_cache[db_id]

        # 7. resume support — by instance_id
        done_ids = already_done_ids(PRED_PATH)
        task_log(f'>>> {PREFIX}: {len(done_ids)}/{len(a_bq_items)} already done')
        n = len(a_bq_items)

        t_loop = time.time(); processed = 0; n_exec_so_far = 0
        for i, (item, route) in enumerate(a_bq_items):
            iid = item.get('instance_id', '')
            if iid in done_ids: continue
            db_id = route['db_id']
            doc_paths = []
            ek = item.get('external_knowledge') or ''
            if ek:
                p = S2_ROOT / 'resource' / 'documents' / ek
                if p.exists(): doc_paths.append(p)

            base_rec = {
                'idx': i, 'instance_id': iid, 'db_id': db_id,
                'lane': 'A_bq', 'benchmark': 'spider2_lite',
                'baseline': 'agent_v8', 'model': CODER_ID,
                'question': item.get('question', ''),
                'external_knowledge': ek,
            }

            try:
                LAST['lm_calls'] = 0; LAST['lm_time'] = 0.0; LAST['lm_completion'] = 0
                idx = get_idx(db_id)
                step = run_bq_agent_step(
                    item.get('question', ''), idx,
                    gen=gen, bq_executor=bq_ex,
                    doc_paths=doc_paths,
                    judge_gen=gen, max_repair_rounds=2,
                    include_direct=True, include_retrieval=True,
                    include_cte=True, max_new_sql=700, max_new_cte=900,
                    execute_chosen_query=True, max_rows_exec=1000,
                )

                rec = {**base_rec,
                        'generated_sql': step['sql'],
                        'final_source': step['final_source'],
                        'parses': step['parses'],
                        'executable': step['executable'],
                        'rows_count': step['rows_count'],
                        'all_known': step['all_known'],
                        'table_refs': step['table_refs'],
                        'table_refs_n': step['table_refs_n'],
                        'has_join': step['has_join'],
                        'has_groupby': step['has_groupby'],
                        'has_subquery': step['has_subquery'],
                        'has_window': step['has_window'],
                        'has_unnest': step['has_unnest'],
                        'has_with': step['has_with'],
                        'bytes_billed': step['bytes_billed'],
                        'bytes_processed': step['bytes_processed'],
                        'error_type': step['error_type'],
                        'error_message': step['error_message'],
                        'phase': step['phase'],
                        'repair_used': step['repair_used'],
                        'repair_success': step['repair_success'],
                        'repair_rounds': step['repair_rounds'],
                        'judge_invoked': step['judge_invoked'],
                        'judge_overrode': step['judge_overrode'],
                        'judge_chose': step['judge_chose'],
                        'judge_confidence': step['judge_confidence'],
                        'candidate_count': step['candidate_count'],
                        'retrieval_selected_keys': step['retrieval']['selected_keys'],
                        'retrieval_doc_titles': step['retrieval']['doc_titles'],
                        'retrieval_fallback': step['retrieval']['fallback_used'],
                        'lm_calls': LAST['lm_calls'],
                        'latency_ms': round(LAST['lm_time'], 2),
                        'completion_tokens': LAST['lm_completion'],
                        'wall_time_s': step['wall_time_s'],
                }
                append_jsonl(PRED_PATH, rec)
                # candidates JSONL
                append_jsonl(CAND_PATH, {'idx': i, 'instance_id': iid,
                                          'candidates': step['candidates_summary']})
                # trace JSONL (repair trace)
                append_jsonl(TRACE_PATH, {'idx': i, 'instance_id': iid,
                                           'repair_trace': step['repair_trace'],
                                           'judge_reason': step['judge_reason'],
                                           'retrieval_rationale':
                                               (step.get('retrieval', {}) or {})})

                processed += 1
                if step.get('executable') is True: n_exec_so_far += 1
                if (i + 1) % 5 == 0 or processed == 1:
                    rate = processed / max(0.001, (time.time() - t_loop) / 60)
                    eta = (n - len(done_ids) - processed) / max(0.001, rate)
                    task_log(f'  {len(done_ids)+processed}/{n} iid={iid:10s} '
                             f'src={step["final_source"]:18s} '
                             f'parses={step["parses"]} exec={step["executable"]} '
                             f'cands={step["candidate_count"]} '
                             f'rep={step["repair_used"]}/{step["repair_success"]} '
                             f'(~{rate:.1f}/min, eta~{eta:.0f}m, '
                             f'exec_so_far={n_exec_so_far})')
                    heartbeat(len(done_ids) + processed, n, rate, n_exec_so_far, 0)

            except Exception as exc:
                task_log(f'  EXC at i={i} iid={iid}: {type(exc).__name__}: {exc}\n'
                         f'{traceback.format_exc()[-500:]}')
                rec = {**base_rec, 'generated_sql': '', 'parses': False,
                        'executable': False, 'all_known': None,
                        'error_type': f'pipeline_exception:{type(exc).__name__}',
                        'error_message': str(exc)[:300]}
                append_jsonl(PRED_PATH, rec)

        elapsed = time.time() - t_loop
        rows = [json.loads(l) for l in PRED_PATH.open(encoding='utf-8')]
        ex_n = sum(1 for r in rows if r.get('executable') is True)
        parses_n = sum(1 for r in rows if r.get('parses') is True)
        task_log(f'>>> DONE: rows={len(rows)} parses={parses_n} exec={ex_n} '
                 f'elapsed={elapsed:.0f}s')
        task_log('PHASE_TEN_BQ_V8_RUNNER_DONE')
    except Exception:
        task_log('PHASE_TEN_BQ_V8_RUNNER_FAILED')
        task_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
