#!/usr/bin/env bash
# Phase 17 launcher cheat-sheet — fired manually as prereqs clear.
# Each block is meant to be uncommented + run individually after the
# previous one returns.

# ---- STAGE C: mistral-24b BF16 (Mistral-Small-Instruct-2501) ----
# Snow (already launched as snow_v17_mistral_bf16_pilot10):
# python tools/run_spider2_v17_pilot.py --lane snow \
#   --model mistral_small_24b_bf16 --limit 10 --no-execute \
#   --run-id snow_v17_mistral_bf16_pilot10 \
#   > outputs/spider2_snow/_v17_mistral_bf16.log 2>&1 &

# BQ (fire after Snow returns):
# python tools/run_spider2_v17_pilot.py --lane bq \
#   --model mistral_small_24b_bf16 --limit 10 \
#   --run-id lite_bq_v17_mistral_bf16_pilot10 \
#   > outputs/spider2_lite/_v17_mistral_bf16.log 2>&1 &

# ---- STAGE D: qwen3-coder-30b-a3b-bf16 (main) ----
# Free GPU first: `del _MDL`, `torch.cuda.empty_cache()` via bridge.
# Snow:
# python tools/run_spider2_v17_pilot.py --lane snow \
#   --model qwen3_coder_30b_bf16 --limit 10 --no-execute \
#   --run-id snow_v17_qwen3coder30b_bf16_pilot10 \
#   > outputs/spider2_snow/_v17_qwen3coder30b.log 2>&1 &

# BQ:
# python tools/run_spider2_v17_pilot.py --lane bq \
#   --model qwen3_coder_30b_bf16 --limit 10 \
#   --run-id lite_bq_v17_qwen3coder30b_bf16_pilot10 \
#   > outputs/spider2_lite/_v17_qwen3coder30b.log 2>&1 &

# ---- Existing v17 baselines on disk (do not re-run) ----
# qwen3_14b BQ:   outputs/spider2_lite/runs/lite_bq_v17_qwen3_14b_pilot10/
# qwen3_14b Snow: outputs/spider2_snow/runs/snow_v17_qwen3_14b_pilot10/
echo "runbook only — see comments"
