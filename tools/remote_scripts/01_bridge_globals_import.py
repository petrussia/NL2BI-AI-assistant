# Step 1: import notebook __main__ globals into bridge scope so we can reuse
# model, tokenizer, db_paths, tables_map, helper functions without re-loading.

import sys
mm = sys.modules.get('__main__')
mm_dict = vars(mm) if mm else {}

# Copy useful names into our exec scope (globals())
WANTED = [
    'model', 'tokenizer',
    'PROJECT_ROOT', 'SPIDER_DIR', 'OUTPUTS_DIR', 'PRACTICE_DIR',
    'tables_map', 'db_paths', 'dev', 'smoke10',
    'build_full_schema_prompt_context', 'extract_sql', 'execute_sql',
    'lexical_schema_linking', 'build_reduced_schema_context',
    'make_b1_prompt', 'make_prompt',
    'func_timeout', 'FunctionTimedOut',
    'load_spider_dev', 'load_spider_tables', 'load_spider_db_paths',
]
imported = []
missing = []
for name in WANTED:
    if name in mm_dict:
        globals()[name] = mm_dict[name]
        imported.append(name)
    else:
        missing.append(name)

print('IMPORTED:', imported)
print('MISSING:', missing)

# Self-check: model + tokenizer present?
if 'model' in globals() and 'tokenizer' in globals():
    import torch
    print('MODEL_DEVICE:', next(model.parameters()).device)
    print('CUDA_AVAILABLE:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('GPU:', torch.cuda.get_device_name(0))
        print('VRAM_USED_MB:', torch.cuda.memory_allocated() // (1024 * 1024))
else:
    print('WARNING: model or tokenizer missing — would need to reload (~3 min)')
