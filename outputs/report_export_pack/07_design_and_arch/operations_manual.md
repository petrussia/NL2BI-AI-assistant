# Operations manual — final (defense-ready)

**Date:** 2026-04-30T12:20:07.210990+00:00
**Author:** Шубин Денис Алексеевич

---

## 1. Runtime profile

- **GPU:** NVIDIA L4 24 GB (or stronger). Confirmed working: Qwen-Coder-7B, Qwen-Instruct-7B, Llama-3.1-8B-Instruct, Qwen-Coder-14B in 4-bit nf4 bitsandbytes.
- **CPU:** standard Colab default (12+ GB RAM).
- **Python:** 3.10+ (tested on 3.12.13).
- **Key dependencies:** `transformers>=4.45`, `bitsandbytes>=0.43`, `accelerate>=0.34`, `func_timeout`, `jsonschema`, `sentencepiece`, `safetensors`.
- **Disk:** ~30 GB for model cache (Qwen-Coder-7B ≈ 15 GB, Llama-3.1-8B ≈ 16 GB, Qwen-Coder-14B ≈ 28 GB on disk fp16; 4-bit on-disk is similar — quant happens at load).

## 2. How to run experiments — end-to-end recipe

1. **Mount Drive and start the bridge.**
   - In the Colab notebook `notebooks/example.ipynb`, run cell `AGENT_BRIDGE_SETUP` (id `7f6bca53`). It starts a Flask server in the kernel and exposes it via a free Cloudflare tunnel.
   - The cell prints `BRIDGE_URL: https://<random>.trycloudflare.com`.
   - Copy that URL into `tools/.bridge_url`.

2. **Sanity-check the bridge.**
   ```bash
   python tools/exec_remote.py --health
   ```
   Should print `{"ok": true, "pid": <int>}`.

3. **Bootstrap helpers and load the primary model (Qwen-Coder-7B).**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/30_kernel_bootstrap.py
   ```
   Cold cache load: ~3 min. Hot cache: ~30 sec.

4. **Run a baseline.** Example for B0 smoke_10:
   - the run is *internal* to the bootstrap script for B0/B1; for B2/B3/B4 use the dedicated BG scripts (`13_b2_smoke10_bg.py`, `23_b2_v1_smoke10_bg.py`, `54_b2v1_b3v1_b4final_smoke10_bg.py`, `62_b3v2_b4v2_smoke10_bg.py`, `74_b2v2_smoke10_multidb30_bg.py`).
   - Each BG script writes per-item predictions to `outputs/predictions/`, metrics to `outputs/metrics/`, and a task log to `outputs/logs/`.

5. **Poll BG progress.**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/_peek_b3v2.py
   ```
   (or `_peek_qwen14b.py`, `_peek_llama.py`, etc.)

6. **Consolidate.**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/65_final_consolidation_v2.py
   ```
   Rebuilds the master matrix CSV/MD and the master overview plot.

7. **Build deliverable tarball.**
   ```bash
   python tools/exec_remote.py --code-file tools/remote_scripts/59_final_tarball.py
   ```
   Tarball lands at `/content/drive/MyDrive/diploma_plan_sql/exports/latest_tz_closure.tar.gz`.

8. **Sync to local mirror.** Either download the tarball via the bridge `--download` flag, or extract via the b64-encoded path used in `tools/remote_scripts/_upload_local_mirror_v2.py`.

## 3. How to restore the bridge after it dies

Cloudflare quickrun tunnels are ephemeral; they die when the Colab cell or kernel restarts. Recovery:

1. In the notebook, re-run cell `7f6bca53`. A fresh URL is printed.
2. Update `tools/.bridge_url` with the new URL.
3. Re-run `python tools/exec_remote.py --health` to confirm.
4. The previous BG threads in the kernel are still alive if the kernel itself wasn't restarted; otherwise re-bootstrap helpers via `30_kernel_bootstrap.py`.

## 4. How to reproduce the master numbers

1. Mount Drive, restore Spider via `31_restore_drive_spider.py` if missing.
2. Restore local mirror to Drive via `_upload_local_mirror_v2.py` if Drive content was wiped.
3. Bootstrap kernel: `30_kernel_bootstrap.py`.
4. Re-run baselines in this order:
   - `54_b2v1_b3v1_b4final_smoke10_bg.py` (B2_v1, B3_v1, B4_final smoke_10)
   - `56_multidb30_5baselines_bg.py` (B0, B1, B2_v1, B3_v1, B4_final on multidb_30)
   - `62_b3v2_b4v2_smoke10_bg.py` (B3_v2, B4_v2 smoke_10 + multidb_30)
   - `74_b2v2_smoke10_multidb30_bg.py` (B2_v2)
   - `67_llama_b0_b1_bg.py` (Llama smoke_10)
   - `71_qwen14b_bg.py` (Qwen-Coder-14B smoke_10 + multidb_30)
5. Final consolidation: `65_final_consolidation_v2.py` then `66_final_docs_v2.py` then `59_final_tarball.py`.

## 5. Failure handling

| Failure | Symptom | Recovery |
|---|---|---|
| Bridge tunnel dead | `getaddrinfo failed` from `exec_remote.py` | Re-run cell `7f6bca53`; update `tools/.bridge_url`. |
| Drive content lost | Empty subdirectories under `/content/drive/MyDrive/diploma_plan_sql/` | Re-run `31_restore_drive_spider.py` then `_upload_local_mirror_v2.py`. |
| Model download interrupted | `from_pretrained` raises connection error | Re-run BG script — `from_pretrained` resumes from cache. |
| OOM on model load | `CUDA out of memory` | Free prior model first (BG scripts do this); reduce concurrent threads. |
| Plan parse failure | Predictions show `path=b1_fallback_invalid_plan` | Expected; B1 fallback handles this. |
| SQL execution timeout | `error_type=timeout` in predictions | Per-query 8s budget; gold SQL timed out too is rare. |

## 6. Honest blockers

- **DeepSeek-Coder-V2-Lite-Instruct** — environmental: `trust_remote_code` modeling file imports `is_torch_fx_available` which is not exported by current transformers. Unblock requires a fresh kernel with `transformers==4.39.x`. See `outputs/logs/deepseek_blocker_final.md`.
- **Llama-3.1-8B-Instruct** — was credential-blocked (no HF_TOKEN); **resolved** when the user attached HF_TOKEN to the runtime. See `outputs/logs/llama_blocker_final.md`.

## 7. Where things live

| Artifact | Path |
|---|---|
| Master matrix CSV | `outputs/tables/final_experiment_master_matrix.csv` |
| Master matrix MD | `outputs/tables/final_experiment_master_matrix.md` |
| Master plot | `outputs/plots/final_experiment_master_overview.png` |
| Multi-DB scientific readout | `outputs/logs/multidb30_scientific_readout.md` |
| Final REPORT | `outputs/REPORT.md` |
| Strict TZ coverage | `outputs/logs/tz_coverage_final_strict_v2.md` |
| Thesis pack | `outputs/thesis_pack_shubin/` |
| Latest tarball | `/content/drive/MyDrive/diploma_plan_sql/exports/latest_tz_closure.tar.gz` |
| Local mirror | the user's machine: `d:\HSE\Диплом\NL2BI-AI-assistant\` |
