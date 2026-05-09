from pathlib import Path
p = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/logs/qwen14b_bg_task_log.txt')
txt = p.read_text(encoding='utf-8') if p.exists() else ''
lines = txt.splitlines()
preds = {
    'B0_s10':  'b0_qwen2p5_coder_14b_instruct_smoke10_predictions.jsonl',
    'B1_s10':  'b1_qwen2p5_coder_14b_instruct_smoke10_predictions.jsonl',
    'B0_mdb':  'b0_qwen2p5_coder_14b_instruct_multidb30_predictions.jsonl',
    'B1_mdb':  'b1_qwen2p5_coder_14b_instruct_multidb30_predictions.jsonl',
}
ROOT = Path('/content/drive/MyDrive/diploma_plan_sql/outputs/predictions')
for L,fn in preds.items():
    fp = ROOT/fn
    n = sum(1 for _ in open(fp, encoding='utf-8')) if fp.exists() else 0
    target = '/30' if 'mdb' in L else '/10'
    print(f'{L}={n}{target}')
print(f'done={"QWEN14B_BG_DONE" in txt}  failed={"QWEN14B_BG_FAILED" in txt}')
print('--- last 10 log lines ---')
for l in lines[-10:]: print(l)
