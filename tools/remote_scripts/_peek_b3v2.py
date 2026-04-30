from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/b3v2_b4v2_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
preds = {
    'B3v2_s10':  '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b3v2_spider_smoke10_predictions.jsonl',
    'B4v2_s10':  '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b4v2_spider_smoke10_predictions.jsonl',
    'B3v2_mdb':  '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b3v2_multidb30_predictions.jsonl',
    'B4v2_mdb':  '/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/b4v2_multidb30_predictions.jsonl',
}
for L, fp in preds.items():
    n = sum(1 for _ in open(fp, encoding='utf-8')) if Path(fp).exists() else 0
    target = '/30' if 'mdb' in L else '/10'
    print(f'{L}={n}{target}')
print(f'done={"B3V2_B4V2_BG_DONE" in txt}  failed={"B3V2_B4V2_BG_FAILED" in txt}')
print('--- last 10 log lines ---')
for l in lines[-10:]: print(l)
