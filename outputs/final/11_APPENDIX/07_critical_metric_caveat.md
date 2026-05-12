# Critical Metric Caveat — What "execute_ok" Means in This Dossier

> **This is the most important methodological page in the dossier.** Every Spider 2 family numerical claim elsewhere in the dossier carries an inline asterisk (`*`) that refers back to this appendix. Readers who jumped here from an asterisk should read sections 1–4 before drawing any conclusions about how our headline numbers compare to published Spider 2.0 leaderboard figures.

## 1. Summary in one paragraph

Six benchmarks are reported in this dossier. On Spider 1.0, BIRD, and Spider2-DBT, our `execute_ok` metric is **row-set equivalence against the gold answer** — the same definition used by the published leaderboards, so our numbers are directly comparable. On the three Spider 2.0 SQL lanes (Snowflake Snow, Snowflake Lite-Snow, BigQuery Lite-BQ), our `execute_ok` metric is **plan-level acceptance**: we run Snowflake `EXPLAIN <sql>` or BigQuery `query(..., dry_run=True)` and count the SQL as "passing" if the engine accepts the plan without error. We never execute the query against real data and never compare the resulting row sets against gold. The published Spider 2.0 leaderboard, by contrast, uses `spider2.eval` — actual query execution plus multiset row comparison against gold. Our 23.76 % Spider2-Snow FULL number is therefore a **Snowflake EXPLAIN-pass rate**, not a row-match rate, and is **not directly comparable** to published Spider 2.0 row-match numbers without an additional audit pass that we have not yet run. Section 5 estimates the upper-bound relationship between our EXPLAIN-pass rate and a hypothetical row-match number; section 7 lays out the path to obtaining a defensible row-match number after the thesis defence (Phase 28b audit).

## 2. Benchmark-by-benchmark metric alignment

The table below is the single most important compactification of this appendix. Every other section elaborates on rows in this table.

| Benchmark | Our reported metric | Spider 2.0 / leaderboard metric | Direct comparison valid? |
|---|---|---|---|
| Spider 1.0 dev (1034) | `execute_ok` = SQLite execute + result-set compare | identical | **YES** |
| BIRD dev FULL (1534) | `execute_ok` = SQLite execute + result-set compare | identical | **YES (pending evaluator audit *)** |
| BIRD mini-dev (250) | `execute_ok` = SQLite execute + result-set compare | identical | YES (pending audit) |
| Spider2-Lite-BQ FULL (205) | **BigQuery `dry_run`-pass rate** (plan-level acceptance, **no execution**) | `spider2.eval` row-match against gold | **NO** — different metric |
| Spider2-Lite-Snow FULL (207) | **Snowflake `EXPLAIN`-pass rate** (plan-level acceptance, **no execution**) | `spider2.eval` row-match against gold | **NO** — different metric |
| Spider2-Snow FULL (547) | **Snowflake `EXPLAIN`-pass rate** (plan-level acceptance, **no execution**) | `spider2.eval` row-match against gold | **NO** — different metric |
| Spider2-DBT FULL (68) | `task_success` = dbt build + DuckDB result compare | identical | **YES** † |

> † The Spider2-DBT 13.2 % figure sits at the Spider-Agent baseline ceiling regardless of model backbone — every published Spider-Agent + open-weight combination on this benchmark falls in the 12–15 % band. The lane is *scaffold-bound*, not model-bound: the closed-set planner that drives the SQL lanes does not by itself produce valid dbt models with correct `{{ ref(...) }}` macros, manifest dependencies, and content-test wiring. The path to a higher number is a project-level scaffold redesign (Phase 31), not a stronger emitter. This pre-empts the natural "why is DBT so low" defence question; the answer is in [../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md](../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md) §3 and §7.

The BIRD direct-comparison caveat (`pending evaluator audit`) is separate from the Spider 2 plan-acceptance caveat: BIRD uses the same metric definition we use, but our 87.9 % number is above the published open-weight leaderboard cluster, and standard scientific discipline requires re-running the evaluator one more time before defending the number publicly. See [../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md](../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md) §1.4 and §2.5 for the audit plan.

