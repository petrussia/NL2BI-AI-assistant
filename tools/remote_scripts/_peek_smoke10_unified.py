from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/b2v1_b3v1_b4final_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
b2 = sum(1 for _ in open('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b2v1_spider_smoke10_predictions.jsonl', encoding='utf-8')) if Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b2v1_spider_smoke10_predictions.jsonl').exists() else 0
b3 = sum(1 for _ in open('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b3v1_spider_smoke10_predictions.jsonl', encoding='utf-8')) if Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b3v1_spider_smoke10_predictions.jsonl').exists() else 0
b4 = sum(1 for _ in open('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b4_final_spider_smoke10_predictions.jsonl', encoding='utf-8')) if Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b4_final_spider_smoke10_predictions.jsonl').exists() else 0
print(f'B2v1={b2}/10  B3v1={b3}/10  B4f={b4}/10  done={"B2_B3_B4_BG_DONE" in txt}  failed={"B2_B3_B4_BG_FAILED" in txt}')
for l in lines[-8:]: print(l)
