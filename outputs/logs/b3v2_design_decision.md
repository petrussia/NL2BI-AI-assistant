# B3_v2 — design decision

**Issued:** 2026-04-30
**Predecessor:** B3_v1 (smoke10 EX = 0.30, multidb_30 EX = 0.47)

## Problem identified by the prior iteration

B3 / B3_v1 ship a "knowledge channel" that synthesises short table-level docs
*from the same Spider tables.json* that already drives schema linking. On Spider
this is purely additive prompt noise: it does not bring in any new external
information. The empirical signal: B3_v1 sits below B1 on every subset.

## Two surgical changes

1. **Knowledge channel disabled for every DB.** Not just "small DBs". The
   adaptive policy of B3_v1 was a half-measure; the underlying channel never
   carried information that schema linking did not already carry.
2. **Asymmetric context.** Planner gets the *reduced* schema (lex-linked
   tables only) so it stays focused; the SQL synthesizer gets the *full*
   schema so it can reach a column the linker dropped.

## Safety net: B1 fallback

If the planner's JSON cannot be parsed (or fails plan_schema_v1 validation),
the pipeline immediately degrades to a B1 single-shot SQL generation for that
item. This guarantees `EX(B3_v2) >= EX(B1) - sql_noise` in expectation: the
baseline can no longer sit *below* B1 because of planner failures.

## Hypothesis

If the prior regression of B3_v1 was driven by (a) knowledge prompt noise and
(b) hard planner failures, then B3_v2 should pull EX back to at least the B1
level on smoke10 and recover most of the gap on multidb_30.

If B3_v2 *still* sits below B1, the conclusion hardens: **on Spider with a
strong base model, layered planning is not just unnecessary, it is actively
harmful, and only a benchmark with multi-step reasoning beyond the base
model's one-shot ability can give planning a positive ROI.**
