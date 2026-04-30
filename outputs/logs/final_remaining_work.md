# Remaining work (post maximal-finish)

Generated: 2026-04-30T12:31:29.037908+00:00

## External / human-only (NOT engineering, blocking nothing)
1. **Editorial polish** of `outputs/docs/architecture_document.md` and
   `outputs/docs/operations_manual.md` for ВКР submission text (~2–3 h human).
2. **Numeric citation pass** in the existing ВКР draft docs — replace
   placeholders with values from `outputs/thesis_pack_shubin/01_final_numbers.md`.

## Optional engineering (not blocking defense)
1. **DeepSeek-Coder-V2-Lite-Instruct B0/B1 smoke_10** — fresh kernel with
   `transformers==4.39.3` pin (~30 min runtime + setup). Steps in
   `outputs/tables/deepseek_blocker_checklist_h100.csv`.
2. **Qwen-Coder-14B-Instruct B0/B1 smoke_10 + multidb_30** — A100/H100 only
   (~30 min runtime). Steps in `outputs/logs/qwen14b_blocker.md`.
3. **B2_v2 / B3_v2 / B4_v2 on smoke_25** — would add 6 cells to master matrix
   and confirm v2 advantage scales (~10 min total).
4. **Latency / token-cost columns** in master matrix — instrumentation in
   generation calls (~30 min code + reruns).

None of the above changes the headline. The diploma is at v3-final-maximal state.
