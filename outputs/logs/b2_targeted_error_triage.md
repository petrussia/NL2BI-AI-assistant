# B2 targeted error triage
_Generated: 2026-04-30T12:12:20.023898+00:00_

## Failure category counts
| source | category | count |
|---|---|---|
| B2_v0 | correct | 7 |
| B2_v0 | result_mismatch_other | 2 |
| B2_v0 | sql_invalid | 1 |
| B2_v1 | correct | 6 |
| B2_v1 | missing_order_by | 1 |
| B2_v1 | result_mismatch_other | 1 |
| B2_v1 | sql_invalid | 2 |

## Per-item failed cases (B2_v0)

### idx=6 db=concert_singer category=result_mismatch_other
**Q:** Show the name and the release year of the song by the youngest singer.
**Gold:** `SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1`
**Gen:** `SELECT Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`
**Why:** intent=

### idx=7 db=concert_singer category=result_mismatch_other
**Q:** What are the names and release years for all the songs of the youngest singer?
**Gold:** `SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1`
**Gen:** `SELECT Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;`
**Why:** intent=

### idx=8 db=concert_singer category=sql_invalid
**Q:** What are all distinct countries where singers above age 20 are from?
**Gold:** `SELECT DISTINCT country FROM singer WHERE age  >  20`
**Gen:** ``
**Why:** plan_invalid


## Per-item failed cases (B2_v1)

### idx=6 db=concert_singer category=missing_order_by
**Q:** Show the name and the release year of the song by the youngest singer.
**Gold:** `SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1`
**Gen:** `SELECT Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);`
**Why:** gold has ORDER BY, gen does not

### idx=7 db=concert_singer category=result_mismatch_other
**Q:** What are the names and release years for all the songs of the youngest singer?
**Gold:** `SELECT song_name ,  song_release_year FROM singer ORDER BY age LIMIT 1`
**Gen:** `SELECT Name, Song_release_year FROM singer WHERE Singer_ID = (SELECT Singer_ID FROM singer ORDER BY Age ASC LIMIT 1);`
**Why:** intent=

### idx=8 db=concert_singer category=sql_invalid
**Q:** What are all distinct countries where singers above age 20 are from?
**Gold:** `SELECT DISTINCT country FROM singer WHERE age  >  20`
**Gen:** ``
**Why:** plan_invalid

### idx=9 db=concert_singer category=sql_invalid
**Q:** What are  the different countries with singers above age 20?
**Gold:** `SELECT DISTINCT country FROM singer WHERE age  >  20`
**Gen:** ``
**Why:** plan_invalid

## Hypotheses for B2_v2 (minimal targeted patches)

1. **Strengthen DISTINCT prompt cue.** When the question contains words like
   "distinct", "different", "unique", "all the X" (set semantics), the planner
   must mark `distinct: true`. Currently this is implied; make it explicit
   and add 1–2 in-context positive examples.
2. **Strengthen subquery filter cue.** Questions like "the youngest", "the
   tallest", "the X with the highest Y" need a subquery in WHERE
   (`(SELECT MIN(...) FROM T)`). Make the planner emit this pattern
   explicitly when it sees a superlative.
3. **B1 fallback on plan failure.** Same trick as B3_v2 / B4_v2: if the plan
   is invalid, fall back to B1 single-shot. This guarantees
   `EX(B2_v2) >= EX(B1) - sql_noise`.
4. **Ban over-engineering.** When the question is a simple SELECT-FROM-WHERE
   without aggregation, ordering, limit, or subqueries — the planner often
   adds spurious GROUP BY or ORDER BY because the prompt mentions them as
   options. Add a short instruction: "Use the simplest plan that satisfies
   the question; do not add operations not requested."

## Decision
Apply hypotheses 1–4 in `baselines_b2_v2.py`, then run B2_v2 smoke_10 + multidb_30.
Stop if delta < +0.03 EX vs B2_v1 — the planner direction is exhausted on
this benchmark and the right answer is "use B0/B1, keep B2_v2 as a safety
net only when an external system requires the plan as an audit trail".
