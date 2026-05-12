# Sample Queries per Benchmark

This appendix walks through one representative task from each of the six benchmarks, with the natural-language question, the schema slice that the closed-set planner saw, the gold SQL, our predicted SQL, and a note on what the example illustrates. The intent is to make the rest of the dossier's metric numbers concrete — every claim of the form "Phase 27 fixed cross-DB identifier drift" or "F4 wraps NUMBER/VARIANT date casts" should be visible in at least one of these examples.

Examples are selected for illustrative value, not for being "best case". One Spider 2.0 example is a failure; the failure mode is annotated.

## 1. Spider 1.0 — `concert_singer` database

**Question.** "Show the stadium name and the number of concerts held in each stadium."

**Schema slice (what the planner saw):**
```
TABLE stadium       (stadium_id INT PK, location TEXT, name TEXT, capacity INT, highest INT, lowest INT, average INT)
TABLE concert       (concert_id INT PK, concert_name TEXT, theme TEXT, stadium_id INT FK→stadium, year TEXT)
TABLE singer        (singer_id INT PK, name TEXT, country TEXT, song_name TEXT, song_release_year TEXT, age INT, is_male TEXT)
TABLE singer_in_concert (concert_id INT FK, singer_id INT FK)
```

**Gold SQL:**
```sql
SELECT T2.name, COUNT(*)
FROM concert AS T1
JOIN stadium AS T2 ON T1.stadium_id = T2.stadium_id
GROUP BY T1.stadium_id
```

**Our predicted SQL (Phase 22):**
```sql
SELECT s.name, COUNT(c.concert_id)
FROM stadium s
JOIN concert c ON s.stadium_id = c.stadium_id
GROUP BY s.stadium_id, s.name
```

**Illustrates.** Spider 1 EX equivalence under join-side reversal and alias-style differences. Both queries produce identical row sets; EX passes. The closed-set planner emitted the join in the opposite direction but the result is invariant. The extra `s.name` in the `GROUP BY` is required by some SQL dialects' strict modes but harmless in SQLite; the result-set comparison ignores it.

## 2. BIRD — `california_schools` database with evidence

**Question.** "What is the average SAT math score of all schools with the highest 5% of free or reduced-price meal rate?"

**Evidence row (passed verbatim to the planner):** "free-meal-rate = `FRPM Count (K-12)` / `Enrollment (K-12)`; top 5% = ORDER BY rate DESC LIMIT 5%."

**Schema slice:**
```
TABLE schools  (CDSCode TEXT PK, ...)
TABLE frpm     (CDSCode TEXT FK, `FRPM Count (K-12)` REAL, `Enrollment (K-12)` REAL, ...)
TABLE satscores (cds TEXT FK→schools.CDSCode, AvgScrMath REAL, ...)
```

**Gold SQL:**
```sql
SELECT AVG(T2.AvgScrMath)
FROM frpm AS T1
JOIN satscores AS T2 ON T1.CDSCode = T2.cds
WHERE T1.`FRPM Count (K-12)` * 1.0 / T1.`Enrollment (K-12)` >=
      (SELECT `FRPM Count (K-12)` * 1.0 / `Enrollment (K-12)`
       FROM frpm
       ORDER BY `FRPM Count (K-12)` * 1.0 / `Enrollment (K-12)` DESC
       LIMIT 1 OFFSET CAST(0.05 * (SELECT COUNT(*) FROM frpm) AS INT))
```

**Our predicted SQL (Phase 22):**
```sql
WITH ranked AS (
  SELECT CDSCode,
         (`FRPM Count (K-12)` * 1.0) / NULLIF(`Enrollment (K-12)`, 0) AS rate
  FROM frpm
),
top5pct AS (
  SELECT CDSCode FROM ranked
  ORDER BY rate DESC
  LIMIT (SELECT CAST(COUNT(*) * 0.05 AS INT) FROM ranked)
)
SELECT AVG(s.AvgScrMath)
FROM satscores s
JOIN top5pct t ON s.cds = t.CDSCode
```

**Illustrates.** BIRD's evidence-row usage. Without the evidence rendered as an instruction block (v9 prompt design), the planner does not produce the rate computation correctly. With the evidence block, the closed-set planner produces a CTE-style decomposition that is functionally equivalent to the gold's subquery decomposition. EX passes. The `NULLIF(..., 0)` defensive guard is something the planner adds without prompting and is harmless on this dataset.

## 3. Spider2-Lite-BQ — `bigquery-public-data.austin_311` task

**Question.** "Which complaint type had the steepest year-over-year growth between 2020 and 2022 in Austin's 311 service requests?"

