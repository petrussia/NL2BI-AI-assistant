# Baseline Progression smoke10 → smoke25

Checked at: 2026-04-25T17:10:59.516414+00:00

| Baseline | Subset | n | EX | Executable | Avg reduction |
|---|---|---|---|---|---|
| B0 | smoke10 | 10 | 1.0 | 10 | — |
| B1 | smoke10 | 10 | 1.0 | 10 | 0.475 |
| B0 | smoke25 | 25 | 0.9600 | 25 | — |
| B1 | smoke25 | 25 | 0.9600 | 25 | 0.58 |

## Deltas
- Δ EX (B1 - B0) on smoke10: +0.0000
- Δ EX (B1 - B0) on smoke25: +0.0000

## Conclusion
**tie on both subsets — no benefit, no harm from schema reduction (information-equivalent on this data)**

Caveat: smoke10 and smoke25 both come from `dev[:10]` and `dev[:25]` respectively, all `concert_singer`. Same DB, only question diversity grows. To stress schema linking, future runs should use a multi-DB subset.
