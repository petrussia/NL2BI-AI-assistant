# Runtime preflight — H100 lane

**Captured:** 2026-04-30T12:09:01.017367+00:00

- Bridge: live (exec_remote.py end-to-end verified by caller)
- GPU detected: **NVIDIA L4** (23.66 GB total)
- Drive mounted: True
- Project root size (top-level dirs):
{
  "data": "present",
  "outputs": "present",
  "repo": "present",
  "exports": "present"
}

## Decision
- If GPU is H100 80GB → proceed with heavy runs (Qwen2.5-Coder-14B, optional DeepSeek attempt with isolated env).
- If GPU is L4 24GB → still proceed with B2_v2/Qwen-14B 4-bit (~8GB), skip DeepSeek-via-isolated-env.
- HF_TOKEN: present in env (do not log).
