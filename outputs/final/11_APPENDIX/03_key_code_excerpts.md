# Key Code Excerpts

This appendix collects the short code blocks that are most load-bearing for the dossier's technical claims. Each excerpt is presented with the source-file path, a brief setup paragraph, the code itself (typically 10–40 LOC), and a few sentences of commentary on what it shows. The intent is that a reader can verify the dossier's architectural claims by reading ~150 LOC across this appendix without having to navigate the full codebase.

Code excerpts are stable as of commit `ad5493b` (Phase 28 closure). Future phases will introduce additional modules but should not invalidate the excerpts below.

## 1. F1 identifier guard — three-part name enforcement

**Source.** `repo/src/evaluation/snow_identifier_guard_v27.py`.

**Setup.** The F1 guard takes a SQL string and a per-task allow-set of `(database, schema, table)` triples derived from the closed-set planner's pick. Its job is to ensure every table reference in the SQL is fully qualified and lives in the allow-set. If SQLGlot parses the SQL, the guard walks the AST; if SQLGlot fails (e.g. on LATERAL FLATTEN), it falls back to a regex pass (F4c).

```python
import sqlglot
from sqlglot import exp

def enforce_three_part(sql: str, allow_set: set[tuple[str, str, str]]) -> tuple[str, dict]:
    """Returns (rewritten_sql, stats). Stats include 'rewritten_n' and 'rejected_n'."""
    stats = {"rewritten_n": 0, "rejected_n": 0, "parse_ok": False}
    try:
        tree = sqlglot.parse_one(sql, read="snowflake")
        stats["parse_ok"] = True
    except Exception:
        return regex_fallback_enforce(sql, allow_set, stats)

    for table in tree.find_all(exp.Table):
        db = (table.args.get("catalog") or exp.Identifier(this="")).name
        sch = (table.args.get("db") or exp.Identifier(this="")).name
        tbl = table.name
        triple = (db.upper(), sch.upper(), tbl.upper())
        if triple in allow_set:
            continue
        # try to attach the canonical (db, schema) from the allow_set if tbl matches
        match = next((t for t in allow_set if t[2] == tbl.upper()), None)
        if match is not None:
            table.set("catalog", exp.Identifier(this=match[0]))
            table.set("db", exp.Identifier(this=match[1]))
            stats["rewritten_n"] += 1
        else:
            stats["rejected_n"] += 1
    return tree.sql(dialect="snowflake"), stats
```

**Commentary.** This is the load-bearing snippet for the Phase 27 grounding claim. The guard either rewrites a partially-qualified table reference to its canonical three-part form, or rejects the SQL outright if the table is not in the allow-set. The `parse_ok=False` branch routes to the F4c regex fallback. The `(db, schema, table)` triple is computed in `.upper()` form because Snowflake identifiers are case-insensitive when unquoted; this is the same casing convention the BM25 partition uses.

## 2. F4 NUMBER/VARIANT date-cast wrapper

**Source.** `repo/src/evaluation/snow_dialect_fixer_v28.py`.

**Setup.** The F4 wrapper finds calls to date-trunc-family functions whose operand is a column declared as `NUMBER` or `VARIANT` in the closed-set schema pack, and inserts a `TO_DATE(TO_CHAR(...), 'YYYYMMDD')` cast around the operand.

```python
import sqlglot
from sqlglot import exp

# date functions whose first arg should be a DATE/TIMESTAMP
DATE_FN_TYPES = (exp.DateTrunc, exp.Extract)
if hasattr(exp, "TimestampTrunc"):
    DATE_FN_TYPES = DATE_FN_TYPES + (exp.TimestampTrunc,)  # Phase 28 discovery

def wrap_number_date_args(sql: str, number_cols: set[str]) -> tuple[str, int]:
    """Wraps NUMBER columns inside date functions with TO_DATE(TO_CHAR(...), 'YYYYMMDD').
    Returns (rewritten_sql, wrapped_n)."""
    try:
        tree = sqlglot.parse_one(sql, read="snowflake")
    except Exception:
        return sql, 0

    wrapped_n = 0
    for node in tree.find_all(*DATE_FN_TYPES):
        # operand to wrap differs by function shape — for DateTrunc/TimestampTrunc the date arg is `this`
        operand = node.this if isinstance(node, (exp.DateTrunc, exp.TimestampTrunc)) else node.args.get("expression")
        if operand is None or not isinstance(operand, exp.Column):
            continue
        col_key = operand.name.upper()
        if col_key not in number_cols:
            continue
        wrapper = exp.func("TO_DATE",
                           exp.func("TO_CHAR", operand.copy()),
                           exp.Literal.string("YYYYMMDD"))
        operand.replace(wrapper)
        wrapped_n += 1
    return tree.sql(dialect="snowflake"), wrapped_n
```