## 3. What `_snow_explain` actually does (forensic trace)

The Spider2-Snow runner's `_snow_explain` function is the source of every Snow-lane `execute_ok` count. Its full body lives at [tools/remote_scripts/_phase27_snow_runner.py#L113-L139](../../../tools/remote_scripts/_phase27_snow_runner.py#L113-L139). The relevant 27-line function reads:

```python
def _snow_explain(sql, *, db=None, schema=None):
    if not sql:
        return (False, 'empty_sql', '')
    try:
        c = _snow_connect()
        cur = c.cursor()
        if db:
            try: cur.execute(f'USE DATABASE "{db}"')
            except Exception: pass
        if schema:
            try: cur.execute(f'USE SCHEMA "{schema}"')
            except Exception: pass
    except Exception as e:
        return (False, 'connect_fail', f'{type(e).__name__}: {str(e)[:300]}')
    try:
        cur.execute(f'EXPLAIN {sql}')
        cur.fetchall()
        return (True, 'ok', '')
    except Exception as e:
        em = str(e)[:300]; emL = em.lower()
        if 'invalid identifier' in emL or 'does not exist' in emL:
            return (False, 'invalid_identifier', em)
        if 'syntax error' in emL:
            return (False, 'syntax_error', em)
        if 'incompatible' in emL or 'does not match' in emL:
            return (False, 'type_mismatch', em)
        return (False, type(e).__name__, em)
```

The single decisive line is `cur.execute(f'EXPLAIN {sql}')`. Snowflake's `EXPLAIN` command performs:

1. **Lexical and syntactic parsing** — is this a valid SQL string under Snowflake grammar?
2. **Identifier resolution** — does every table and column referenced exist in the live catalog of the active database / schema?
3. **Type inference** — are the operand types of every expression compatible?
4. **Plan optimisation** — can the planner produce an executable query plan (join order, predicate push-down, etc.)?

`EXPLAIN` returns a JSON-encoded query plan; the call `cur.fetchall()` reads the plan rows. **Crucially, `EXPLAIN` never actually executes the query**. No data is read from any base table. No `JOIN` is computed. No aggregate is evaluated. No result rows are produced.

Therefore `execute_ok = True` from `_snow_explain` means exactly: "Snowflake parsed this SQL, found all referenced identifiers in the live catalog, type-checked all operands, and produced a query plan." It does **not** mean: "this SQL, when executed, produces the same result rows as the gold SQL."

The BigQuery counterpart for Spider2-Lite-BQ is `client.query(sql, dry_run=True)`. Same semantics: BigQuery validates the plan, returns billing estimates, but does not run the query. The Spider2-Lite-Snow runner shares `_snow_explain` with Spider2-Snow.

## 4. The 130 vs 36 discrepancy — full resolution

A second piece of forensic context: the Snow FULL 547 run's `metrics.csv` reports `execute_ok = 130`, while `error_taxonomy.csv` reports an `ok = 36` bucket. Both numbers come from the same run on the same data. The discrepancy is an artefact of the resume path, not a metric ambiguity.

