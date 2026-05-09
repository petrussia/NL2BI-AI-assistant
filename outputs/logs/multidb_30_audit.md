# Multi-DB Subset Audit (multidb_30)

Built at: 2026-04-29T15:31:08.784311+00:00
Source: `data/spider/dev.json`
Output: `/content/drive/MyDrive/diploma_plan_sql/data/spider/subsets/multidb_30.json`

- N items: **30**
- Unique databases: **6**
- Per-DB target: **5** items each
- Skipped DBs: **['concert_singer']** (covered by smoke10/smoke25)
- Selection rule: alphabetical sort of db_id, take first PER_DB items (deterministic, no randomness)

## Selected DBs and counts

| db_id | items |
|---|---|
| `battle_death` | 5 |
| `car_1` | 5 |
| `course_teach` | 5 |
| `cre_Doc_Template_Mgt` | 5 |
| `dog_kennels` | 5 |
| `employee_hire_evaluation` | 5 |

## Reproducibility

- No `random.seed` involved.
- Spider `dev.json` byte-identical (see `data/spider/SOURCE_AND_AUDIT.md`).
- The same script produces the same subset on any kernel.

## Why this composition (no cherry-picking)

- Sorting by db_id is a property of the dataset, not of difficulty.
- Taking the first PER_DB items per DB preserves the original Spider ordering within each DB.
- This may include both easy and hard questions; the only filter applied is the per-DB count.
