# Step 12: B2 component sanity test on smoke10 item 0.
# Runs the full pipeline once end-to-end and prints every intermediate state.
# If green here, the BG smoke10 run is safe.

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
SPIDER_DIR = PROJECT_ROOT / 'data' / 'spider'
REPO = PROJECT_ROOT / 'repo'

# Make repo/src/evaluation importable
import sys
eval_path = str(REPO / 'src' / 'evaluation')
if eval_path not in sys.path:
    sys.path.insert(0, eval_path)

# Force reimport in case kernel cached an older version
for mod in list(sys.modules):
    if mod.startswith('baselines_b2'):
        del sys.modules[mod]
import baselines_b2 as b2

mm = sys.modules['__main__']
def _from_main(name):
    return getattr(mm, name, None) or globals().get(name)

model = _from_main('model'); tokenizer = _from_main('tokenizer')
tables_map = _from_main('tables_map'); db_paths = _from_main('db_paths')
lexical_schema_linking = _from_main('lexical_schema_linking')
build_reduced_schema_context = _from_main('build_reduced_schema_context')
extract_sql = _from_main('extract_sql'); execute_sql = _from_main('execute_sql')

import torch

# Load plan_schema
plan_schema = json.loads((REPO / 'docs' / 'plan_schema.json').read_text(encoding='utf-8'))

# Load smoke10 item 0
smoke10 = json.loads((SPIDER_DIR / 'subsets' / 'smoke_10.json').read_text(encoding='utf-8'))
item = smoke10[0]
print(f'item.idx=0 db_id={item["db_id"]} question={item["question"]!r}')
print(f'gold_sql={item["query"]!r}')

# Step a: schema linking
link = lexical_schema_linking(item['question'], item['db_id'], tables_map)
print(f'\n[link] selected_tables={link["selected_tables"]} reduction={link["reduction_ratio"]:.2f} fallback={link["fallback_used"]}')
reduced_ctx = build_reduced_schema_context(item['db_id'], link['selected_table_indexes'], tables_map)
print(f'\n[reduced_schema_context]\n{reduced_ctx}')

# Step b: planner
plan_prompt = b2.make_plan_prompt(item['question'], reduced_ctx)
print(f'\n[plan_prompt len={len(plan_prompt)}]\n{plan_prompt[:500]}...')

def gen(prompt, max_new=192):
    messages = [{'role': 'user', 'content': prompt}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(rendered, return_tensors='pt')
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

plan_raw = gen(plan_prompt, max_new=256)
print(f'\n[plan_raw]\n{plan_raw}')

# Step c: parse + validate
plan_parsed, plan_valid, plan_error = b2.parse_and_validate_plan(plan_raw, plan_schema)
print(f'\n[plan_parsed valid={plan_valid} error={plan_error!r}]')
print(json.dumps(plan_parsed, ensure_ascii=False, indent=2) if plan_parsed else '(no parsed plan)')

# Step d: plan->sql (only if valid)
if plan_valid:
    sql_prompt = b2.make_plan_to_sql_prompt(item['question'], plan_parsed, reduced_ctx)
    print(f'\n[sql_prompt len={len(sql_prompt)}]\n{sql_prompt[:400]}...')
    sql_raw = gen(sql_prompt, max_new=192)
    print(f'\n[sql_raw]\n{sql_raw}')
    generated_sql = extract_sql(sql_raw)
    print(f'\n[generated_sql] {generated_sql}')
    # Step e: execute + evaluate
    try:
        pred = execute_sql(db_paths[item['db_id']], generated_sql)
        gold = execute_sql(db_paths[item['db_id']], item['query'])
        execution_match = sorted(pred) == sorted(gold)
        print(f'\n[exec] executable=True execution_match={execution_match}')
        print(f'pred_rows[:3]={pred[:3]}  gold_rows[:3]={gold[:3]}')
    except Exception as exc:
        print(f'\n[exec] FAILED: {type(exc).__name__}: {exc}')
else:
    print('\n[plan_invalid] would record error_type="plan_invalid" and skip SQL generation')

print('\nSTATUS=DONE')
