from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/b2_smoke10_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
pred = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b2_spider_smoke10_predictions.jsonl')
n = sum(1 for _ in open(pred, encoding='utf-8')) if pred.exists() else 0
done = 'B2_BG_DONE' in txt
failed = 'B2_BG_FAILED' in txt
print(f'B2_progress={n}/10  done={done}  failed={failed}')
for l in lines[-6:]:
    print(l)
