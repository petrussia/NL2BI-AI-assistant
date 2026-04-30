# Runtime preflight — full-matrix closure

**Captured:** 2026-04-30T15:20:33.945730+00:00

| | |
|---|---|
| Python | 3.12.13 |
| Platform | Linux-6.6.113+-x86_64-with-glibc2.35 |
| GPU | **NVIDIA A100-SXM4-80GB** |
| GPU VRAM total | 85.09 GB |
| GPU VRAM free | 84.65 GB |
| HF_TOKEN | set |
| Drive | True |

## Package versions
```json
{
  "torch": "2.10.0+cu128",
  "transformers": "5.0.0",
  "bitsandbytes": "NOT_INSTALLED (RuntimeError)",
  "accelerate": "1.13.0",
  "jsonschema": "4.26.0",
  "huggingface_hub": "1.11.0",
  "sentencepiece": "0.2.1",
  "safetensors": "0.7.0",
  "func_timeout": "4.3.5"
}
```

## Master state inventory
- Master matrix CSV: present, 29 prior rows
- Predictions on Drive: 29 files
- Repo modules on Drive: 15 files (incl. baselines_b2_v2/b3_v2/b4_v2)
- Subsets present: smoke_10.json, smoke_25.json, smoke_50.json, multidb_30.json
