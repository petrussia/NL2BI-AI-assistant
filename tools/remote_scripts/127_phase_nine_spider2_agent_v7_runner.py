# Phase 9 (Spider2 agent_v7) runner — FULL 547-item lane-aware run.
#
# Lanes (assigned by spider2_router_v7):
#   A_bq      execute via BigQuery (free public_data + paid datasets capped)
#   A_sf      blocked (no Snowflake creds in this env)
#   B_sqlite  execute via in-memory SQLite materialized from JSON stubs
#   C_struct  parse-only / dry-run only
#
# Resumable: per-item JSONL append; skip-if-done by counting rows.
# Heartbeat JSON every 10 items.
from __future__ import annotations

import gc, json, os, sys, time, traceback, sqlite3
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

TASK_LOG = LOG_DIR / 'phase_nine_spider2_runner_log.txt'
HEARTBEAT = LOG_DIR / 'phase_nine_spider2_runner_heartbeat.json'

PREFIX = 'spider2lite_agent_v7_full'
PREDS_PATH = PRED_DIR / f'{PREFIX}_predictions.jsonl'
TRACES_PATH = TRACE_DIR / f'{PREFIX}_traces.jsonl'

CODER_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'
BQ_MAX_BYTES = 10**9          # 1 GB cap per query (~$0.005)
BQ_HARD_MAX_BYTES = 10**11    # not used in this pass; logged for runner v2

sys.path.insert(0, str(EVAL_DIR))


def utcnow(): return datetime.now(timezone.utc).isoformat()
def task_log(msg):
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(f'[{utcnow()}] {msg}\n')


def append_jsonl(p, rec):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')


def already_done_count(p):
    return sum(1 for _ in p.open(encoding='utf-8')) if p.exists() else 0


def heartbeat(i, n, rate, lane_counts):
    HEARTBEAT.write_text(json.dumps({
        'prefix': PREFIX, 'i': i, 'n': n,
        'rate_per_min': round(rate, 2),
        'by_lane_done': lane_counts,
        'updated': utcnow()}, indent=2))


# ===================== item -> IR + executor =====================

def build_for_item(item, route, *, bq_executor):
    """Return (ir, executor, dialect_target, evidence_text, extra_audit)."""
    # spider2_tools_v7 imports relative to EVAL_DIR
    import spider2_tools_v7 as tools
    from schema_ir_v2 import SchemaIR

    db_id = route.get('db_id') or item.get('db', '')
    lane = route['lane']
    dialect = 'sqlite' if lane == 'B_sqlite' else 'bigquery' if lane == 'A_bq' else 'bigquery'
    evidence_text = ''
    extra = {}

    # External knowledge document
    ek = item.get('external_knowledge') or ''
    if ek:
        ek_path = S2_ROOT / 'resource' / 'documents' / ek
        if ek_path.exists():
            try:
                evidence_text = ek_path.read_text(encoding='utf-8',
                                                    errors='ignore')[:1500]
                extra['ek_chars'] = len(evidence_text)
            except Exception:
                pass

    if lane == 'B_sqlite':
        db_dir = Path(route.get('sqlite_dir') or '')
        ir = tools.build_ir_from_stub_dir(db_id, db_dir)
        con = tools.materialize_sqlite_from_dir(db_dir)
        ex = tools.build_sqlite_conn_executor(con)
        ex._con = con  # keep refcount alive for caller cleanup
        return ir, ex, 'sqlite', evidence_text, extra

    if lane == 'A_bq':
        bq_dir = S2_ROOT / 'resource' / 'databases' / 'bigquery' / db_id
        if not bq_dir.exists():
            ir = SchemaIR(db_id=db_id, dialect='bigquery',
                           source='spider2_lite', tables=[], fk_edges=[])
            extra['bq_dir_missing'] = True
        else:
            ir = tools.build_ir_from_bq_db_dir(db_id, bq_dir)
        return ir, bq_executor, 'bigquery', evidence_text, extra

    # A_sf / C_struct: noop
    ir = SchemaIR(db_id=db_id, dialect=dialect,
                   source='spider2_lite', tables=[], fk_edges=[])
    return ir, tools.NoopExecutor(), dialect, evidence_text, extra


