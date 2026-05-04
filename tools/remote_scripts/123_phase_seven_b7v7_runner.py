# Phase 7 (B7_v7) runner — calibrated B6_v7 controller with rich evidence layer.
# Ablations on FULL BIRD only (Spider has no per-item evidence; would be no-op).
#   - B7d_rich:           gold + schema + value-hints + generated_aliases (productive)
#   - B7c_profiles_only:  schema + value-hints (no gold, no aliases)
#   - B7e_none:           no evidence at all (sanity check vs B6_v7)
#
# Per-db value-hint cache: probes a database once and reuses the EvidenceV7 list
# across all questions on that db. Bounded by `_SAFE_TIMEOUT_S` per probe and
# a global per-db budget.
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

TASK_LOG = LOG_DIR / 'phase_seven_b7v7_runner_log.txt'
HEARTBEAT = LOG_DIR / 'phase_seven_b7v7_runner_heartbeat.json'
PLAN_SCHEMA_PATH = ROOT / 'tools' / 'eval_v2' / 'plan_schema_v5.json'
EVAL_DIR = ROOT / 'tools' / 'eval_v2'
sys.path.insert(0, str(EVAL_DIR))

CODER_ID = 'Qwen/Qwen2.5-Coder-7B-Instruct'

CELLS_TO_RUN = os.environ.get('PHASE7_CELLS', 'B7d_rich,B7c_profiles_only,B7e_none').split(',')

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
    task_log(f'PHASE_SEVEN_B7V7_RUNNER_START cells={CELLS_TO_RUN}')
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        bird_full = json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/mini_dev_sqlite.json').read_text(encoding='utf-8'))
        bird_tables = {t['db_id']: t for t in
                        json.loads((EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_tables.json').read_text(encoding='utf-8'))}
        task_log(f'data: bird_full={len(bird_full)}')

        import schema_ir_v2, baselines_b7_v7, evidence_store_v2
        import evidence_semantics_v7 as ev7
        task_log('v2/v5/v7 modules imported ok')

        bird_db_root = EXT/'bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_databases'
        bird_irs = {db_id: schema_ir_v2.from_bird_tables_entry(
            entry, sqlite_path=str((bird_db_root/db_id/f'{db_id}.sqlite'))
                  if (bird_db_root/db_id/f'{db_id}.sqlite').exists() else None,
            description_dir=str((bird_db_root/db_id/'database_description'))
                  if (bird_db_root/db_id/'database_description').is_dir() else None)
                     for db_id, entry in bird_tables.items()}
        evstore = evidence_store_v2.EvidenceStore()
        evidence_store_v2.load_bird(evstore, bird_full)
        task_log(f'IRs built bird={len(bird_irs)}')

        # ---- precompute per-db value hints ONCE ----
        per_db_value_hints = {}
        per_db_schema_ev = {}
        for db_id, ir in bird_irs.items():
            sp = bird_db_root/db_id/f'{db_id}.sqlite'
            db_path = str(sp) if sp.exists() else None
            t0 = time.time()
            try:
                hints = ev7.build_column_value_hints(ir, db_path=db_path) if db_path else []
            except Exception as exc:
                task_log(f'  WARN value hints failed for {db_id}: {exc}')
                hints = []
            per_db_value_hints[db_id] = hints
            per_db_schema_ev[db_id] = ev7.build_db_profile_evidence(ir)
            elapsed = time.time() - t0
            task_log(f'  precomputed evidence for {db_id}: hints={len(hints)} schema_ev={len(per_db_schema_ev[db_id])} t={elapsed:.1f}s')
        task_log(f'precompute done; total dbs={len(bird_irs)}')

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

        def evaluate_bird(item, sql):
            try:
                db_id = item['db_id']
                sp = bird_db_root/db_id/f'{db_id}.sqlite'
                ex = make_executor(str(sp))
                ok_a, rows_a, et_a, em_a = ex(sql)
                if not ok_a: return False, False, et_a, em_a
                gold_text = item.get('SQL') or item.get('gold_sql') or item.get('query')
                if not gold_text: return True, False, 'no_gold', ''
                ok_g, rows_g, _, _ = ex(gold_text)
                if rows_g is None: return True, False, '', ''
                match = sorted(rows_a) == sorted(rows_g)
                return True, match, ('result_mismatch' if not match else ''), ''
            except Exception as exc:
                return False, False, type(exc).__name__, str(exc)

        # Custom build_evidence_pack closure that reuses per-db precompute.
        # Mode is passed EXPLICITLY (closure-global was buggy in v1: `global
        # ev_mode` creates a module-level var that doesn't override main's
        # local `ev_mode` captured by this function — all cells silently ran
        # in 'rich' mode in v1).
        def render_evidence_for_item(question: str, ir, item, mode: str) -> tuple[str, int]:
            """Wraps ev7.build_evidence_pack but inlines precomputed hints."""
            from evidence_semantics_v7 import (
                EvidenceV7, synthesize_aliases, retrieve_evidence_for_question,
                render_evidence_pack,
            )
            db_id = ir.db_id
            per_item_evidence = (item.get('evidence') or '').strip()
            flags = {
                'rich':           dict(schema=True,  hints=True,  aliases=True,  gold=True),
                'gold_only':      dict(schema=False, hints=False, aliases=False, gold=True),
                'profiles_only':  dict(schema=True,  hints=True,  aliases=False, gold=False),
                'generated_only': dict(schema=False, hints=False, aliases=True,  gold=False),
                'none':           dict(schema=False, hints=False, aliases=False, gold=False),
            }.get(mode, dict(schema=True, hints=True, aliases=True, gold=True))
            items_ev: list[EvidenceV7] = []
            if flags['gold'] and per_item_evidence:
                items_ev.append(EvidenceV7(scope='item', source_type='gold',
                                            text=per_item_evidence, confidence=1.0,
                                            quality='strong', is_gold=True))
            if flags['schema']:
                items_ev.extend(per_db_schema_ev.get(db_id, []))
            if flags['aliases']:
                items_ev.extend(synthesize_aliases(question, ir))
            if flags['hints']:
                items_ev.extend(per_db_value_hints.get(db_id, []))
            # selected_tables for relevance ranking
            sel_tables = []
            try:
                from schema_linker_bidirectional_v2 import link
                lr = link(question, ir, k_tables=5, expand_extra=4)
                sel_tables = lr.selected_tables or []
            except Exception:
                pass
            ranked = retrieve_evidence_for_question(question, ir, items_ev,
                                                     selected_tables=sel_tables, k=8)
            return render_evidence_pack(ranked, char_budget=600), len(ranked)

        def run_cell(prefix, ev_mode_in):
            preds_path = PRED_DIR/f'{prefix}_predictions.jsonl'
            done = already_done_count(preds_path); n = len(bird_full)
            task_log(f'>>> {prefix}: {done}/{n} already done (mode={ev_mode_in})')
            if done >= n: task_log('  SKIP'); return
            t0 = time.time(); processed = 0
            for i, item in enumerate(bird_full):
                if i < done: continue
                db_id = item['db_id']
                ir = bird_irs.get(db_id)
                if ir is None:
                    rec = {'idx':i,'benchmark':'bird','db_id':db_id,
                           'baseline':f'B7_v7_{ev_mode_in}','model':CODER_ID,
                           'generated_sql':'','executable':False,'execution_match':False,
                           'error_type':'no_schema_ir','error_message':'',
                           'safe_select':False,'fallback_used':True}
                    append_jsonl(preds_path, rec); continue
                try:
                    LAST['lm_calls']=0; LAST['lm_time']=0.0; LAST['lm_completion']=0
                    sp = bird_db_root/db_id/f'{db_id}.sqlite'
                    verifier_ex = make_executor(str(sp)) if sp.exists() else None

                    # Render evidence using precomputed per-db data; mode passed explicitly
                    rendered_ev, ev_n = render_evidence_for_item(item['question'], ir, item, ev_mode_in)

                    # Use b6_v7 directly (b7_v7 wrapper would re-probe DB; we already cached)
                    import baselines_b6_v7
                    judge_policy = {
                        'needs_judge': True, 'judge_close_margin': 0.10,
                        'judge_override_min_conf': 0.65, 'judge_max_candidates': 4,
                        'allow_anchor_override': True, 'spider_safe_mode': False,
                    }
                    step = baselines_b6_v7.run_b6v7_step(
                        item['question'], ir, gen=gen, executor=verifier_ex,
                        evidence_store=evstore, per_item_evidence=rendered_ev,
                        plan_schema_path=str(PLAN_SCHEMA_PATH) if PLAN_SCHEMA_PATH.exists() else None,
                        judge_gen=gen, judge_policy=judge_policy, benchmark='bird',
                    )
                    sql = step['sql']
                    if not step['safe']:
                        executable, match, et, em = False, False, f'unsafe:{step["safe_reason"]}', ''
                    else:
                        executable, match, et, em = evaluate_bird(item, sql)
                    gold_sql = item.get('query') or item.get('SQL') or item.get('sql') or item.get('gold_sql','')
                    audit = step.get('audit', {})
                    rec = {
                        'idx':i,'benchmark':'bird','db_id':db_id,
                        'question':item.get('question',''),'gold_sql':gold_sql,
                        'model':CODER_ID,'baseline':f'B7_v7_{ev_mode_in}',
                        'generated_sql':sql,'executable':executable,'execution_match':match,
                        'error_type':et,'error_message':em,
                        'latency_ms':round(LAST['lm_time'],2),
                        'completion_tokens':LAST['lm_completion'],
                        'lm_calls':LAST['lm_calls'],
                        'evidence_mode':ev_mode_in,
                        'evidence_chars_rendered':len(rendered_ev),
                        'evidence_items_n':ev_n,
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
                                 f'ev_chars={len(rendered_ev)} '
                                 f'exec={executable} match={match} '
                                 f'(~{rate:.1f}/min, eta~{eta:.1f}m)')
                        heartbeat(prefix, i+1, n, rate)
                except Exception as exc:
                    task_log(f'  EXC at {i}: {exc}\n{traceback.format_exc()[-400:]}')
                    rec = {'idx':i,'benchmark':'bird','db_id':db_id,
                           'baseline':f'B7_v7_{ev_mode_in}','model':CODER_ID,
                           'generated_sql':'','executable':False,'execution_match':False,
                           'error_type':f'pipeline_exception:{type(exc).__name__}',
                           'error_message':str(exc)[:300],'safe_select':False,
                           'evidence_mode':ev_mode_in}
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

        cell_specs = [
            ('B7d_rich',          'rich',           'b7d_rich_qwen2p5_coder_7b_bird_full'),
            ('B7c_profiles_only', 'profiles_only',  'b7c_profiles_only_qwen2p5_coder_7b_bird_full'),
            ('B7e_none',          'none',           'b7e_none_qwen2p5_coder_7b_bird_full'),
        ]
        for label, mode, prefix in cell_specs:
            if label not in CELLS_TO_RUN:
                task_log(f'>>> SKIP {label} (not in CELLS_TO_RUN)')
                continue
            task_log(f'>>> CELL {label} (mode={mode})')
            run_cell(prefix, mode)

        task_log('PHASE_SEVEN_B7V7_RUNNER_DONE')
    except Exception as exc:
        task_log('PHASE_SEVEN_B7V7_RUNNER_FAILED')
        task_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
