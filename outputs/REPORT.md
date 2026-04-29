# B2 Pipeline Report — Local Snapshot

**Generated:** 2026-04-25 (after B2 smoke10 run)
**Source tarball:** `/content/drive/MyDrive/diploma_plan_sql/exports/diploma_b2_smoke10_results_20260425T175558Z.tar.gz` (123 KB)
**Bridge:** `https://participation-writings-organization-papua.trycloudflare.com` (live during this session)

---

## TL;DR

| metric | smoke10 |
|---|---|
| **EX B0 (full schema, single-shot)** | 1.0000 (10/10) |
| **EX B1 (reduced schema, single-shot)** | 1.0000 (10/10) |
| **EX B2 (Plan→SQL, two-shot)** | **0.7000 (7/10)** |
| executable B2 | 9 / 10 |
| plan_valid B2 | 9 / 10 |
| plan_parse_failures B2 | 0 / 10 |
| avg schema reduction (B1/B2) | 0.475 |
| **Winner on smoke10** | **tie (B0 = B1)** — B2 regresses |

**Headline:** Adding a planner stage **regressed** EX from 1.0 to 0.7. The planner itself is mostly working — 9/10 plans parse and validate against `plan_schema.json` — but two of them framed the question incorrectly, and one couldn't be fit into the schema at all. This is a clean signal that **the planner stage adds risk on simple questions** that the model already solves directly. Gain is only expected when planning genuinely helps (multi-step questions, multi-DB questions). Smoke10 is too easy to show that.

---

## What ran (this session)

| stage | result |
|---|---|
| Bridge `/health` | ok (pid 2218) |
| Preflight (19 required artefacts) | 18/19 — `plan_schema.json` was missing |
| Schema authored | `repo/docs/plan_schema.json` (3.5 KB), strict, 7-value intent enum, `additionalProperties: false` |
| Design decision | `outputs/logs/b2_design_decision.md` |
| `repo/src/evaluation/baselines_b2.py` | written (4.6 KB) — `make_plan_prompt`, `extract_json_block`, `parse_and_validate_plan`, `make_plan_to_sql_prompt` |
| `jsonschema` 4.26.0 | installed in kernel |
| **Component test on item 0** | end-to-end PASS: question → plan_valid → SQL → executable → execution_match |
| Schema bug found | `operations` was in `required` but missing from `properties`; patched (`tools/exec_remote.py --code`) |
| **B2 smoke10 BG inference** | 10/10 done in ~25 min; predictions saved incrementally |
| Three-way comparison | written: csv / md / png / case_diff |
| Practice + thesis evidence packs | refreshed to include B2 |
| Next-step readiness after B2 | written |
| Tarball v3 + Drive backup + local extract | 123 KB tarball, **84 files** locally |

## Numbers

### Three-way smoke10
```
| Metric            | B0     | B1     | B2     |
| EX                | 1.0000 | 1.0000 | 0.7000 |
| executable_count  | 10/10  | 10/10  |  9/10  |
| avg_reduction_ratio | —    | 0.475  | 0.475  |
| plan_valid_count  | —      | —      |  9/10  |
| plan_parse_failures | —    | —      |  0/10  |
```

Winner on smoke10: **tie (B0 = B1)** — B2 lost 3 cases.

