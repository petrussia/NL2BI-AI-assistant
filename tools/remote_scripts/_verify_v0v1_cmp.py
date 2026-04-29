from pathlib import Path
r = Path('/content/drive/MyDrive/diploma_plan_sql/outputs')
files = [
    r / 'tables' / 'b2_v0_vs_b2_v1_smoke10_comparison.csv',
    r / 'tables' / 'b2_v0_vs_b2_v1_smoke10_comparison.md',
    r / 'plots' / 'b2_v0_vs_b2_v1_smoke10_bar.png',
]
for p in files:
    e = p.exists()
    s = p.stat().st_size if e else 0
    print(f'{e} {s:>8}B {p.name}')
print()
csv_p = files[0]
if csv_p.exists():
    print(csv_p.read_text(encoding='utf-8'))
