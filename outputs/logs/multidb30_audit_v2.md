# multidb_30 audit (v2)

**Captured:** 2026-04-30T12:28:51.184084+00:00
**N items:** 30
**Distinct DBs:** 6

## Distribution by db_id
| db_id | count |
|---|---|
| `battle_death` | 5 |
| `car_1` | 5 |
| `course_teach` | 5 |
| `cre_Doc_Template_Mgt` | 5 |
| `dog_kennels` | 5 |
| `employee_hire_evaluation` | 5 |

## Manifest sanity
- All items have non-empty `question`: True
- All items have `query` (gold SQL): True
- All db_ids resolvable to sqlite path:
  - `battle_death`: True
  - `car_1`: True
  - `course_teach`: True
  - `cre_Doc_Template_Mgt`: True
  - `dog_kennels`: True
  - `employee_hire_evaluation`: True
