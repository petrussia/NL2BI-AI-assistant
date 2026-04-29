# Thesis Methods Notes

Updated 2026-04-25T17:55:21.925124+00:00. Reusable phrasing for the experiments chapter; not the chapter itself.

## Setup paragraph
Spider dev split was loaded from the official YALE bundle. The first 10 and 25 examples define `smoke_10` and `smoke_25`; both fall in `concert_singer` (4 tables). All inference ran on a single NVIDIA L4 GPU in Google Colab using `Qwen/Qwen2.5-Coder-7B-Instruct` quantised to 4-bit `nf4` via `bitsandbytes`, greedy decoding (`do_sample=False`), `max_new_tokens=192` for SQL and 256 for plans. Generated SQL was extracted with a regex stripping markdown fences, executed via SQLite with an 8-second timeout (`func_timeout`), and compared to gold by row-multiset equality.

## Baselines paragraph
**B0** is a single-shot full-schema NL→SQL prompt. **B1** uses the same scaffold but replaces the schema block with a reduced one chosen by lexical schema linking (token overlap, table-name x2, column-name x1, English stopwords removed, `min_score=0.5`); tables with no signal trigger a full-schema fallback. **B2** is a two-stage Plan→SQL pipeline: a planner emits a JSON Plan validated against a strict schema with seven `intent` enum values and `additionalProperties: false`; the validated plan is then included in a second prompt that emits SQL. Invalid plans are recorded as `error_type=plan_invalid` and skip SQL generation.

## Results-shape paragraph
On smoke10, B0=B1=1.0 and B2=0.7; B2 plan_valid=9/10. On smoke25, B0=B1=0.96; B2 not yet evaluated. Both subsets being from the same DB bounds the schema-linking benefit; B2 introduces planner overhead but adds an explicit verifiable artefact (the JSON Plan).

## Limitations paragraph
The schema-linking signal is bounded on `concert_singer` alone — irrelevant tables are at most 3 of 4. Stronger conclusions require a multi-DB subset where the linker can rule out *databases*, not just tables. EX is execution-equivalence only; logical equivalence and partial-credit metrics are not computed. The model is loaded in 4-bit; numerical sensitivity to the quantisation scheme is not measured. B2 has no repair loop, no multi-candidate selection, and no domain-doc retrieval — these belong to B2.5+ and B3+. No fine-tuning is performed.

## Tooling paragraph (for the methods appendix)
Inference cells are dispatched via a Cloudflare-tunnelled Flask server inside the Colab kernel (notebook cell `AGENT_BRIDGE_SETUP`, id `7f6bca53`). The local agent talks to the kernel directly over HTTPS; this avoids the focus-race failure of SendKeys-based notebook drivers when the agent's terminal output renders in the same VS Code window as the notebook. Predictions are saved incrementally so a Cloudflare HTTP timeout (~100 s) never loses data; the background thread continues writing to Drive after the request returns. The `13_b2_smoke10_bg.py` script reuses this pattern verbatim from `04b_smoke25_b0_and_b1_bg.py`.