### B2 failure breakdown (smoke10)
| idx | bucket | what happened |
|---|---|---|
| 6 | result_mismatch | "Show the name and release year of the song by the youngest singer." Plan was valid; SQL was `SELECT Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1`. Likely wrong column or wrong intent (gold wants the song attributes for the youngest singer's songs, not just the singer row). |
| 7 | result_mismatch | "What are the names and release years for all the songs of the youngest singer?" Plan emitted the same single-row framing as idx 6. SQL `… LIMIT 1` drops the "all songs" requirement entirely. |
| 8 | plan_invalid | "What are all distinct countries where singers above age 20 are from?" — JSON plan failed schema validation (likely an unsupported field or malformed filter for `>` + DISTINCT). Skipped SQL stage; counted as wrong. |

So three distinct failure modes:
1. Plan misframes intent (idx 6, 7) — "youngest" + "songs" interpreted as "youngest singer row".
2. Plan can't be expressed in our minimal schema (idx 8) — DISTINCT + filter + group-by interaction.

These are **planner-introduced** errors. B0 and B1 (no planner stage) handle all three correctly.

## What the planner *did* do well
- 9/10 plans parsed AND validated — the strict schema (`additionalProperties: false`, 7-value intent enum) didn't crowd out legitimate answers.
- Zero JSON parse failures — the model produced clean JSON every time.
- For 7 out of 10 questions the plan was right and so was the SQL.

## What the planner *did not* do
- No repair / retry loop. When the plan misframes, there is no second chance.
- No cross-validation between plan and SQL. SQL was generated from the plan without checking executable correctness against examples.
- No multi-candidate selection. One greedy plan, one greedy SQL.

## Pipeline state (local mirror — 84 files)

```
D:\HSE\Диплом\NL2BI-AI-assistant\
├── outputs\
│   ├── predictions\  (5 files — B0/B1/B2 smoke10 + B0/B1 smoke25)
│   ├── metrics\      (5 files)
│   ├── tables\       (31 files: summaries, examples, error_cases,
│   │                            two-way + three-way comparisons,
│   │                            case_diffs, schema linking examples,
│   │                            B2 plan_examples, aggregate progression,
│   │                            error taxonomy, failure buckets)
│   ├── logs\         (30 files: audits, runlogs, schema linking audits,
│   │                            bridge_status, artifact_recheck,
│   │                            B2 readiness + B2 implementation_plan,
│   │                            B2 design decision, b2_preflight,
│   │                            next_step_after_b2,
│   │                            thesis_* pack)
│   ├── plots\        (4 PNGs: smoke10 bar, smoke25 bar, progression 4-bar,
│   │                          three-way smoke10 bar)
│   └── REPORT.md     (this file)
├── practice\         (5 files: worklog, checklist, mapping, figure_index, table_index)
├── repo\
│   ├── docs\plan_schema.json
│   └── src\evaluation\
│       ├── baselines.py     (B1 lexical schema linking)
│       └── baselines_b2.py  (B2 minimal Plan->SQL pipeline)
└── data\spider\SOURCE_AND_AUDIT.md
```

## Tooling state

| component | status |
|---|---|
| Bridge cell `7f6bca53` `AGENT_BRIDGE_SETUP` | live |
| `tools/.bridge_url` | `https://participation-writings-organization-papua.trycloudflare.com` |
| `tools/exec_remote.py` | works — used for everything in this session (one HTTP `/exec` per script) |
| Background-thread inference dispatcher pattern | reused verbatim in `13_b2_smoke10_bg.py` |
| `tools/run_cell.py` v3 (SendKeys fallback) | retained, not used this session |
| `tools/notebook_status.py` | not needed — bridge is enough |

## Recommended next step

Per `outputs/logs/next_step_after_b2.md`:

> **1) B2 error triage on smoke10** — investigate plan_invalid and result_mismatch cases by hand (3 cases, ~20 min). Then patch the planner prompt (more examples? richer intent enum? add a "DISTINCT" hint?). Re-run B2 smoke10 and compare.
>
> 2) B2 on smoke25 (after smoke10 is back to >0.9 EX).
>
> 3) Multi-DB sample (this is where schema linking and planning should *both* show real gain).
>
> 4) B2.5 retrieval-enhanced (only after multi-DB sample shows separation).

Out of scope until then: B3, B4, fine-tuning, final practice/thesis writeups.

---

## Stable benefit verdict (after smoke10 + smoke25 + smoke10-B2)

- **Schema linking (B1 vs B0):** **inconclusive** on single-DB data — tie on smoke10, tie on smoke25, identical mistake at smoke25 idx 16. To verify, multi-DB sample needed.
- **Plan→SQL (B2 vs B1):** **regressed** on smoke10 (0.7 vs 1.0). On easy single-DB single-step questions, the planner stage is pure risk: it can misframe intent or fail to fit the question into the schema. B2 needs harder questions (multi-step, multi-table joins, multi-DB) before it can show value. The current evaluation slice is too small a window.
