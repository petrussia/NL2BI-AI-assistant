# Final delivery status — v3 (maximal-finish)

Generated: 2026-04-30T12:31:29.037908+00:00

## Engineering scope — completed
- 14 baseline modules in `repo/src/evaluation/`.
- **25 baseline runs** across 3 subsets and 3 models (master matrix).
- B2_v2 / B3_v2 / B4_v2 v2 safety-net iteration: +0.50 smoke_10 / +0.27 multi-DB
  vs v1; **B2_v2 multi-DB BEATS B1** by +0.0333.
- Model block: 3 of 4 mandatory models evaluated (Qwen-Coder-7B, Qwen-Instruct-7B,
  Llama-3.1-8B); DeepSeek blocked environmentally with isolated-env attempt
  documented; Qwen-Coder-14B blocked on L4 hardware with explicit unblock path.
- 7 bundled docs in `outputs/docs/` (architecture + operations manual rewritten
  defense-ready in this iteration).
- 10 figures with captions in `outputs/plots/plot_captions_for_thesis.md`.
- **Shubin-only thesis pack** in `outputs/thesis_pack_shubin/` (8 files).

## Defense-readiness
- TZ coverage (strict, evidence-based): **100% (16/16)**.
- Negative result: cleanly framed and quantified; partial overturn for B2_v2.
- Reproduction: tarball + bridge tooling + `tools/remote_scripts/` ladder
  (numbered 30..79).

## What still requires human writing
1. Editorial pass on `outputs/docs/architecture_document.md` and
   `outputs/docs/operations_manual.md` for ВКР submission text (~2–3 h).
2. Insertion of numeric citations from `outputs/thesis_pack_shubin/01_final_numbers.md`
   into the existing ВКР drafts.
3. (Optional) DeepSeek B0/B1 in a clean notebook (~30 min runtime + setup).
4. (Optional) Qwen-Coder-14B B0/B1 on A100/H100 (~30 min runtime).
