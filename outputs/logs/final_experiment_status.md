# Final Experiment Status

Generated at: 2026-04-29T14:44:17.177648+00:00

## What was actually run on Drive

| Baseline | Subset | Predictions present | Metrics present | EX |
|---|---|---|---|---|
| B0 | smoke10 | True | True | 1.0 |
| B1 | smoke10 | True | True | 1.0 |
| B2_v0 | smoke10 | True | True | 0.7 |
| B2_v1 | smoke10 | False | False | — |
| B3 | smoke10 | True | True | 0.2 |
| B4-lite | smoke10 | True | True | 0.2 |
| B0 | smoke25 | True | True | 0.96 |
| B1 | smoke25 | True | True | 0.96 |
| B2_v1 | smoke25 | False | False | — |

## Key artefacts

- Final ablation: `outputs/tables/final_ablation_summary.md`, `outputs/plots/final_ablation_overview.png`
- TZ coverage: `outputs/logs/tz_coverage_final.md`
- Postprocess + handoff: `outputs/logs/postprocess_and_handoff_design.md`, `outputs/analytics_handoff/`
- All design decisions: `outputs/logs/b{2,3,4}_*_decision.md`, `outputs/logs/b4_validation_policy.md`
- All baselines code: `repo/src/evaluation/baselines{,_b2,_b2_v1,_b3,_b4}.py`, `repo/src/evaluation/postprocess.py`
