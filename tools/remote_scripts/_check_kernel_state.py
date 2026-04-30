import sys
import torch
mm = sys.modules['__main__']
have = []
need = ['model','tokenizer','PROJECT_ROOT','tables_map','db_paths','dev','smoke10',
        'lexical_schema_linking','build_full_schema_prompt_context','build_reduced_schema_context',
        'extract_sql','execute_sql','make_prompt','make_b1_prompt','func_timeout','FunctionTimedOut']
missing = []
for n in need:
    if hasattr(mm, n):
        have.append(n)
    else:
        missing.append(n)
print('have:', have)
print('missing:', missing)
print('cuda:', torch.cuda.is_available(), 'vram_mb:', torch.cuda.memory_allocated()//(1024*1024) if torch.cuda.is_available() else 0)
