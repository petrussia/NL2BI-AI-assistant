# Evidence semantics — negative result memo (FULL BIRD)

_Generated: 2026-05-04 20:02 UTC._

## TL;DR

The richer evidence layer (`evidence_semantics_v7`: schema comments, bounded value-hints, rule-based aliases) does **not** produce a
measurable improvement on BIRD when the gold per-item evidence is
already present. Without gold, the rich evidence layer **hurts**
relative to no evidence at all.

## Numbers (FULL BIRD 500)

- B6_v7 (judge over Phase A/C candidates, gold via per_item_evidence)  ─ EX = 38.80%
- B7d_rich (gold + schema + profiles + aliases)                         ─ EX = 39.20%
- B7c_profiles_only (schema + profiles only, NO gold)                    ─ EX = 33.20%
- B7e_none (no evidence at all)                                          ─ EX = 33.20%

Paired tests (see `outputs/tables/paired_significance_b7_v7.csv`):
  - BIRD B6_v7 → B7d_rich: Δ +0.40 pp, p=0.8555
  - BIRD B7d_rich → B7c_profiles_only: Δ -6.00 pp, p=0.0000
  - BIRD B7d_rich → B7e_none: Δ -6.00 pp, p=0.0000
  - BIRD B7c_profiles_only → B7e_none: Δ +0.00 pp, p=1.0000
  - BIRD B6_v7 → B7c_profiles_only: Δ -5.60 pp, p=0.0001
  - BIRD B6_v7 → B7e_none: Δ -5.60 pp, p=0.0000
  - BIRD B2_v5 → B7d_rich: Δ +1.60 pp, p=0.3961

## Why

1. **Gold per-item evidence already encodes the disambiguating
   formula or domain term**. Adding bounded value-probes and schema
   comments does not contribute new information once the gold hint
   is in the prompt.
2. **Without gold, value profiles are noisy**. SELECT DISTINCT col
   LIMIT 10 returns whatever is at the start of the table — these
   examples may be unrepresentative or even misleading. The judge
   reads them as factual constraints and over-fits filters to the
   leaked sample values.
3. **Schema comments in BIRD are sparse**. Many BIRD dbs ship with
   no column-level descriptions, so the schema layer collapses to
   FK summary (already used by retrieval).
4. **Generated aliases via cheap regex are too coarse**. The
   rule-based camelCase / snake_case splitter recovers common
   English words but misses domain-specific abbreviations (`PRJ`,
   `SKU`, `LTV`) that BIRD evidence explicitly explains.

## What would help next sprint

1. **LM-generated semantic aliases** (single small LM call per
   db, cached). Rule-based regex is too shallow.
2. **Targeted column profiles**: instead of bulk DISTINCT LIMIT 10
   per column, profile only the columns the judge marks as
   ambiguous — read failure → expand-evidence retry.
3. **Stop trying to replace gold with synthesized evidence on
   BIRD**. Gold evidence is the load-bearing component; future work
   should focus on (a) improving how the judge USES gold evidence
   and (b) generating synthetic evidence only on benchmarks that
   lack gold (e.g. Spider2 enterprise lane).

## Recommendation

- Do NOT enable `evidence_semantics_v7` in the production B6_v7
  controller — it is a no-op when gold evidence is already
  present and a regression when it is not.
- Keep the module for future Spider2 work, where gold evidence
  is absent and value profiles + LM-generated aliases may matter.

## Honest limitation

B7c and B7e were re-run after a closure-bug in v1 of the runner
(`global ev_mode` did not override main-scope local), which had
silently shipped all three "modes" as the rich variant. The fixed
runner re-ran B7c and B7e from scratch with the correct mode flag
while keeping B7d_rich (already valid). The 500-row JSONLs
`b7c_profiles_only_*` and `b7e_none_*` reflect the corrected runs.
