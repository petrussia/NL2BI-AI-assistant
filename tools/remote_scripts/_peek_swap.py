from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/model_swap_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
done = 'MODEL_SWAP_BG_DONE' in txt
failed = 'MODEL_SWAP_BG_FAILED' in txt
loaded = next((l for l in lines if 'COMPARATOR_MODEL_LOADED=' in l), None) or next((l for l in lines if 'LOADED ' in l), None)
print(f'done={done}  failed={failed}')
if loaded: print('LOADED:', loaded)
for l in lines[-8:]:
    print(l)
