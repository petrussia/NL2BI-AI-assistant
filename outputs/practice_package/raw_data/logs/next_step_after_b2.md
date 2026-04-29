# Next Step After B2

Updated: 2026-04-25T17:55:50.203661+00:00

## Current state on smoke10
- B0 EX = 1.0
- B1 EX = 1.0
- B2 EX = 0.7
- B2 plan_valid_count = 9 / 10
- B2 plan_parse_failures = 0 / 10

## Recommended ordering
**1) B2 error triage on smoke10** — investigate plan_invalid and result_mismatch cases, then B2 smoke25.

2. **B2 on smoke25** — same code path, larger n; soak test before any architectural change.
3. **Multi-DB sample** — pick one or two questions from each of several Spider DBs (`concert_singer`, `wrestler`, `assets_maintenance`, `world_1`, `pets_1`). This is the first evaluation slice where lexical schema linking can show real gain (table elimination across DBs, not within one). Run B0/B1/B2 against it.
4. **B2.5 retrieval-enhanced** — replace the within-DB lexical linker with a cross-DB retrieval index (still lexical / TF-IDF, no embeddings yet). Stage this only after multi-DB sample shows separation.

## Rationale
B2 is below the comfort zone; smoke10 is small enough to triage by hand.

## Multi-DB note
Multi-DB sample remains valuable but not the most urgent next step.

## Out of scope until the above is done
- B3, B4 (more complex pipelines).
- Fine-tuning of any kind.
- Final practice / thesis chapters.
- Replacing 4-bit quantisation.
- Domain-doc retrieval (Spider has no glossary that justifies it).

## Risks to watch
- Cloudflare quick-tunnel timeout (~100 s) — keep using the bridge-side BG-thread pattern (`13_b2_smoke10_bg.py`).
- Plan parse failures inflate B2 error rate without informing about the underlying SQL skill — track them separately.
- Single-DB subsets continue to mask schema-linking benefit. Treat smoke25 ties cautiously.
