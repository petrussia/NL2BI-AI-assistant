# v3 Architecture Head-to-Head (Qwen-Coder-7B)

_Generated: 2026-04-30T22:33:40.604353+00:00_

### multidb_30

| Baseline | EX | Has planner? | Has v3 linker/retrieval? |
|---|---|---|---|
| B0 | 0.9333 | no | no |
| B1V3 | 0.8000 | no | YES |
| B2V2 | 0.8000 | YES | no |
| B3V3 | 0.8000 | no | YES |
| B1 | 0.7667 | no | no |
| B2V3 | 0.7667 | YES | YES |
| B4V3 | 0.7667 | YES | YES |
| B3V2 | 0.7333 | no | no |
| B4V2 | 0.7333 | YES | no |
| B4_FINAL | 0.4667 | YES | no |

### smoke_25

| Baseline | EX | Has planner? | Has v3 linker/retrieval? |
|---|---|---|---|
| B0 | 0.9600 | no | no |
| B1 | 0.9600 | no | no |
| B1V3 | 0.9600 | no | YES |
| B2V2 | 0.9600 | YES | no |
| B2V3 | 0.9600 | YES | YES |
| B3V2 | 0.9600 | no | no |
| B3V3 | 0.9600 | no | YES |
| B4V2 | 0.9600 | YES | no |
| B4V3 | 0.9600 | YES | YES |

### bird_minidev_30

| Baseline | EX | Has planner? | Has v3 linker/retrieval? |
|---|---|---|---|
| B0 | 0.2667 | no | no |
| B3V3 | 0.2333 | no | YES |
| B1 | 0.2000 | no | no |
| B1V3 | 0.2000 | no | YES |
| B2V2 | 0.2000 | YES | no |
| B2V3 | 0.2000 | YES | YES |
| B4V3 | 0.2000 | YES | YES |
