from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/deepseek_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
b0 = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/deepseek_b0_smoke10_predictions.jsonl')
b1 = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions/deepseek_b1_smoke10_predictions.jsonl')
nb0 = sum(1 for _ in open(b0, encoding='utf-8')) if b0.exists() else 0
nb1 = sum(1 for _ in open(b1, encoding='utf-8')) if b1.exists() else 0
print(f'B0={nb0}/10  B1={nb1}/10  done_ok={"DEEPSEEK_BG_DONE_OK" in txt}  '
      f'done_blocked={"DEEPSEEK_BG_DONE_BLOCKED" in txt}  failed={"DEEPSEEK_BG_FAILED" in txt}')
print('--- last 12 log lines ---')
for l in lines[-12:]: print(l)
