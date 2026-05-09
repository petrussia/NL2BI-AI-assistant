from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/multidb30_5b_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
preds = {
    'B0':  '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b0_multidb30_v2_predictions.jsonl',
    'B1':  '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b1_multidb30_v2_predictions.jsonl',
    'B2v1':'/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b2v1_multidb30_predictions.jsonl',
    'B3v1':'/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b3v1_multidb30_predictions.jsonl',
    'B4f': '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b4_final_multidb30_predictions.jsonl',
}
for L,fp in preds.items():
    n = sum(1 for _ in open(fp, encoding='utf-8')) if Path(fp).exists() else 0
    print(f'{L}={n}/30')
print(f'done={"MULTIDB30_5B_BG_DONE" in txt}  failed={"MULTIDB30_5B_BG_FAILED" in txt}')
print('--- last 8 log lines ---')
for l in lines[-8:]: print(l)
