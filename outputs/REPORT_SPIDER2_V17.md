# Spider2 Phase 17 (model swap on top of v16 pipeline) — unified report

_Generated: 2026-05-09 | branch: `experiments/denis` | author: Denis_

> **Scope.** Phase 17 holds the entire v16 pipeline constant — schema-grounding
> validator, identifier mapper with constrained substitution, BQ nested-rewrite,
> 4-part collapse, async-batch BG, Drive-marker poll — and **swaps only the
> generator**. Goal: test whether a stronger or different-family model can lift
> Snow off the 0% floor or BQ above the 60% Coder-7B baseline. Hardware: A100 80GB.
> Four generators × two lanes × pilot10 (= 80 task-attempts). NO FULL launches
> (gates not cleared). **Snow stayed at 0/10 schema_valid for every model. On BQ
> the Coder-7B baseline (60%) outperformed every larger model.**

---

## 1. Hardware + environment

| field | value |
|---|---|
| GPU | A100 80GB (HBM) |
| python | 3.12 |
| torch | 2.10.0+cu128 |
| transformers | 5.0.0 |
| accelerate | 1.13.0 |
| bitsandbytes | 0.49.2 (not used in final BF16 run) |
| pipeline | v16 (validator + constrained repair + nested rewrite, unchanged) |

Mid-experiment note: Colab runtime upgraded transformers 4.x → 5.0 between
the BQ-Qwen3-14B run (Phase 16-tail) and the Phase 17 mistral/qwen3-coder
runs. The validator and runner code is independent of transformers
internals; only model loading and chat-template paths are touched. Both
behave identically across versions for the deterministic-decoding setup
(do_sample=False, temperature=0).

## 2. What changed vs Phase 16

- New module `repo/src/evaluation/model_registry_v17.py` — 8 model
  profiles indexed by short alias. Single source of truth for hf_id +
  load_kwargs + non-thinking-mode + extra_pip.
- New launcher `tools/run_spider2_v17_pilot.py --lane {bq,snow}
  --model <alias>` — re-uses both v16 colab runners verbatim and patches
  only `_ensure_model` and `_gen` via a regex replace on the runner
  template before injection. The runner template (validator, mapper,
  repair, async-batch wrapper) is byte-identical to Phase 16.
- One bug found and fixed: `mistralai/Mistral-Small-3.2-24B-Instruct-2506`
  ships as `Mistral3Config` (multi-modal class) which transformers 5.0
  does NOT register with `AutoModelForCausalLM`. Swapped to
  `mistralai/Mistral-Small-24B-Instruct-2501` (same parameter count,
  classic MistralConfig, text-only). Documented in registry.

## 3. Pilot10 grid (4 models × 2 lanes)

### 3.1 chosen_schema_valid (the gate metric)

| Model (alias) | Snow | BQ | Snow Δ vs v16 | BQ Δ vs v16 |
|---|---:|---:|---:|---:|
| Qwen2.5-Coder-7B-Instruct (`qwen2_5_coder_7b`, **v16 baseline**) | 0/10 (0%) | 6/10 (60%) | — | — |
| Qwen3-14B (`qwen3_14b_sample20`, general) | 0/10 (0%) | 2/10 (20%) | 0 | **-4 (-40pp)** ❌ |
| Mistral-Small-24B-2501 BF16 (`mistral_small_24b_bf16`) | 0/10 (0%) | 3/10 (30%) | 0 | **-3 (-30pp)** ❌ |
| Qwen3-Coder-30B-A3B BF16 (`qwen3_coder_30b_bf16`) | 0/10 (0%) | 4/10 (40%) | 0 | **-2 (-20pp)** ❌ |

### 3.2 Other engine-side metrics (parse_ok / execute_ok)

| Model | Snow parse_ok | BQ parse_ok | Snow execute_ok | BQ execute_ok |
|---|---:|---:|---:|---:|
| Coder-7B v16 | 0 | 0 | 0 | 0 |
| Qwen3-14B | 0 | 0 | 0 | 0 |
| Mistral-Small-24B-2501 | 0 | 0 | 0 | 0 |
| Qwen3-Coder-30B-A3B | 0 | 0 | 0 | 0 |

Across all 4 models × both lanes, parse_ok and execute_ok stayed at 0/10.
Catalog/live divergence remains the dominant blocker on the BQ side and
semantic identifier hallucination remains the dominant blocker on Snow.

### 3.3 Constrained-repair helpful (mapper substitution counts)

| Model | Snow | BQ |
|---|---:|---:|
| Coder-7B v16 | 0 | 6 |
| Qwen3-14B | 0 | 2 |
| Mistral-Small-24B-2501 | 0 | 3 |
| Qwen3-Coder-30B-A3B | 0 | 3 |

Pattern: mapper helpfulness on Snow is structurally pinned at 0 — the
catalog diverges from live SF at the schema/database level (semantic miss),
not the typo level the mapper handles. On BQ, Coder-7B still wins.

## 4. Snow ceiling — robust across every model tested

Across **every Phase 11–17 attempt** Snow has stayed at 0–1/10
chosen_schema_valid:

