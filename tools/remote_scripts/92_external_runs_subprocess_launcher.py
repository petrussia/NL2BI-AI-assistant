# Launch external benchmark evaluation as a single subprocess.
# Runs:
#   Qwen-Coder-7B: B0+B2_v2 on bird_minidev_30 + B0+B2_v2 on spider2lite_30
#   Llama-3.1-8B : B0+B2_v2 on bird_minidev_30 + B0+B2_v2 on spider2lite_30
# = 8 runs total. BIRD has SQLite execution (full EX); Spider2-Lite is
# prediction-only with structural metrics.

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
RUNNER = Path('/tmp/external_runner.py')

RUNNER.write_text(textwrap.dedent('''\
import csv
import datetime as dt
import gc
import json
import os
import re
import sqlite3
import sys
import textwrap
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
EXT = PROJECT_ROOT / 'external_benchmarks'
OUTPUTS = PROJECT_ROOT / 'outputs'
REPO = PROJECT_ROOT / 'repo'
for sub in ['logs','metrics','predictions','tables']:
    (OUTPUTS/sub).mkdir(parents=True, exist_ok=True)

TASK_LOG = OUTPUTS / 'logs' / 'external_runs_subproc_log.txt'

def task_log(msg):
    line = f'[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}'
    print(line, flush=True)
    with TASK_LOG.open('a', encoding='utf-8') as f:
        f.write(line+'\\n')

try:
    TASK_LOG.write_text('', encoding='utf-8')
    task_log('EXTERNAL_RUNS_SUBPROC_START')

    from func_timeout import FunctionTimedOut, func_timeout
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        from jsonschema import Draft7Validator as Draft202012Validator

    sys.path.insert(0, str(REPO/'src'/'evaluation'))
    import external_benchmark_adapters as ext
    import baselines_b2_v2 as b2v2

    plan_schema_v1 = json.loads((REPO/'docs'/'plan_schema_v1.json').read_text(encoding='utf-8'))
    plan_validator = Draft202012Validator(plan_schema_v1)

    bird_slice = ext.bird_load(EXT/'bird_mini_dev/processed/bird_minidev_30_diverse.json')
    s2_slice = ext.spider2_load(EXT/'spider2_lite/processed/spider2lite_30_diverse.json')
    task_log(f'loaded BIRD slice: n={len(bird_slice)}; Spider2 slice: n={len(s2_slice)}')

    # ===== generation helpers =====
    import torch
    MODEL = {'tok': None, 'm': None, 'id': None}
    def free_model():
        MODEL['tok'] = None; MODEL['m'] = None
        gc.collect(); torch.cuda.empty_cache()
        try: torch.cuda.synchronize()
        except Exception: pass

    def load_model(model_id, gated=False):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        token = os.environ.get('HF_TOKEN') if gated else None
        free_model()
        free, total = torch.cuda.mem_get_info(0)
        task_log(f'loading {model_id}: gpu_free={free/1e9:.2f} GB total={total/1e9:.2f} GB')
        t0 = time.time()
        kwargs = dict(device_map='auto', low_cpu_mem_usage=True, torch_dtype=torch.bfloat16,
                      trust_remote_code=True)
        if gated and token: kwargs['token'] = token
        tok = AutoTokenizer.from_pretrained(model_id, token=token if gated else None,
                                             trust_remote_code=True)
        m = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        m.eval()
        MODEL['tok'] = tok; MODEL['m'] = m; MODEL['id'] = model_id
        task_log(f'LOADED {model_id} in {time.time()-t0:.1f}s VRAM={torch.cuda.memory_allocated()//(1024*1024)} MB')

    def gen(prompt, max_new=256):
        m = MODEL['m']; tok = MODEL['tok']
        messages = [{'role':'user','content':prompt}]
        rendered = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(rendered, return_tensors='pt')
        inputs = {k: v.to(m.device) for k,v in inputs.items()}
        with torch.no_grad():
            out = m.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.eos_token_id)
        n_in = inputs['input_ids'].shape[1]
        return tok.decode(out[0][n_in:], skip_special_tokens=True)

    def extract_sql(text):
        text = text.strip()
        text = re.sub(r'^```(?:sql)?', '', text, flags=re.I).strip()
        text = re.sub(r'```$', '', text).strip()
        m = re.search(r'(?is)(select\\b.*)', text)
        if m: text = m.group(1).strip()
        text = text.split('\\n\\n')[0].strip()
        if ';' in text: text = text.split(';', 1)[0].strip()
        return text.rstrip(';') + ';'

    def execute_sql(db_path, sql, timeout=8):
        def _run():
            con = sqlite3.connect(str(db_path)); cur = con.cursor()
            cur.execute(sql); rows = cur.fetchall(); con.close(); return rows
        return func_timeout(timeout, _run)

    def make_b0_prompt_text(question, full_schema):
        return textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {full_schema}

        Question: {question}
        SQL:
        """).strip()

    # ===== writers =====
    def _md(rows, cols):
        lines = ['|'+'|'.join(cols)+'|', '|'+'|'.join(['---']*len(cols))+'|']
        for r in rows:
            v = []
            for c in cols:
                x = r.get(c, '')
                if isinstance(x, (list, dict)): x = json.dumps(x, ensure_ascii=False)
                v.append(str(x).replace('|','\\\\|').replace('\\n','<br>')[:700])
            lines.append('|'+'|'.join(v)+'|')
        return '\\n'.join(lines)+'\\n'

    def write_run(prefix, records, started, subset_name, bench_group, extra):
        pred_p = OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl'
        metr_p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
        sum_p = OUTPUTS/'tables'/f'{prefix}_summary.csv'
        run_p = OUTPUTS/'logs'/f'{prefix}_runlog.txt'
        err_p = OUTPUTS/'tables'/f'{prefix}_error_cases.md'
        ex_p = OUTPUTS/'tables'/f'{prefix}_examples.md'
        pred_p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in records), encoding='utf-8')
        total = len(records)
        exec_count = sum(1 for r in records if r.get('executable'))
        match_count = sum(1 for r in records if r.get('execution_match'))
        ex = match_count/total if total else 0.0
        # Aggregate structural for prediction-only benchmarks
        struct = ext.aggregate_structural(records)
        base = {'run_id': prefix, 'model': MODEL['id'], 'subset': subset_name,
                'benchmark_group': bench_group,
                'n': total, 'execution_match_count': match_count, 'ex': ex,
                'executable_count': exec_count}
        base.update({f'struct_{k}': f'{v:.4f}' if isinstance(v,float) else v for k,v in struct.items()})
        base.update(extra)
        with metr_p.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(base.keys())); w.writeheader(); w.writerow(base)
        with sum_p.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['metric','value']); w.writeheader()
            for k,v in [('completed','true'),('EX',ex),('executable_count',exec_count),
                        ('total',total),('model',MODEL['id']),('subset',subset_name),
                        ('benchmark_group',bench_group)] + list(extra.items()) + list(struct.items()):
                w.writerow({'metric':k,'value':v})
        run_p.write_text(textwrap.dedent(f"""
        {prefix} run log
        checked_at: {dt.datetime.now(dt.timezone.utc).isoformat()}
        model: {MODEL['id']}
        subset: {subset_name}
        benchmark_group: {bench_group}
        total: {total}
        executable_count: {exec_count}
        execution_match_count: {match_count}
        EX: {ex}
        elapsed_seconds: {time.time()-started:.2f}
        """).strip()+'\\n', encoding='utf-8')
        cols = ['idx','question','db_id','generated_sql','executable','execution_match','error_type','path']
        err_p.write_text(f'# {prefix} Error Cases\\n\\n' +
                         _md([records[i] for i in range(len(records)) if not records[i].get('execution_match')], cols),
                         encoding='utf-8')
        ex_p.write_text(f'# {prefix} Examples\\n\\n' + _md(records[:5], cols), encoding='utf-8')
        return base

    # ===== BIRD evaluators =====
    def evaluate_bird(item, sql):
        executable, match = False, False
        err_t, err_m = '', ''
        try:
            db_path = ext.bird_db_path(item['db_id'])
            pred = execute_sql(db_path, sql)
            executable = True
            gold = execute_sql(db_path, item['gold_sql']) if item.get('gold_sql') else None
            if gold is not None:
                match = sorted(pred) == sorted(gold)
                if not match: err_t = 'result_mismatch'
            else:
                err_t = 'no_gold'
        except FunctionTimedOut as exc:
            err_t, err_m = 'timeout', repr(exc)
        except Exception as exc:
            err_t, err_m = type(exc).__name__, str(exc)
        return executable, match, err_t, err_m

    def b1_fallback_bird(item):
        link = ext.bird_lex_link(item['question'], item['db_id'])
        reduced = ext.bird_reduced_schema(item['db_id'], link['selected_table_indexes'])
        prompt = textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQLite SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {reduced}

        Question: {item['question']}
        SQL:
        """).strip()
        return extract_sql(gen(prompt, max_new=256))

    def b1_fallback_s2(item):
        link = ext.spider2_lex_link_proxy(item['question'], item['db_id'])
        reduced = ext.spider2_full_schema_proxy(item['db_id'])  # proxy uses full anyway
        prompt = textwrap.dedent(f"""
        You are a text-to-SQL assistant. Generate one SQL query for the question.
        Use only the given schema. Return SQL only, no markdown and no explanation.

        {reduced}

        Question: {item['question']}
        SQL:
        """).strip()
        return extract_sql(gen(prompt, max_new=256))

    # ===== runners (BIRD) =====
    def run_b0_bird(prefix):
        task_log(f'=== B0 BIRD {MODEL["id"]} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(bird_slice):
            try:
                full_schema = ext.bird_full_schema(item['db_id'])
                p = make_b0_prompt_text(item['question'], full_schema)
                raw = gen(p, max_new=256)
                sql = extract_sql(raw)
                exb, match, et, em = evaluate_bird(item, sql)
            except Exception as exc:
                raw, sql = '', ''
                exb, match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('gold_sql',''), 'generated_raw': raw, 'generated_sql': sql,
                   'executable': exb, 'execution_match': match,
                   'error_type': et, 'error_message': em, 'path': 'direct_full_schema',
                   'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"]:<25} exec={exb} match={match} err={et!r}')
        return write_run(prefix, recs, t0, 'bird_minidev_30', 'external_validation',
                         {'quantization':'bf16','schema_strategy':'full_schema',
                          'gold_execution':'sqlite_minidev'})

    def run_b2v2_bird(prefix):
        task_log(f'=== B2_v2 BIRD {MODEL["id"]} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(bird_slice):
            full_schema = ext.bird_full_schema(item['db_id'])
            path = ''; plan_obj = None; plan_err = ''
            sql = ''
            try:
                plan_prompt = b2v2.make_b2v2_plan_prompt(item['question'], full_schema)
                raw_plan = gen(plan_prompt, max_new=256)
                plan_obj, plan_err = b2v2.parse_plan_json(raw_plan)
                if plan_obj is not None:
                    try:
                        plan_validator.validate(plan_obj)
                    except Exception as exc:
                        plan_err = f'schema_validation:{type(exc).__name__}:{str(exc)[:100]}'
                        plan_obj = None
                if plan_obj is None:
                    path = 'b1_fallback_invalid_plan'
                    sql = b1_fallback_bird(item)
                else:
                    sql_prompt = b2v2.make_b2v2_sql_prompt(item['question'], plan_obj, full_schema)
                    raw = gen(sql_prompt, max_new=256)
                    sql = extract_sql(raw)
                    path = 'plan_then_sql'
                exb, match, et, em = evaluate_bird(item, sql)
            except Exception as exc:
                sql=''; exb,match = False, False
                et, em = 'gen_failed', f'{type(exc).__name__}: {exc}'
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('gold_sql',''), 'plan': plan_obj, 'plan_error': plan_err,
                   'generated_sql': sql, 'executable': exb, 'execution_match': match,
                   'error_type': et, 'error_message': em, 'path': path,
                   'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B2v2 {i:>2} {item["db_id"]:<25} path={path:<26} exec={exb} match={match} err={et!r}')
        return write_run(prefix, recs, t0, 'bird_minidev_30', 'external_validation',
                         {'quantization':'bf16',
                          'schema_strategy':'full_schema_planner_full_schema_synth',
                          'plan_validator':'plan_schema_v1',
                          'fallback_policy':'b1_on_invalid_plan',
                          'gold_execution':'sqlite_minidev'})

    # ===== runners (Spider2-Lite — prediction-only) =====
    def run_b0_s2(prefix):
        task_log(f'=== B0 Spider2-Lite {MODEL["id"]} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(s2_slice):
            try:
                full_schema = ext.spider2_full_schema_proxy(item['db_id'])
                p = make_b0_prompt_text(item['question'], full_schema)
                raw = gen(p, max_new=256)
                sql = extract_sql(raw)
            except Exception as exc:
                raw, sql = '', ''
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('gold_sql',''), 'generated_raw': raw, 'generated_sql': sql,
                   'executable': None, 'execution_match': None,
                   'error_type': 'no_execution_engine', 'error_message': '',
                   'path': 'direct_full_schema_proxy',
                   'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B0 {i:>2} {item["db_id"]:<30} sql_len={len(sql)}')
        return write_run(prefix, recs, t0, 'spider2lite_30', 'external_validation',
                         {'quantization':'bf16',
                          'schema_strategy':'full_schema_proxy',
                          'gold_execution':'NOT_AVAILABLE_bigquery_snowflake_only',
                          'evaluation_mode':'prediction_only_structural_metrics'})

    def run_b2v2_s2(prefix):
        task_log(f'=== B2_v2 Spider2-Lite {MODEL["id"]} ===')
        t0 = time.time(); recs = []
        for i, item in enumerate(s2_slice):
            full_schema = ext.spider2_full_schema_proxy(item['db_id'])
            path = ''; plan_obj = None; plan_err = ''
            sql = ''
            try:
                plan_prompt = b2v2.make_b2v2_plan_prompt(item['question'], full_schema)
                raw_plan = gen(plan_prompt, max_new=256)
                plan_obj, plan_err = b2v2.parse_plan_json(raw_plan)
                if plan_obj is not None:
                    try:
                        plan_validator.validate(plan_obj)
                    except Exception as exc:
                        plan_err = f'schema_validation:{type(exc).__name__}:{str(exc)[:100]}'
                        plan_obj = None
                if plan_obj is None:
                    path = 'b1_fallback_invalid_plan'
                    sql = b1_fallback_s2(item)
                else:
                    sql_prompt = b2v2.make_b2v2_sql_prompt(item['question'], plan_obj, full_schema)
                    raw = gen(sql_prompt, max_new=256)
                    sql = extract_sql(raw)
                    path = 'plan_then_sql'
            except Exception:
                sql = ''
            rec = {'idx': i, 'question': item['question'], 'db_id': item['db_id'],
                   'gold_sql': item.get('gold_sql',''), 'plan': plan_obj, 'plan_error': plan_err,
                   'generated_sql': sql, 'executable': None, 'execution_match': None,
                   'error_type': 'no_execution_engine', 'error_message': '',
                   'path': path, 'structural': ext.structural_features(sql)}
            recs.append(rec)
            (OUTPUTS/'predictions'/f'{prefix}_predictions.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False)+'\\n' for r in recs), encoding='utf-8')
            task_log(f'  B2v2 {i:>2} {item["db_id"]:<30} path={path:<26} sql_len={len(sql)}')
        return write_run(prefix, recs, t0, 'spider2lite_30', 'external_validation',
                         {'quantization':'bf16',
                          'schema_strategy':'full_schema_proxy_planner_full_schema_synth',
                          'plan_validator':'plan_schema_v1',
                          'fallback_policy':'b1_on_invalid_plan',
                          'gold_execution':'NOT_AVAILABLE_bigquery_snowflake_only',
                          'evaluation_mode':'prediction_only_structural_metrics'})

    # ===== Lane 1: Qwen-Coder-7B =====
    load_model('Qwen/Qwen2.5-Coder-7B-Instruct', gated=False)
    s = run_b0_bird('b0_qwen2p5_coder_7b_bird_minidev_30')
    task_log(f'Qwen7B_B0_BIRD EX={s["ex"]:.4f}')
    s = run_b2v2_bird('b2v2_qwen2p5_coder_7b_bird_minidev_30')
    task_log(f'Qwen7B_B2v2_BIRD EX={s["ex"]:.4f}')
    s = run_b0_s2('b0_qwen2p5_coder_7b_spider2lite_30')
    task_log(f'Qwen7B_B0_Spider2Lite (prediction-only) avg_safe_select={s.get("struct_pct_safe_select","-")}')
    s = run_b2v2_s2('b2v2_qwen2p5_coder_7b_spider2lite_30')
    task_log(f'Qwen7B_B2v2_Spider2Lite (prediction-only) avg_safe_select={s.get("struct_pct_safe_select","-")}')

    # ===== Lane 2: Llama-3.1-8B =====
    load_model('meta-llama/Llama-3.1-8B-Instruct', gated=True)
    s = run_b0_bird('b0_llama_3p1_8b_bird_minidev_30')
    task_log(f'Llama_B0_BIRD EX={s["ex"]:.4f}')
    s = run_b2v2_bird('b2v2_llama_3p1_8b_bird_minidev_30')
    task_log(f'Llama_B2v2_BIRD EX={s["ex"]:.4f}')
    s = run_b0_s2('b0_llama_3p1_8b_spider2lite_30')
    task_log(f'Llama_B0_Spider2Lite (prediction-only) avg_safe_select={s.get("struct_pct_safe_select","-")}')
    s = run_b2v2_s2('b2v2_llama_3p1_8b_spider2lite_30')
    task_log(f'Llama_B2v2_Spider2Lite (prediction-only) avg_safe_select={s.get("struct_pct_safe_select","-")}')

    task_log('EXTERNAL_RUNS_SUBPROC_DONE')
except Exception:
    task_log('EXTERNAL_RUNS_SUBPROC_FAILED')
    task_log(traceback.format_exc())
'''))

