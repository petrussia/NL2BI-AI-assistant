# External validation master matrix

_Generated: 2026-04-30T16:39:46.961409+00:00_
_Total rows: 8_

| Baseline | Model | Benchmark | Subset | n | EX | Executable | Mode | Safe-SELECT % | Has-JOIN % | Has-GROUPBY % | Avg tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | Qwen2.5-Coder-7B | BIRD-Mini-Dev | bird_minidev_30 | 30 | 0.2667 | 26 | full_EX | 100.0000 | 63.3333 | 16.6667 | 26.7000 |
| b2v2 | Qwen2.5-Coder-7B | BIRD-Mini-Dev | bird_minidev_30 | 30 | 0.2000 | 22 | full_EX | 100.0000 | 50.0000 | 13.3333 | 25.5667 |
| b0 | Qwen2.5-Coder-7B | Spider-2-Lite | spider2lite_30 | 30 | 0.0000 | 0 | structural_only | 96.6667 | 40.0000 | 60.0000 | 43.2333 |
| b2v2 | Qwen2.5-Coder-7B | Spider-2-Lite | spider2lite_30 | 30 | 0.0000 | 0 | structural_only | 96.6667 | 53.3333 | 60.0000 | 46.1000 |
| b0 | Llama-3.1-8B | BIRD-Mini-Dev | bird_minidev_30 | 30 | 0.1333 | 20 | full_EX | 100.0000 | 66.6667 | 13.3333 | 25.1000 |
| b2v2 | Llama-3.1-8B | BIRD-Mini-Dev | bird_minidev_30 | 30 | 0.0667 | 16 | full_EX | 100.0000 | 50.0000 | 10.0000 | 22.2333 |
| b0 | Llama-3.1-8B | Spider-2-Lite | spider2lite_30 | 30 | 0.0000 | 0 | structural_only | 100.0000 | 66.6667 | 36.6667 | 51.8000 |
| b2v2 | Llama-3.1-8B | Spider-2-Lite | spider2lite_30 | 30 | 0.0000 | 0 | structural_only | 100.0000 | 43.3333 | 36.6667 | 51.5667 |
