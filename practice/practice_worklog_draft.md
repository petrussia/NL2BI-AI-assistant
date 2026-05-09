# Practice Worklog Draft

## Current State (updated 2026-04-25T17:55:21.925124+00:00)

### B0 (full schema baseline)
- smoke10: EX=1.0, executable 10/10
- smoke25: EX=0.96, executable 25/25
- model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy

### B1 (reduced schema via lexical schema linking)
- smoke10: EX=1.0, avg reduction 0.475
- smoke25: EX=0.96, avg reduction 0.58

### B2 (Plan->SQL minimal pipeline)
- smoke10: EX=0.7, executable 9/10, plan_valid 9/10
- planner: JSON Plan validated against `repo/docs/plan_schema.json`
- module: `repo/src/evaluation/baselines_b2.py`
- design notes: `outputs/logs/b2_design_decision.md`

### Comparisons
- B0 vs B1 smoke10/smoke25 + aggregate progression smoke10→smoke25 (csv/md/png/case_diff)
- B0 vs B1 vs B2 smoke10 (csv/md/png/case_diff)

### Tooling
- Bridge tool primary path: `tools/exec_remote.py` over cloudflared tunnel from notebook cell `7f6bca53`
- Background-thread inference dispatcher pattern reused for both `04b_smoke25_b0_and_b1_bg.py` and `13_b2_smoke10_bg.py`

### Out of scope (intentionally not done)
- B2 on smoke25 (next candidate experiment)
- multi-DB sample (next-after-that)
- B3, B4, fine-tuning
- final practice and thesis chapters
