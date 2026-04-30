from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/b3_b4_smoke10_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
b3 = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b3_spider_smoke10_predictions.jsonl')
b4 = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b4_spider_smoke10_predictions.jsonl')
n_b3 = sum(1 for _ in open(b3, encoding='utf-8')) if b3.exists() else 0
n_b4 = sum(1 for _ in open(b4, encoding='utf-8')) if b4.exists() else 0
done = 'B3_B4_BG_DONE' in txt
failed = 'B3_B4_BG_FAILED' in txt
print(f'B3={n_b3}/10  B4={n_b4}/10  done={done}  failed={failed}')
for l in lines[-7:]:
    print(l)
