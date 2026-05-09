# B4_v2 — design decision

**Issued:** 2026-04-30
**Predecessor:** B4_final (smoke10 EX = 0.30, multidb_30 EX = 0.47, capped by B3_v1)

## Problem identified by the prior iteration

B4_final's ceiling was set by `plan_valid_count / n` upstream from the B3_v1
planner. Multi-candidate sampling and bounded repair could not rescue items
where the planner had already failed. The repair loop tried to re-derive SQL
from a malformed plan; that almost never converges.

## Two surgical changes

1. **B1 fallback at *two* points** (not one): if the plan cannot be parsed *or*
   if no candidate executes after repair, emit a B1 single-shot SQL. This makes
   B4_v2 strictly dominate B1 in expectation: every plan-or-repair failure
   degrades to B1 instead of producing an empty/invalid SQL.
2. **Multi-candidate sampling only on valid plans.** When the plan is invalid
   we save the inference budget by going straight to B1 — no point spending
   3 sampled completions on a broken plan.

## Repair budget

Kept at 1 (depth=1). Empirically deeper repair on Spider does not help and
only inflates latency.

## Hypothesis

If the prior regression of B4_final was driven by upstream planner failures
inflating the "no executable candidate" rate, then B4_v2 should match or
exceed B1 across all subsets. If B4_v2 is roughly equal to B1, that is the
clean result: **multi-candidate / repair / SELECT-guard add safety but no
accuracy on this evaluation slice**, and the value of the planner stack is
zero unless we move to a benchmark with harder questions.