**Schema slice:**
```
TABLE bigquery-public-data.austin_311.311_service_requests
  (unique_key STRING, complaint_type STRING, created_date TIMESTAMP, ...)
```

**Gold SQL (abridged):**
```sql
WITH yearly AS (
  SELECT complaint_type, EXTRACT(YEAR FROM created_date) AS yr, COUNT(*) AS cnt
  FROM `bigquery-public-data.austin_311.311_service_requests`
  WHERE EXTRACT(YEAR FROM created_date) BETWEEN 2020 AND 2022
  GROUP BY complaint_type, yr
),
deltas AS (
  SELECT complaint_type,
         MAX(IF(yr = 2022, cnt, 0)) AS y2022,
         MAX(IF(yr = 2020, cnt, 0)) AS y2020
  FROM yearly GROUP BY complaint_type
)
SELECT complaint_type, (y2022 - y2020) AS growth
FROM deltas
ORDER BY growth DESC LIMIT 1
```

**Our predicted SQL (Phase 22, exec_ok):**
```sql
WITH yearly AS (
  SELECT complaint_type, EXTRACT(YEAR FROM created_date) AS yr, COUNT(*) AS cnt
  FROM `bigquery-public-data.austin_311.311_service_requests`
  WHERE created_date BETWEEN '2020-01-01' AND '2022-12-31'
  GROUP BY 1, 2
)
SELECT complaint_type, (MAX(IF(yr = 2022, cnt, 0)) - MAX(IF(yr = 2020, cnt, 0))) AS growth
FROM yearly
GROUP BY complaint_type
ORDER BY growth DESC
LIMIT 1
```

**Illustrates.** BigQuery FQN handling (`project.dataset.table` in backticks) and the engine-compat boundary. Our SQL is one of the 30 % of Lite-BQ tasks that pass at Phase 22. The remaining 70 % typically fail on engine-compat constructs like `ARRAY_EXISTS` or multi-CTE chains that the planner emits in Snowflake style.

## 4. Spider2-Lite-Snow — pre-Phase 27 failure case

**Task ID.** sf_local_001, database `TPCH_SF1` on the Spider 2 Snowflake account.

**Question.** "List the top 5 nations by total revenue from lineitem in 1995."

**Schema slice (what Phase 26 planner saw):**
```
SCHEMA TPCH_SF1.PUBLIC
TABLE LINEITEM (L_ORDERKEY NUMBER, L_PARTKEY NUMBER, L_SUPPKEY NUMBER,
                L_EXTENDEDPRICE NUMBER, L_DISCOUNT NUMBER, L_SHIPDATE DATE, ...)
TABLE ORDERS   (O_ORDERKEY NUMBER, O_CUSTKEY NUMBER, O_ORDERDATE DATE, ...)
TABLE CUSTOMER (C_CUSTKEY NUMBER, C_NATIONKEY NUMBER, ...)
TABLE NATION   (N_NATIONKEY NUMBER, N_NAME VARCHAR, ...)
```

**Phase 26 predicted SQL (failed):**
```sql
SELECT N.N_NAME, SUM(L.L_EXTENDEDPRICE * (1 - L.L_DISCOUNT)) AS revenue
FROM LINEITEM L
JOIN ORDERS O ON L.L_ORDERKEY = O.O_ORDERKEY
JOIN CUSTOMER C ON O.O_CUSTKEY = C.C_CUSTKEY
JOIN NATION N ON C.C_NATIONKEY = N.N_NATIONKEY
WHERE EXTRACT(YEAR FROM L.L_SHIPDATE) = 1995
GROUP BY N.N_NAME
ORDER BY revenue DESC
LIMIT 5
```

**Why it failed pre-Phase 27.** The planner emitted unqualified table names. The validator did not catch this because the names did exist in *some* visible Snowflake database in the global BM25 index — they were bound to the wrong database at execution time, returning empty results that did not match gold.

**Phase 27 predicted SQL (exec_ok):**
```sql
SELECT N.N_NAME, SUM(L.L_EXTENDEDPRICE * (1 - L.L_DISCOUNT)) AS revenue
FROM TPCH_SF1.PUBLIC.LINEITEM L
JOIN TPCH_SF1.PUBLIC.ORDERS O ON L.L_ORDERKEY = O.O_ORDERKEY
JOIN TPCH_SF1.PUBLIC.CUSTOMER C ON O.O_CUSTKEY = C.C_CUSTKEY
JOIN TPCH_SF1.PUBLIC.NATION N ON C.C_NATIONKEY = N.N_NATIONKEY
WHERE EXTRACT(YEAR FROM L.L_SHIPDATE) = 1995
GROUP BY N.N_NAME
ORDER BY revenue DESC
LIMIT 5
```