| Phase | Model | Snow chosen_schema_valid |
|---|---|---:|
| 11 | Coder-7B | 1/10 |
| 12 | Coder-7B | 1/10 |
| 13 | Coder-7B | 0/10 (crash fix regression) |
| 16 | Coder-7B | 0/10 |
| 17 | Qwen3-14B (general) | 0/10 |
| 17 | Mistral-Small-24B-2501 BF16 | 0/10 |
| 17 | Qwen3-Coder-30B-A3B BF16 | 0/10 |

**Conclusion**: Snow is not generator-bound. The bottleneck is the
catalog: identifier hallucinations on Snow are semantic
(database/schema-level), not typo-shaped, so the constrained substitution
mapper has nothing to substitute toward. **Lifting Snow requires
retrieval-side work (oracle catalog, hybrid RAG, expanded sample
metadata), NOT a stronger generator.**

## 5. BQ — code-specialized small model beats large general models

| Model | Params | Code-specialized? | BQ schema_valid |
|---|---:|:---:|---:|
| Qwen2.5-Coder-7B (Coder family) | 7B | ✅ | **6/10 (60%)** |
| Qwen3-14B (general) | 14B | ✗ | 2/10 (20%) |
| Mistral-Small-24B-2501 (general) | 24B | ✗ | 3/10 (30%) |
| Qwen3-Coder-30B-A3B (Coder family, MoE 30B/3B active) | 30B/3B | ✅ | 4/10 (40%) |

Phase 17 isolates a clean signal: **at the same v16 pipeline, code-specialized
fine-tuning matters more than parameter count** for SQL identifier
selection on Spider2-Lite-BQ pilot10. The 7B Coder beats the 14B and 24B
general models by 30–40pp on schema_valid. Whether the 30B Coder beats
the 7B Coder is the deciding question for STAGE D (in §6 once the BQ run
returns).

## 6. STAGE D headline

**BQ Qwen3-Coder-30B-A3B BF16 pilot10 = chosen_schema_valid 4/10 (40%).**

The model is the strongest non-baseline coder in the comparison set. It
beats both general 14B and 24B baselines (which scored 20% and 30%) by a
clear margin, **but it underperforms Qwen2.5-Coder-7B-Instruct (60%) by
20pp.**

| comparison | direction | reading |
|---|:---:|---|
| 30B Coder vs 14B general | **+20pp** | code-specialization helps |
| 30B Coder vs 24B general | **+10pp** | code-specialization helps |
| 30B Coder vs **7B Coder** | **−20pp** | size-up does NOT compound |

Two clean readings:

1. **Code-specialized fine-tuning is the dominant lever** at this stage
   of the pipeline. A 7B coder beats both a 14B and a 24B general model.
   A 30B coder beats both general models. Family > scale.
2. **Within the coder family, more parameters did not lift schema_valid.**
   On n=10 the difference is 6 vs 4 = 20pp, which is suggestive but
   noisy. Mechanistically it is plausible: schema_valid is gated by the
   constrained-substitution mapper, which already maps Coder-7B's
   identifiers to catalog hits at a 60% rate. The 30B model has fewer
   raw "needs substitution" candidates (per-task struct skips dropped
   from 65 → 72 average and constrained_repair_helpful = 3 vs Coder-7B
   = 6) — i.e. it generates somewhat more confident initial identifiers
   but with **higher leak rate to `object_not_found`** (4/10 vs 2/10
   for Coder-7B), suggesting more "plausible-but-stale" identifiers
   that pass the validator but are absent from live BQ. Catalog/live
   divergence (the same parse_ok=0 issue from Phase 16) re-emerges
   as the next-step bottleneck.

Headline: **on Spider2-Lite-BQ pilot10, more parameters in the same
family did not improve schema_valid; in fact the small Coder remains
the operating-point baseline.** The model-side ceiling on this lane,
without retrieval/catalog work, is approximately 60% schema_valid.

## 7. What goes into ВКР from Phase 17

| signal | source |
|---|---|
| Phase 17 pilot10 grid (4 models × 2 lanes) | this report |
| Snow ceiling reproduced across 4 generators × 7 phases | §4 |
| Code-specialized vs general at fixed-pipeline | §5 |
| `model_registry_v17` + non-invasive launcher | code |
| transformers 5.0 / Mistral3Config compat note | §2 |

## 8. What MUST NOT go into ВКР

- Any Phase 17 number framed as a Spider2 benchmark — these are pilot10s
  on a development pipeline, not FULL benchmarks.
- Snow Phase 17 data marketed as evidence about model quality — Snow is
  retrieval-bound; the 0/10 result speaks to the catalog, not the
  models.
- Any "average across models" or "best of 4" leaderboard claim — pilot
  variance on n=10 is too high.

## 9. Operational status

- All Phase 17 commits stay local until explicit user push.
- DBT FULL 68 = 13.2% remains the only publishable Spider2 number.
- `model_registry_v17.py` is now the canonical place to add or test
  future generator candidates without touching v16 runners.