# Spawn detached subprocess
proc = subprocess.Popen([sys.executable, str(RUNNER)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env={**os.environ})
print(f'STARTED subprocess pid={proc.pid}')
print(f'TASK_LOG={PROJECT_ROOT/"outputs/logs/external_runs_subproc_log.txt"}')
print(f'RUNNER_PATH={RUNNER}')

# Also write external adapter design doc
design = PROJECT_ROOT / 'outputs' / 'logs' / 'external_adapter_design.md'
design.write_text('''# External benchmark adapter — design

**Module:** `repo/src/evaluation/external_benchmark_adapters.py`

## Public API
- `bird_load(slice_path)` — load BIRD slice (list of dict).
- `bird_db_path(db_id) -> Path` — resolves to `external_benchmarks/bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_databases/<db_id>/<db_id>.sqlite`.
- `bird_full_schema(db_id)` — builds Spider-style schema text from `dev_tables.json`.
- `bird_lex_link(question, db_id)` — same lex-overlap linker as our internal Spider linker.
- `bird_reduced_schema(db_id, selected_idx)` — reduced schema for B1 fallback.
- `spider2_load(slice_path)` — load Spider2-Lite slice.
- `spider2_full_schema_proxy(db)` — synthesises a schema description from DDL.csv + sample JSON files in `resource/databases/sqlite/<db>/` (or bigquery/snowflake DDL as fallback).
- `spider2_lex_link_proxy(question, db)` — proxy lex linker over the synthesised schema.
- `structural_features(sql) / aggregate_structural(records)` — execution-free metrics for prediction-only benchmarks.

## Why two paths
- BIRD ships SQLite databases → full EX execution via our standard sandbox (`func_timeout`, 8s).
- Spider 2.0-Lite ships DDL+JSON for BigQuery/Snowflake — no actual database engine instance, no public gold inside the lite jsonl. We compute structural metrics only and document this as an environmental limitation.

## Integration with main pipeline
- Prefix-based naming: `<baseline>_<model_slug>_<benchmark>_<subset>` (e.g. `b0_qwen2p5_coder_7b_bird_minidev_30`).
- All outputs land in the same `outputs/{predictions,metrics,tables,logs}/` directories.
- Master matrix gets a new column `benchmark_group ∈ {internal_core, external_validation}` to keep external slices separate from canonical Spider runs.
- A separate `external_validation_master_matrix` view aggregates only the external rows.
''', encoding='utf-8')
print(f'WROTE {design}')