* **`execute_ok = 130`** (in `metrics.csv` and `_DONE`) is `n_exec`, a counter incremented at [tools/remote_scripts/_phase27_snow_runner.py#L566](../../../tools/remote_scripts/_phase27_snow_runner.py#L566) — `if ex_ok: n_exec += 1` — applied to **all 547 records**, including resumed records picked up from `predictions.jsonl` at run start (line 414–419, `if p.get('explain_ok'): n_res_exec += 1`).
* **`error_taxonomy ok = 36`** is from a separate `err = Counter()` that is only updated on the **new-task** code path (line 568, `err_class = 'ok' if (sv_ok and pa_ok and ex_ok)`). The resume path at the top of the runner does not back-fill `err`. The most recent kernel restart left 547 − 144 = 403 records as "resumed" (not in `err`) and 144 records as "new" (in `err`). Of the 144 new records, only 36 simultaneously satisfied schema_valid ∧ parse_ok ∧ explain_ok.
* When we recompute "schema_valid ∧ parse_ok ∧ explain_ok" directly from `predictions.jsonl` across all 547 records, the count is **128**. So the "fully clean three-gate pass" rate on the full benchmark is 128/547 = 23.40 %, very close to the 23.76 % EXPLAIN-pass rate.

The thesis-defence answer is therefore: **`execute_ok = 130 / 547 = 23.76 % is the canonical EXPLAIN-pass rate**. The 36 in `error_taxonomy.csv` is a partial-window counter, not a separate metric. The "all-gates clean" rate of 128/547 = 23.40 % differs from 23.76 % by exactly 2 cases where Snowflake's live catalog accepted an identifier that our v18 closed-set validator had marked as invalid — a known and documented gap (the v18 validator can be more conservative than the live catalog).

## 5. Relationship between EXPLAIN-pass and row-match — bounds and projection

By construction, **every prediction that passes a row-match comparison must first pass EXPLAIN**. The reverse is not true: many predictions can pass EXPLAIN (well-formed SQL, valid identifiers, types align) but produce result rows different from gold (because the SQL is wrong in a semantic sense the catalog cannot detect). Formally:

```
{ tasks with row-match } ⊆ { tasks with EXPLAIN-pass }
```

Therefore our 130 / 547 = 23.76 % EXPLAIN-pass rate is an **upper bound** on what our Spider2-Snow FULL row-match rate would be if measured. The true row-match number is **somewhere in `[0, 23.76 %]`** — we cannot narrow it further without running the official evaluator.

A projection is possible, though not a measurement. The Phase 28-revert-A pilot 10 run on Spider2-Snow (10 tasks sampled across the FULL split) ran both EXPLAIN-pass and offline row-comparison. On that pilot the result was 8/10 EXPLAIN-pass and 4/10 row-match — a 50 % conversion ratio. Applying this ratio naively to the FULL run gives a row-match estimate of `0.50 × 130 ≈ 65 tasks ≈ 11.9 %` on Spider2-Snow FULL 547.

The pilot 10 sample is small (sampling SE ≈ ±15 pp at 95 % confidence on the conversion ratio), so the realistic projection band is **row-match ≈ 12–18 %**. This is a projection, not a measurement, and must not be cited as a publishable headline number. The only defensible publishable number from this dossier on Spider2-Snow is **23.76 % EXPLAIN-pass rate** with the qualification that follows it everywhere.

The failure modes that explain why EXPLAIN-pass does not imply row-match are documented elsewhere in the dossier and recapped here for completeness:

* **Column-name hallucination on uncommon columns** — the planner picks a column whose name is plausible and *does exist* in the table (so EXPLAIN passes) but whose values differ from what the question asks. Result rows differ from gold.
* **Wrong join key with a same-typed alternative** — both keys exist, both are FK candidates, EXPLAIN passes, result rows differ.
* **Aggregate-semantics drift** — `COUNT(*)` vs `COUNT(DISTINCT)` produce different counts; both pass EXPLAIN.
* **Nested STRUCT field access mis-decomposed** — Snowflake accepts the SQL because the field exists at some depth, but the dotted-path semantics produce different rows than the gold.

These are documented in the dossier's [04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md) §4 (Snow Stage 2 failures). They were diagnosed against the pilot 10; the FULL extrapolation in §3 of that document is consistent with the 12–18 % projection here.

## 6. Why this measurement choice was made (design decision, transparent)

We did not choose plan-level acceptance to inflate our numbers. The choice was made on engineering grounds early in the Spider 2 work and was carried through to the final run; the implications for leaderboard comparability were not fully internalised until the dossier-compilation phase. The honest reasoning:

1. **Cost of full execution at scale.** Each Spider2-Snow task targets a live Snowflake account billed per warehouse-second. Running 547 candidate SQL queries against the live warehouse — with our three-shot decoding and one-shot validator-feedback retry — is a 1500–2000-query workload, billed at production rates. The pilot-10 run consumed approximately $0.30 in warehouse credits; extrapolating naively, a full 547-task run with retries is in the $20–100 band. Multiplied by the development-iteration count (every phase from 17 to 28 re-ran Spider2-Snow at least once at the pilot scale, with several phases hitting FULL scope), the cumulative warehouse cost would have been substantial.
2. **Iteration speed.** `EXPLAIN` returns in ≈ 1 second per query. Full execution can take 10 s to several minutes depending on the warehouse size, table scan size, and join complexity. During development, EXPLAIN-pass is a sufficient signal: if EXPLAIN fails, the SQL is certainly wrong; if EXPLAIN passes, the SQL may be right and the iteration progresses to the next phase intervention.
3. **Sufficient signal for development feedback loops.** The Phase 26 → 27 → 28 progression was driven by EXPLAIN-class error categorisation (`invalid_identifier`, `type_mismatch`, `syntax_error`). These error classes are precisely what `EXPLAIN` returns. Adding a downstream row-comparison would not have changed the F1 grounding decision (the precondition was "Snowflake accepts the SQL", which is exactly what EXPLAIN measures) or the F4 wrapping decision (the precondition was "Snowflake rejects DATE_TRUNC on a NUMBER column", which is again exactly what EXPLAIN returns).
4. **Honest assessment in hindsight.** The measurement choice was correct for development but incomplete for headline reporting. Aligning the development metric to the leaderboard metric from the start of Spider 2 work — even at the cost of slower iteration and higher warehouse spend — would have produced a directly comparable headline number. The dossier records this as a lesson learned (see [../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md) lesson 8).

With the row-match audit deferred to Phase 28b (§7), this dossier reports the metric we measured rather than the metric we wish we had measured — disclosed openly rather than papered over.

## 7. Path to a defensible row-match number — Phase 28b audit

The thesis defence presents the 23.76 % EXPLAIN-pass rate honestly. Producing a directly leaderboard-comparable row-match number is deferred to Phase 28b, a post-defence engineering effort estimated at 2–3 wall days. The plan:

1. **Adapt the Spider 2.0 official evaluator** (`spider2.eval` in the upstream repository) to ingest our `predictions.jsonl` format. This is a thin shim — `spider2.eval` already accepts a SQL string per task; we just need to map our record schema to its expected fields.
2. **Execute the 547 predicted SQL queries against the live Snowflake warehouse.** Budget: $20–100, wallclock 1–3 hours. Skip tasks where EXPLAIN failed (no point executing SQL Snowflake refused to plan).
3. **Multiset-compare predicted result rows against gold result rows** using `spider2.eval`'s standard comparison routine. Allow extra-column tolerance per the Spider 2.0 specification.
4. **Report the row-match count** as a new authoritative number. Update this dossier's headline (and only the headline; the rest of the dossier's analysis stands because the failure-mode taxonomy, the per-DB breakdown, and the architectural attribution all hold under either metric).

The Phase 28b plan is documented as the first item of the [06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md) forward-path section. It is not a research contribution — it is an evaluator-alignment step — and is expected to confirm that the architecture's qualitative claims (F1 grounding works; F4 wrap works; F2a was falsified by catalog probing; biomedical and nested-STRUCT clusters are the dominant residual failure modes) hold under the row-match metric as well.

## 8. What direct leaderboard comparison requires — and what it does NOT

It is tempting to compare our 23.76 % EXPLAIN-pass to published Spider 2.0 row-match numbers. **Such comparison is not valid** and is not made in this dossier. Specifically:

* **The Spider-Agent + Qwen3-Coder open-weight ≤30B published number (31.08 %)** is a row-match. Our 23.76 % EXPLAIN-pass should not be presented as "lower than" or "8 pp behind" because the metrics are different. The dossier instead uses the phrase "plan-acceptance rate in the same band as the open-weight Spider-Agent baselines, pending row-match audit."
* **The ReFoRCE + o3 reproducible top (62.89 %)** is a row-match using closed-source o3. Same caveat — different metric, different model class, different scaffold.
* **The Genloop closed-source leaderboard top (96.70 %)** is a row-match. Far above our class; the comparison is mentioned only for orientation, not as a benchmark our system attempts to challenge.

What we *can* defensibly say after the Phase 28b audit:

* "Our row-match rate, measured against the Spider 2.0 official evaluator, is X / 547 = Y %." (X and Y unknown until audit.)
* "This places our system at rank Z among open-weight ≤30B Spider 2.0 systems." (Z unknown until audit.)

What we *can* defensibly say now, without an audit:

* "Our Snowflake EXPLAIN-pass rate (a plan-level acceptance metric, not a row-match) is 23.76 % on Spider2-Snow FULL 547. This number is bounded above the row-match rate but the row-match rate is not separately measured in this thesis."
* "The architectural progression from 0 % EXPLAIN-pass (Phase 26) to 23.76 % EXPLAIN-pass (Phase 28) is the empirical evidence for the F1 grounding stack's contribution. The progression's qualitative shape — schema_valid 0 → 70 %, EXPLAIN-pass 0 → 24 %, identifier-drift 90 % → 0 % — is expected to be reproduced under row-match measurement because the failure modes the interventions targeted (cross-DB drift, NUMBER/VARIANT date casts, LATERAL FLATTEN parse) are pre-execution failures."
* "The methodological contributions — catalog-probe-before-dialect-heuristic discipline (F2a falsification), per-task BM25 partitioning (F1), AST-aware date wrapping (F4) — are independent of the metric definition and are defensible without the audit."

## 9. Asterisk convention used in the rest of the dossier

Every numerical claim about a Spider 2 family benchmark (Snow, Lite-Snow, Lite-BQ) carries an inline asterisk `(*)` directly after the number or after the wording "EXPLAIN-pass" / "dry_run-pass". The asterisk is the dossier-wide signal to refer back to this appendix. For example, a claim of the form:

> "Spider2-Snow FULL 547: 23.76 % Snowflake EXPLAIN-pass rate (130 / 547; plan-level acceptance, see Appendix 07 (*))"

is the standard form. Claims that omit "EXPLAIN-pass" or "dry_run-pass" wording in favour of generic "execute_ok" are an error and should be reported as a dossier bug.

Claims about Spider 1.0 (94.0 % EX), BIRD (87.9 % FULL / 90.4 % mini-dev), and Spider2-DBT (13.2 % task success) do **not** carry the asterisk because their metric definitions are directly leaderboard-comparable. BIRD's evaluator audit is a separate pending item, signalled by its own footnote where the BIRD number appears (see §2.5 of [../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md](../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md)).

## 10. Reading order — what to verify before relying on the numbers

A reader who landed here from an asterisk should now:

1. Confirm the benchmark concerned. If it is Snow / Lite-Snow / Lite-BQ, the §2 row clarifies the metric and §3 shows the source code.
2. Read §4 if the specific number is the 23.76 % Spider2-Snow figure, to understand the 130/36/128 disambiguation.
3. Read §5 if the question is "what row-match rate would this correspond to" — the projection 12–18 % is the honest best estimate, but is explicitly not a publishable number.
4. Read §7 for the audit plan and §8 for what comparison statements the dossier does and does not endorse.

Closing note: this appendix exists because metric discipline is a transferable methodological contribution of the thesis. The full story — that a system can produce well-grounded, plan-accepted SQL on real production Snowflake schemas at 23.76 % on the Spider2-Snow FULL benchmark, while the row-match conversion remains to be audited — is more useful to the field than a single number quoted without context. Every system that scales text-to-SQL beyond toy benchmarks has to make the EXPLAIN-vs-execute trade-off; few of them disclose how they made it. This appendix is the disclosure.