**Illustrates.** The F1 grounding stack's contribution. The per-task BM25 partition now restricts retrieval to `TPCH_SF1`, the AST guard enforces three-part name rendering, and the identifier guard rejects any unqualified table name. The SQL is otherwise identical; the only difference is that every table reference is fully qualified.

## 5. Spider2-Snow — Phase 28 F4 wrap success

**Task ID.** sf_remote_017, database `WEATHER_DAILY_HISTORICAL`.

**Question.** "Find the average temperature per quarter for station ID 'USW00094728' between 2020 and 2024."

**Schema slice:**
```
SCHEMA WEATHER_DAILY_HISTORICAL.PUBLIC
TABLE DAILY_OBSERVATIONS (STATION VARCHAR, DATE_KEY NUMBER, TEMPERATURE_C FLOAT, ...)
```

Critical detail: `DATE_KEY` is stored as a `NUMBER` (YYYYMMDD encoded), not a Snowflake `DATE` type. Querying it with `DATE_TRUNC` directly is a runtime error.

**Phase 27 predicted SQL (failed at exec):**
```sql
SELECT DATE_TRUNC('QUARTER', DATE_KEY) AS quarter, AVG(TEMPERATURE_C)
FROM WEATHER_DAILY_HISTORICAL.PUBLIC.DAILY_OBSERVATIONS
WHERE STATION = 'USW00094728' AND DATE_KEY BETWEEN 20200101 AND 20241231
GROUP BY 1
ORDER BY 1
```

**Phase 28 predicted SQL (exec_ok after F4 wrap):**
```sql
SELECT DATE_TRUNC('QUARTER', TO_DATE(TO_CHAR(DATE_KEY), 'YYYYMMDD')) AS quarter,
       AVG(TEMPERATURE_C)
FROM WEATHER_DAILY_HISTORICAL.PUBLIC.DAILY_OBSERVATIONS
WHERE STATION = 'USW00094728' AND DATE_KEY BETWEEN 20200101 AND 20241231
GROUP BY 1
ORDER BY 1
```

**Illustrates.** The F4 NUMBER/VARIANT date-cast wrapper at work. The planner originally emitted `DATE_TRUNC('QUARTER', DATE_KEY)` because the schema description listed `DATE_KEY` without making its NUMBER encoding explicit. The F4 wrapper, walking the SQLGlot AST and finding a `TimestampTrunc` whose operand is a column typed `NUMBER`, inserts the `TO_DATE(TO_CHAR(...), 'YYYYMMDD')` cast wrapper. EX passes. The `wrapped_n` counter increments.

## 6. Spider2-DBT — ran_ok_but_score_zero example

**Task ID.** dbt_marketing_007.

**Question.** "Build a dbt model that aggregates customer lifetime value (CLV) per customer, materialised as a table."

**Existing staging models the task could `ref()`:** `stg_customers`, `stg_orders`, `stg_order_items`.

**Gold dbt model:**
```sql
{{ config(materialized='table') }}
SELECT
  c.customer_id,
  SUM(oi.quantity * oi.unit_price) AS lifetime_value
FROM {{ ref('stg_customers') }} c
JOIN {{ ref('stg_orders') }} o ON c.customer_id = o.customer_id
JOIN {{ ref('stg_order_items') }} oi ON o.order_id = oi.order_id
GROUP BY c.customer_id
```

**Our predicted dbt model (Phase 25, ran_ok_but_score_zero):**
```sql
{{ config(materialized='table') }}
SELECT
  c.customer_id,
  o.order_id,
  SUM(oi.quantity * oi.unit_price) AS lifetime_value
FROM {{ ref('stg_customers') }} c
JOIN {{ ref('stg_orders') }} o ON c.customer_id = o.customer_id
JOIN {{ ref('stg_order_items') }} oi ON o.order_id = oi.order_id
GROUP BY c.customer_id, o.order_id
```

**Illustrates.** A DBT failure mode that is *not* a SQL bug. The model compiles, dbt runs it, the output table has the right column types, but the rubric expects one row per customer and our model has one row per `(customer, order)` pair. The rubric scores zero. This is the "wrong aggregation level" sub-cause of *ran_ok_but_score_zero* (8 of 17 tasks in this band). Phase 31's rubric-feedback retry would surface the column-name expectation ("customer_id is unique in output") to the planner on a second pass, which the audit predicts would recover 10 of 17 tasks in this band. The example shows precisely the mechanism the Phase 31 plan targets.
