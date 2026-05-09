# Llama-3.1-8B-Instruct — HF_TOKEN check

**Probed at:** 2026-04-30T11:16:39.952190+00:00
**Target model:** `meta-llama/Llama-3.1-8B-Instruct`

## Env-var presence
{
  "HF_TOKEN": false,
  "HUGGING_FACE_HUB_TOKEN": false,
  "HUGGINGFACE_HUB_TOKEN": false,
  "HF_API_TOKEN": false,
  "HUGGINGFACE_TOKEN": false
}

## Token file
- Path: `/root/.cache/huggingface/token`
- Present: **False**

## Colab userdata (Secrets)
{
  "HF_TOKEN": "error_TimeoutException",
  "HUGGINGFACE_TOKEN": "error_TimeoutException",
  "HF_API_TOKEN": "error_TimeoutException"
}

## Final decision
- have_token = **False**
- gated_repo_probe: {}
