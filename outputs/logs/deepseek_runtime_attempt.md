# DeepSeek-Coder-V2-Lite-Instruct runtime attempt log

- Model: `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`
- Attempt: 2026-04-30T11:20:13.940227+00:00
- Rewritten with root cause: 2026-04-30T11:24:56.190697+00:00
- GPU: NVIDIA L4 (23.66 GB total, 23.46 GB free before load)
- Quant config: 4-bit nf4 bnb, double-quant, fp16 compute
- Outcome: **failed**
- Error class: `ImportError`
- Error message: `cannot import name 'is_torch_fx_available' from
  'transformers.utils.import_utils'`
- Elapsed: 16.29s (download + index, then import-time symbol resolution)
- Root cause: trust_remote_code modeling file references a transformers
  symbol that is no longer exported in the kernel's installed version.
- Decision: do not downgrade transformers in-place (would break Qwen-Coder).
  Document as environmental blocker; ship `deepseek_blocker_final.md`.