**Commentary.** The `hasattr(exp, "TimestampTrunc")` guard is the Phase 28 discovery — in SQLGlot 25.16.x's snowflake dialect, `DATE_TRUNC` parses as `exp.TimestampTrunc`, not `exp.DateTrunc`. Without this check, the F4 wrapper would silently skip every Snowflake `DATE_TRUNC` call. The wrapper's behaviour is gated by `number_cols` (the set of column names typed as NUMBER in the schema pack), so it does not falsely wrap legitimate `DATE` operands.

## 3. Per-task BM25 partition

**Source.** `repo/src/evaluation/schema_linking_v18.py`.

**Setup.** The schema linker maintains a global index of (table, column) tokens across all visible Snowflake databases. The Phase 27 F1 partition restricts retrieval to a single task's database before BM25 scoring.

```python
from rank_bm25 import BM25Okapi

class SchemaLinker:
    def __init__(self, all_columns: list[ColRec]):
        self._index_by_db = {}
        for c in all_columns:
            db = c.db.upper()
            self._index_by_db.setdefault(db, []).append(c)
        # build BM25 indices lazily per db
        self._bm25_by_db = {}

    def _get_bm25(self, db: str) -> tuple[BM25Okapi, list[ColRec]]:
        if db not in self._bm25_by_db:
            cols = self._index_by_db[db]
            tokens = [self._tokenize(c.full_path()) for c in cols]
            self._bm25_by_db[db] = (BM25Okapi(tokens), cols)
        return self._bm25_by_db[db]

    def retrieve(self, query: str, db: str, top_k_tables: int = 200, top_k_cols: int = 40):
        bm25, cols = self._get_bm25(db.upper())
        scores = bm25.get_scores(self._tokenize(query))
        ranked = sorted(zip(scores, cols), reverse=True)
        # ... post-filtering and PK/FK injection elided for brevity ...
        return ranked[:top_k_cols]
```

**Commentary.** Before Phase 27, the index was global — `BM25Okapi(tokens)` was built once over all columns across all databases. A task whose database was `TPCH_SF1` could retrieve columns from `SNOWFLAKE_SAMPLE_DATA` because tokens matched. The per-task partition keyed by `c.db.upper()` is the load-bearing fix: each task now retrieves only from its own database's column set. The retrieval scaling from `top_k_tables=80, top_k_cols=20` (Phase 26) to `200, 40` (Phase 27) was a secondary tuning needed because the per-DB indices are smaller — the absolute retrieval count had to grow to maintain effective recall.

## 4. Resume scaffolding — append + periodic flush

**Source.** `tools/remote_scripts/_phase27_snow_runner.py`.

**Setup.** Long-running Spider2-Snow FULL runs (≥ 3 hours) need to survive Drive FUSE sync delays and intermittent kernel deaths. The pattern is: open the predictions file in append mode, write each prediction immediately on completion, close and reopen the file every N tasks to force the FUSE writeback.

```python
import jsonlines
from pathlib import Path

PREDS_PATH = Path(OUTPUT_DIR) / "predictions.jsonl"
FLUSH_EVERY = 10

def load_done_iids() -> set[str]:
    if not PREDS_PATH.exists():
        return set()
    with jsonlines.open(PREDS_PATH) as r:
        return {row["iid"] for row in r if "iid" in row}

def run_all(tasks: list[Task]):
    done = load_done_iids()
    pending = [t for t in tasks if t.iid not in done]
    pf = jsonlines.open(PREDS_PATH, mode="a")
    try:
        for i, t in enumerate(pending, 1):
            pred = run_one(t)
            pf.write(pred)
            if i % FLUSH_EVERY == 0:
                pf.close()
                pf = jsonlines.open(PREDS_PATH, mode="a")  # force FUSE flush
                heartbeat(i, len(pending))
    finally:
        pf.close()
```

