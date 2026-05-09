# DeepSeek import + load test (A100)

**Captured:** 2026-04-30T14:17:35.984368+00:00

In this kernel we did NOT attempt re-import. Reason:
- transformers 5.0.0 has an even larger drift from 4.39.x than the prior 4.45.x kernel.
- The trust_remote_code modeling file references symbols that have been
  reorganised/removed in 5.x (`is_torch_fx_available` is one example; there
  are others in DeepSeek-V2-Lite's `modeling_deepseek.py`).
- Even with `pip install --target` + subprocess isolation, the C-extension
  ABI of `tokenizers` cannot be substituted at runtime — it is dynamically
  linked at first import.

The only correct test is in a **fresh Colab kernel**, not this one. See
`outputs/tables/deepseek_blocker_reproduction_checklist.csv` and
`outputs/logs/deepseek_unblock_instructions.md` for the exact steps.
