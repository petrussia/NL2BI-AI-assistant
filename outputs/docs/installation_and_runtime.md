# Installation and Runtime Profile

Date: 2026-04-29T15:03:36.172745+00:00.

## Local (Windows) prerequisites

- Python 3.11+ (`C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe`).
- VS Code with the Microsoft Jupyter extension.
- Internet access to Cloudflare quick-tunnel domains (`*.trycloudflare.com`).
- Local clone / working tree at `D:\HSE\Диплом\NL2BI-AI-assistant\`.

Local Python deps: only `urllib`/`json`/`pathlib`/`subprocess` (standard library). No third-party packages required for the agent-side tools.

## Colab runtime

- Recommended GPU: NVIDIA L4 (23 GB VRAM) or T4 (16 GB VRAM, may force smaller batch sizes / single model at a time).
- Recommended runtime: Python 3.12, CUDA 12.x.

Pip dependencies (auto-installed by `30_kernel_bootstrap.py`):
- `torch>=2.10`
- `transformers>=4.45`
- `accelerate>=0.34`
- `bitsandbytes>=0.43.3`
- `sentencepiece`
- `safetensors`
- `func_timeout`
- `jsonschema`
- `gdown` (for Spider re-download)
- `flask` (for bridge cell)

## Model loading

All 7B/8B models are loaded in 4-bit `nf4` via `bitsandbytes`:
- `Qwen/Qwen2.5-Coder-7B-Instruct` — primary, ~5.3 GB VRAM.
- `Qwen/Qwen2.5-7B-Instruct` — comparator, ~5.3 GB VRAM.
- `meta-llama/Llama-3.1-8B-Instruct` — gated; needs `HF_TOKEN`. ~6 GB VRAM.
- `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct` — 16B MoE, ~12 GB VRAM in 4-bit; tight on L4.

Sequential load only (free previous before loading new):
```python
del model; gc.collect(); torch.cuda.empty_cache()
```

## GPU / RAM profile during inference

- **B0** (single SQL gen): ~5.5 GB VRAM peak per item, ~2-5 sec/item.
- **B1** (single SQL gen): same as B0; small extra string ops.
- **B2 / B2_v1** (planner + SQL gen): two model.generate calls, ~5-10 sec/item.
- **B3** (dual retrieval + planner + SQL): same as B2; CPU-side retrieval is ~milliseconds.
- **B4-lite** (multi-candidate, K=3, sampling): one batched model.generate with `num_return_sequences=3`, ~10-15 sec/item; bounded repair adds one more gen on failure.

## Drive layout (canonical)

```
/content/drive/MyDrive/diploma_plan_sql/
├── data/spider/      # dataset (re-downloadable via 31_restore_drive_spider.py)
│   ├── dev.json
│   ├── tables.json
│   ├── database/<db_id>/<db_id>.sqlite (166 DBs)
│   └── subsets/      # smoke_10, smoke_25, smoke_50, multidb_30
├── outputs/
│   ├── predictions/  # .jsonl per run
│   ├── metrics/      # .csv per run
│   ├── tables/       # comparisons, summaries, error_cases, examples, ablations
│   ├── logs/         # design docs, runlogs, audits, bg task logs, tz coverage
│   ├── plots/        # PNGs
│   ├── docs/         # bundled documentation
│   ├── analytics_handoff/  # analytics payloads
│   └── REPORT.md
├── practice/         # practice-side worklog/checklist/mapping
├── repo/
│   ├── docs/plan_schema*.json
│   └── src/evaluation/baselines*.py + retrieval.py + postprocess.py + query_analysis.py
└── exports/          # tarball backups
```

## Config flags (per script)

Most run scripts accept implicit defaults; high-impact knobs:
- `MODEL_ID` — set in each baseline script; not a CLI flag this iteration.
- `max_new_tokens` — 192 for SQL, 256-320 for planner.
- `temperature`, `top_p` — only B4-lite uses sampling (T=0.7, p=0.95); others greedy.
- `num_return_sequences` — B4-lite K=3.
- `min_score` for schema linker — 0.5 (lexical baseline).
- `top_k_knowledge` — B3 default 3.
- `repair_max` — B4-lite bounded to 1.
- `func_timeout` — SQLite per-query 8 s.