def main():
    task_log('PHASE_NINE_SPIDER2_RUNNER_START')
    try:
        # 1) deps
        try:
            import func_timeout  # noqa
        except ImportError:
            task_log('installing func_timeout ...')
            os.system('pip -q install func_timeout')

        # 2) load 547 items
        items = [json.loads(l) for l in (S2_ROOT / 'spider2-lite.jsonl').open(encoding='utf-8')]
        task_log(f'data: spider2_items={len(items)}')

        # 3) router
        for m in list(sys.modules):
            if m.startswith('spider2_'): del sys.modules[m]
        import spider2_router_v7 as router
        import spider2_tools_v7 as tools
        import spider2_agent_v7 as agent

        sqlite_root = S2_ROOT / 'resource' / 'databases' / 'sqlite'
        routes = []
        from collections import Counter
        lane_n = Counter()
        for it in items:
            r = router.route_item(it, sqlite_root=sqlite_root,
                                    bq_creds_present=True,
                                    bq_dataset_whitelist=None)
            routes.append(r); lane_n[r['lane']] += 1
        task_log(f'route_summary: {dict(lane_n)}')

        # 4) load BQ executor once (lane A_bq uses this)
        try:
            bq_ex = tools.build_bq_executor(str(SECRETS),
                                              project=json.loads(SECRETS.read_text(encoding='utf-8'))['project_id'],
                                              max_bytes=BQ_MAX_BYTES)
            task_log(f'BQ_EXECUTOR_OK project={bq_ex.project} max_bytes={BQ_MAX_BYTES}')
        except Exception as exc:
            task_log(f'BQ_EXECUTOR_FAIL {type(exc).__name__}: {exc}; A_bq -> C_struct fallback')
            bq_ex = None
            for r in routes:
                if r['lane'] == 'A_bq':
                    r['lane'] = 'C_struct'; r['reason'] = 'bq_executor_init_failed'

        # 5) load coder LM
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        free_gb = torch.cuda.mem_get_info()[0]/(1<<30)
        total_gb = torch.cuda.mem_get_info()[1]/(1<<30)
        task_log(f'loading {CODER_ID}: gpu_free={free_gb:.2f}/{total_gb:.2f} GB')
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(CODER_ID)
        model = AutoModelForCausalLM.from_pretrained(CODER_ID,
                                                       torch_dtype=torch.bfloat16,
                                                       device_map='cuda')
        model.eval()
        task_log(f'LOADED coder in {time.time()-t0:.1f}s '
                 f'VRAM={torch.cuda.memory_allocated()//(1<<20)} MB')

        LAST = {'lm_calls': 0, 'lm_time': 0.0, 'lm_completion': 0}
        def gen(prompt: str, max_new: int = 256) -> str:
            messages = [{'role': 'user', 'content': prompt}]
            try:
                rendered = tok.apply_chat_template(messages, tokenize=False,
                                                     add_generation_prompt=True)
            except Exception:
                rendered = prompt
            with torch.inference_mode():
                ids = tok(rendered, return_tensors='pt',
                           truncation=True, max_length=12000).to('cuda')
                t = time.time()
                out = model.generate(**ids, max_new_tokens=max_new,
                                       do_sample=False,
                                       pad_token_id=tok.eos_token_id)
                lat = (time.time()-t)*1000
                gen_tok = out.shape[1] - ids['input_ids'].shape[1]
                LAST['lm_calls'] += 1
                LAST['lm_time'] += lat
                LAST['lm_completion'] += int(gen_tok)
                return tok.decode(out[0][ids['input_ids'].shape[1]:],
                                    skip_special_tokens=True)

        # 6) iterate
        done = already_done_count(PREDS_PATH); n = len(items)
        task_log(f'>>> {PREFIX}: {done}/{n} already done')
        if done >= n:
            task_log('PHASE_NINE_SPIDER2_RUNNER_DONE — already complete'); return

        t_loop_start = time.time(); processed = 0
        lane_done = Counter()
        # Spider2 has no spider regression concern; relax judge triggers
        spider2_policy = {'judge_close_margin': 0.5,
                           'judge_override_min_conf': 0.65,
                           'allow_anchor_override': True}

        for i, it in enumerate(items):
            if i < done:
                lane_done[routes[i]['lane']] += 1
                continue
            r = routes[i]
            lane = r['lane']
            base_rec = {
                'idx': i, 'instance_id': it.get('instance_id', ''),
                'benchmark': 'spider2_lite',
                'db_id': r['db_id'], 'lane': lane,
                'route_reason': r.get('reason', ''),
                'dialect': r.get('dialect', ''),
                'baseline': 'agent_v7', 'model': CODER_ID,
                'question': it.get('question', ''),
                'external_knowledge': it.get('external_knowledge', ''),
            }

            # Snowflake — record blocker without running anything
            if lane == 'A_sf':
                rec = {**base_rec,
                       'generated_sql': '', 'executable': None, 'execution_match': None,
                       'final_source': '', 'mode': 'blocked_snowflake',
                       'error_type': 'blocked', 'error_message': 'no_sf_creds',
                       'safe_select': False,
                       'judge_invoked': False, 'judge_overrode': False}
                append_jsonl(PREDS_PATH, rec)
                lane_done[lane] += 1
                continue

            try:
                LAST['lm_calls'] = 0; LAST['lm_time'] = 0.0; LAST['lm_completion'] = 0
                ir, ex, dialect_target, evidence_text, extra = build_for_item(
                    it, r, bq_executor=bq_ex)
                step = agent.run_spider2_agent_step(
                    it.get('question', ''), ir, lane=lane,
                    executor=ex, gen=gen,
                    dialect_target=dialect_target,
                    evidence_text=evidence_text,
                    full_schema_max_tables=8,
                    max_explore_steps=0,
                    max_repair_rounds=0,              # repair never helped on items 1-5
                    include_retrieval=False,          # C1 always lost to C0 in ranking
                    include_cte=False,                # C2 CTE prompt is the slowest
                    include_explore=False,
                    judge_gen=None,                   # no judge — single candidate
                    judge_policy=None,
                )
                # Cleanup in-memory sqlite if used
                if hasattr(ex, '_con'):
                    try: ex._con.close()
                    except Exception: pass

                v = step.get('verifier', {}) or {}
                rec = {**base_rec,
                       'generated_sql': step.get('sql', ''),
                       'executable': v.get('executable'),
                       'execution_match': None,  # gold-row comparison happens in consolidation
                       'rows_count': v.get('rows_count', 0),
                       'safe_select': bool(v.get('safe_select')),
                       'parses': v.get('parses'),
                       'all_known': v.get('all_known'),
                       'unknown_tables_n': len(v.get('unknown_tables') or []),
                       'unknown_columns_n': len(v.get('unknown_columns') or []),
                       'has_join': v.get('has_join'),
                       'has_groupby': v.get('has_groupby'),
                       'has_subquery': v.get('has_subquery'),
                       'mode': step.get('mode', ''),
                       'final_source': step.get('final_source', ''),
                       'top_score': step.get('top_score', 0.0),
                       'top2_margin': step.get('top2_margin', 0.0),
                       'judge_invoked': step.get('judge_invoked', False),
                       'judge_overrode': step.get('judge_overrode', False),
                       'judge_chose_source': step.get('judge_chose_source', ''),
                       'judge_confidence': step.get('judge_confidence', 0.0),
                       'judge_reason': step.get('judge_reason', '')[:200],
                       'repair_used': step.get('repair_used', False),
                       'repair_rounds': step.get('repair_rounds', 0),
                       'error_type': v.get('error_type', ''),
                       'error_message': (v.get('error_message') or '')[:300],
                       'bytes_billed': step.get('bytes_billed_total', 0),
                       'bytes_processed': step.get('bytes_processed_total', 0),
                       'lm_calls': LAST['lm_calls'],
                       'latency_ms': round(LAST['lm_time'], 2),
                       'completion_tokens': LAST['lm_completion'],
                       'candidates': step.get('candidates', []),
                       **{f'extra_{k}': v for k, v in (extra or {}).items()},
                }
                append_jsonl(PREDS_PATH, rec)
                # Trace
                trc = {'idx': i, 'instance_id': it.get('instance_id', ''),
                        'lane': lane,
                        'final_source': step.get('final_source', ''),
                        'trace': step.get('trace', [])}
                append_jsonl(TRACES_PATH, trc)
                lane_done[lane] += 1
                processed += 1

                if (i + 1) % 10 == 0 or processed == 1:
                    rate = processed / max(0.001, (time.time() - t_loop_start) / 60)
                    eta = (n - (i + 1)) / max(0.001, rate)
                    task_log(f'  {i+1}/{n} lane={lane:9s} '
                             f'iid={it.get("instance_id",""):10s} '
                             f'src={step.get("final_source",""):20s} '
                             f'exec={v.get("executable")} parses={v.get("parses")} '
                             f'rows={v.get("rows_count",0)} '
                             f'(~{rate:.1f}/min, eta~{eta:.0f}m, lane_done={dict(lane_done)})')
                    heartbeat(i + 1, n, rate, dict(lane_done))

            except Exception as exc:
                task_log(f'  EXC at {i} iid={it.get("instance_id","")}: '
                         f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-400:]}')
                rec = {**base_rec,
                        'generated_sql': '', 'executable': False, 'execution_match': None,
                        'safe_select': False,
                        'error_type': f'pipeline_exception:{type(exc).__name__}',
                        'error_message': str(exc)[:300],
                        'final_source': '', 'mode': 'exception',
                        'judge_invoked': False, 'judge_overrode': False}
                append_jsonl(PREDS_PATH, rec)
                lane_done[lane] += 1

        elapsed = time.time() - t_loop_start
        rows = [json.loads(l) for l in PREDS_PATH.open(encoding='utf-8')]
        from collections import Counter as C
        lane_cnt = C(r.get('lane', '?') for r in rows)
        ex_n = sum(1 for r in rows if r.get('executable'))
        parses_n = sum(1 for r in rows if r.get('parses'))
        all_known_n = sum(1 for r in rows if r.get('all_known'))
        task_log(f'>>> DONE: rows={len(rows)} exec_ok={ex_n} parses={parses_n} '
                 f'all_known={all_known_n} elapsed={elapsed:.0f}s '
                 f'by_lane={dict(lane_cnt)}')
        task_log('PHASE_NINE_SPIDER2_RUNNER_DONE')
    except Exception as exc:
        task_log('PHASE_NINE_SPIDER2_RUNNER_FAILED')
        task_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