**Commentary.** The `load_done_iids()` pass at startup is what makes the runner resumable — on a kernel restart, all previously-predicted task IDs are skipped and the runner picks up at the next pending task. The `pf.close() + reopen` every 10 tasks is the Drive FUSE fix from the Phase 28 closure incident (79 tasks lost when kernel died with unflushed buffer). The pattern adds ≤ 50 ms per 10-task batch, negligible against the per-task inference cost of ≈ 15–30 seconds.

## 5. Validator-feedback retry

**Source.** `repo/src/pipeline/retry_loop.py`.

**Setup.** When the validator rejects a SQL, we re-prompt the emitter with the validator's error rendered as a natural-language hint. The retry budget is one shot per task.

```python
def emit_with_retry(planner_pick: PlannerPick, max_retries: int = 1) -> EmitResult:
    sql = emitter.generate(prompt_from(planner_pick))
    for attempt in range(max_retries):
        result = validate(sql, planner_pick.schema_pack)
        if result.ok:
            return EmitResult(sql=sql, retries=attempt, validator_ok=True)
        hint = render_validator_error_as_hint(result.error)
        sql = emitter.generate(prompt_from(planner_pick, retry_hint=hint))
    final_result = validate(sql, planner_pick.schema_pack)
    return EmitResult(sql=sql, retries=max_retries, validator_ok=final_result.ok)
```

**Commentary.** The retry budget is intentionally tight (one shot). The audit at Phase 14 measured retry-rate effectiveness: 70 % of recoverable failures recovered on shot 1, an additional 9 % on shot 2, an additional 3 % on shot 3, with diminishing returns thereafter. Given the inference cost per shot is substantial, we settled on one retry. The validator-error-to-hint renderer (`render_validator_error_as_hint`) is itself a small but interesting component: it translates SQLGlot error codes into natural-language descriptions that the emitter understands.

## 6. Closed-set candidate selector

**Source.** `repo/src/evaluation/candidate_selector_v18.py`.

**Setup.** After schema linking returns 40 candidate columns, the candidate selector groups them into "families" (one per plausible interpretation of the question) and picks the top family by joint plausibility score. The selector's output is what the planner sees as the table/column menu.

```python
def select_candidates(cols: list[ColRec], question: str) -> CandidateSet:
    by_table = defaultdict(list)
    for c in cols:
        by_table[c.table_full].append(c)

    # Family A: top-1 table only
    # Family B: top-1 + top-2 tables joined on inferred PK/FK
    # Family C: explicit join hint family (added Phase 22 A3)
    families = [
        Family("A", list(by_table.values())[0]),
        Family("B", merged_top_two(by_table)),
        Family("C", joined_with_hints(by_table, question)) if has_join_keywords(question) else None,
    ]
    families = [f for f in families if f is not None]
    return max(families, key=lambda f: f.score(question))
```

**Commentary.** The Family-A/B/C selector is the core of the closed-set planner. The Phase 22 audit found that Family C was almost never picked (≤ 5 % of tasks); even when explicit join keywords were present, Family B's score usually dominated. This is a known issue we have not closed — the Family C scoring weights need re-tuning. The Phase 28 closure deferred this to Phase 29.

## 7. Bridge `/exec` endpoint

**Source.** `tools/remote_scripts/bridge.py` (Colab-side).

**Setup.** The bridge exposes a Python `exec` endpoint over Cloudflare Tunnel. The agent posts code, the bridge runs it in `_SHARED_GLOBALS`, and returns stdout/stderr.

```python
_SHARED_GLOBALS = {}

@app.route("/exec", methods=["POST"])
def exec_endpoint():
    code = request.json["code"]
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            exec(code, _SHARED_GLOBALS)
    except Exception as e:
        err.write(traceback.format_exc())
    return jsonify({"stdout": out.getvalue(), "stderr": err.getvalue()})
```

**Commentary.** `_SHARED_GLOBALS` (not `__main__.__dict__`) is the indirection that caused the "models missing from `__main__`" recovery incident. The fix was the alias mapping in the bringup memory file's §3 (e.g. `_TOK_PLAN = tok_a` placed into `_SHARED_GLOBALS`). The exec endpoint is intentionally minimal — there is no command sandboxing, no rate limiting, no auth (the Cloudflare Tunnel's URL is the only access control). This is acceptable for a single-user research deployment but would not be production-safe.
