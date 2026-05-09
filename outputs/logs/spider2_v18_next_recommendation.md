# Spider2 Phase 18 → Phase 18.1 — recommendation

_Generated: 2026-05-09_

## What Phase 18.0 changed

- Live BQ catalog (74 aliases / 154 dataset combos / 422k columns) and
  live Snow catalog (152 DBs / 573k columns) on disk.
- v18 pipeline: schema linker → compact pack → JSON planner → JSON
  validation → deterministic SQL renderer + Coder-7B control candidate
  → validator + BQ dry_run + selector.
- BQ pilot10: parse_ok 0 → 10/10. **execute_ok 0 → 1/10 — first non-zero
  engine acceptance signal in any non-DBT Spider2 lane.**

## What Phase 18.0 did NOT change

- chosen_schema_valid stayed 0/10 on the strict v18 closed-set check
  (over-conservative on hyphenated BQ projects, GA wildcard shards,
  nested struct paths). Numerator is wrong, not the metric.
- BQ pilot50 NOT launched (gate composite not cleared).
- Snow pilot10 NOT run this session (catalog harvested, pipeline ready).
- Ambiguity bank, multi-candidate families C/D, premium track all
  deferred to v18.2+ per the audited scope cut.

## Recommended order for Phase 18.1

### (1) Three concrete patches, then BQ pilot10 re-run (highest leverage)
- Renderer prefix-duplication collapse (`sql_renderer_v18`).
- Validator hyphen-aware identifier match (`candidate_selector_v18`).
- Date-shard wildcard recognition in plan validator + renderer
  (`structured_plan_v18` + `sql_renderer_v18`).

After these three: re-run `lite_bq_v18_pilot10`. Expected lift to
3-5/10 dry_run_ok. ~30 min code + 10 min pilot.

### (2) BQ pilot10 re-run on a non-GA-heavy slice
The first 10 BQ tasks happen to be GA-heavy. Re-pilot on
`bq30..bq40` (e.g. census, BLS, biketheft) to confirm the lift
generalizes. Same pipeline; different `--limit` slice.

### (3) Snow pilot10 on the v18 pipeline
Catalog is on disk. Same launcher with `--lane snow` once we add a
v18 Snow runner stub (mirror of `run_spider2_v18_bq_pilot.py`).

### (4) Pilot50 on whichever lane clears the gate first
Per brief: schema_valid > historical best AND non-zero engine signal.
After (1)-(3) we should know which lane is closest.

### (5) Ambiguity bank — only after (4)
Worth building only when the base pipeline reliably reaches `parse_ok
+ engine_ok ≥ 50%`; before that, ambiguity disambiguation is a tiny
edge case relative to the bug-class fixes.

## What goes into ВКР NOW (after Phase 18 + commit)

| signal | source |
|---|---|
| Live BQ + Snow catalogs on disk (refreshable) | Phase 18 |
| v18 schema-first / closed-set architecture | Phase 18 commit |
| **First non-zero `dry_run_ok` on Spider2-Lite-BQ** | Phase 18 pilot10 |
| parse_ok 100% via deterministic renderer | Phase 18 pilot10 |

## What MUST NOT go into ВКР

- Any Phase 18 number framed as a Spider2 benchmark — pilot10 is a
  pipeline-progression signal at n=10.
- The 1/10 dry_run_ok marketed as a benchmark result.
- The 0/10 closed-set schema_valid taken as a regression — the metric
  definition tightened, not the pipeline got worse. The proper
  comparison is parse_ok and dry_run_ok, both up from 0.

## Operational reminders

- All commits stay local until explicit user push.
- DBT FULL 68 = 13.2% remains the only publishable Spider2 number.
- v18.1 work continues on `experiments/denis`.
- The Phase 18.1 punch list is in §13 of `REPORT_SPIDER2_V18.md`.
