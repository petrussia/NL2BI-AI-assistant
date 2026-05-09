# External benchmark acquisition — summary

_Generated: 2026-04-30T15:57:19.335000+00:00_

| Benchmark | Status | Tasks loaded | Unique DBs | Slice |
|---|---|---|---|---|
| Spider 2.0-Lite | OK | 547 | 158 | `external_benchmarks/spider2_lite/processed/spider2lite_30_diverse.json` |
| BIRD Mini-Dev | FAILED | 0 | 0 | `external_benchmarks/bird_mini_dev/processed/bird_minidev_30_diverse.json` |

## Drive layout
```
external_benchmarks/
├── spider2_lite/
│   ├── raw/Spider2/        (sparse-checkout: spider2-lite/)
│   ├── processed/spider2lite_30_diverse.json
│   └── manifests/spider2_lite_manifest.json
└── bird_mini_dev/
    ├── raw/mini_dev/       (full shallow clone)
    ├── processed/bird_minidev_30_diverse.json
    └── manifests/bird_mini_dev_manifest.json
```

## Audit logs
- `outputs/logs/spider2_lite_acquisition.md`
- `outputs/logs/spider2lite_30_diverse_audit.md`
- `outputs/logs/spider2_lite_eval_limitations.md` (if EX not computable)
- `outputs/logs/bird_mini_dev_acquisition.md`
- `outputs/logs/bird_minidev_30_diverse_audit.md`
