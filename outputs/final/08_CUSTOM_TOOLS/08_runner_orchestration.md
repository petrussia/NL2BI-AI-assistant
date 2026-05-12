# 08.08 — Runner Orchestration (tools/remote_scripts/_phase*_*.py)

## Покрытие модулей

`tools/remote_scripts/_phase*_*.py` — orchestration layer соединяющий все вышеописанные modules в работающий pipeline. На разных фазах эксперимента — разные runner-ы. Текущий primary runner:

| File | LOC | Purpose | Status |
|---|---|---|---|
| `tools/remote_scripts/_phase27_snow_runner.py` | ~620 | Snow + Lite-Snow FULL runner с Phase 27 F1 + Phase 28 F4/F4c | **active** (commit `ad5493b`) |
| `tools/remote_scripts/_phase25_load_models.py` | ~58 | Model bootstrap (load planner + emitter в kernel) | bootstrap |
| `tools/_invoke_remote.py` | ~24 | Local-to-Colab bridge HTTP helper | utility |
| `tools/_upload_runner_both.py` | ~24 | Upload runner to S1+S2 kernels | utility |
| `tools/_send_phase28_*.py` | varies | Phase 28 specific helpers (bringup, smoke, repair) | utility |

И многие diagnostic / probe scripts:

| File | Purpose |
|---|---|
| `_phase27_step1_diagnostic.py` | Cross-DB drift baseline measurement |
| `_phase27_sanity_pack_build.py` | F1 catalog filter integration test |
| `_phase27_probe_pilot10c.py` | Run-state probe |
| `_phase27_pull_pilot10c.py` | Predictions + traces pull |
| `_phase28_catalog_case_probe.py` | Catalog case distribution probe (F2a-falsifying tool) |
| `_phase28_s1_fix_snowflake.py` | Snowflake env restoration + connect_fail cleanup |
| `_phase28_s2_load_models_bg.py` | Background model loader (kernel restart recovery) |
| `_phase28_s1_lite_supervisor.py` / `_phase28_s1_supervisor_v2.py` | Auto Snow→Lite handoff |
| `_phase28_full_heartbeat.py` / `_phase28_full_verify_stack.py` | Status / sanity checks |

## Главный runner: `_phase27_snow_runner.py`

### Macro structure (~620 LOC)

```
1.  Imports + DRV path constant
2.  _gen / _gen_planner — model inference wrappers
3.  _extract_sql — SQL extraction from emitter output
4.  _snow_connect / _snow_explain — Snowflake engine validator
5.  _snow_schema_valid_ast — AST validator (Phase 27 relaxed)
6.  _snow_parse_ok — SQLGlot parse check
7.  _snow_direct_prompt — emitter prompt builder (Phase 28 col:TYPE + cast rules)
8.  _inject_pk_fk — PK/FK heuristic injection (Phase 27 correction 3)
9.  _v18_plan — planner с feedback retry
10. _run_phase27_snow — главный loop (per-task processing)
11. _upload_modules_to_drive — module sync helper
12. Bottom: registers helpers in globals + prints PHASE27_SNOW_RUNNER_REGISTERED
```

### Code walkthrough

#### Excerpt 1 — Main loop skeleton (`_run_phase27_snow`, lines 318-410)

```python
def _run_phase27_snow(run_id, jsonl_path, *, alias_filter_set=None,
                      instance_ids_set=None,
                      limit=None, out_subdir='spider2_snow'):
    """Phase 27 STAGE F1 Snow runner."""
    import importlib
    # Reload modules — pickup latest Drive versions
    for mod in ['schema_linking_v18', 'schema_pack_builder_v18',
                'structured_plan_v18', 'snow_identifier_guard_v27',
                'snow_dialect_fixer_v28']:
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    import schema_linking_v18 as sl
    import schema_pack_builder_v18 as sb
    import structured_plan_v18 as sp
    import snow_identifier_guard_v27 as guard
    try:
        import snow_dialect_fixer_v28 as fixer
    except Exception:
        fixer = None

    out_dir = DRV / 'outputs' / out_subdir / 'runs' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / '_STARTED').write_text(json.dumps({
        'run_id': run_id, 'phase': 27, 'mode': 'F1_snow', 'ts': time.time()}))

    # Pre-load entire catalog
    cat_path = DRV / 'outputs/cache/spider2_snow_live_catalog_v18.jsonl'
    full_catalog = sl.load_catalog_jsonl(cat_path, 'snow')

    # Phase 27 F1: partition catalog by db (uppercase) для fast per-task subset retrieval
    cat_by_db = defaultdict(list)
    for c in full_catalog:
        cat_by_db[c.db.upper()].append(c)

    # Load tasks
    tasks = []
    with open(jsonl_path, encoding='utf-8') as fh:
        for ln in fh:
            t = json.loads(ln)
            alias = t.get('db') or t.get('db_id') or ''
            if alias_filter_set is not None and alias not in alias_filter_set:
                continue
            if instance_ids_set is not None and t.get('instance_id') not in instance_ids_set:
                continue
            tasks.append(t)
    if limit: tasks = tasks[:limit]
```

**Что критично**:
- **Reload modules** на старте (lines 333-337). Pulls latest Drive versions of pipeline modules. **Важно после code edits**: developer edits локально, uploads to Drive, runner reloads — picks up changes без kernel restart.
- **`fixer = None` если import fails** (lines 343-345). Allows running без `snow_dialect_fixer_v28` (e.g., Phase 27-era code on which Phase 28 wasn't deployed yet).
- **Catalog partition** (lines 351-355): one-shot operation на kernel session. 587K rows partitioned in seconds; subsequent per-task lookups O(1).
- **`alias_filter_set` + `instance_ids_set`**: optional subset filters. Used для pilot runs (specific 10 iids) or lane subsetting (only certain db_id values).

#### Excerpt 2 — Resume scaffolding (Phase 28 hardening, lines 401-450)

```python
# Resume from kernel death — scan existing files in run dir for
# already-completed iids. Operational scaffolding only; pipeline modules
# are frozen at v28-revert-A.
done_iids = set()
n_res_sv = n_res_parse = n_res_exec = n_res_plan = 0
pf_path = out_dir / 'predictions.jsonl'
tf_path = out_dir / 'traces.jsonl'
if pf_path.exists():
    with open(pf_path, encoding='utf-8') as f:
        for ln in f:
            if not ln.strip(): continue
            try:
                p = json.loads(ln)
                iid = p.get('instance_id')
                if iid:
                    done_iids.add(iid)
                    if p.get('explain_ok'): n_res_exec += 1
                    if p.get('schema_valid'): n_res_sv += 1
                    if p.get('parse_ok'): n_res_parse += 1
            except Exception:
                pass
if tf_path.exists():
    with open(tf_path, encoding='utf-8') as f:
        for ln in f:
            try:
                if json.loads(ln).get('plan_ok'): n_res_plan += 1
            except Exception: pass

before_resume = len(tasks)
tasks = [t for t in tasks if t.get('instance_id') not in done_iids]
if done_iids:
    print(f'[{run_id}] RESUMED: {len(done_iids)} prior done '
          f'(sv={n_res_sv} parse={n_res_parse} exec={n_res_exec} plan={n_res_plan}), '
          f'{before_resume - len(tasks)} skipped, {len(tasks)} remaining',
          flush=True)

# Append, not overwrite — preserves prior task records on resume
pf = open(out_dir / 'predictions.jsonl', 'a', encoding='utf-8')
tf = open(out_dir / 'traces.jsonl', 'a', encoding='utf-8')
```

**Что критично**: critical Phase 28 hardening — без resume scaffolding каждый restart kernel-я начинал с нуля, теряя hours of compute. Reading existing predictions.jsonl + filtering done iids + opening in append mode — standard resume pattern.

#### Excerpt 3 — Per-task loop body (lines 410-490)

```python
for task in tasks:
    n += 1
    tid = task.get('instance_id') or f't{n}'
    task_db = (task.get('db') or task.get('db_id') or '').upper()
    question = task.get('question') or task.get('instruction') or ''
    ek = task.get('external_knowledge') or ''
    trace = {'instance_id': tid, 'task_db': task_db}
    try:
        # Per-task catalog subset (Phase 27 F1)
        cat_subset = cat_by_db.get(task_db, [])
        if not cat_subset:
            err['no_catalog_for_task_db'] += 1
            # ... write skip record ...
            continue
        
        # Per-task BM25 index
        linker = sl.SchemaLinker(cat_subset)
        link = linker.query(question, db_filter=task_db,
                              top_columns=200, top_tables=40)
        pack = sb.build_pack(link, lane='snow', alias=task_db,
                              max_tables=10, max_cols_per_table=22,
                              all_catalog_cols=cat_subset)
        n_pk_fk = _inject_pk_fk(pack, cat_subset)
        
        # Planner
        plan_prompt = sb.pack_to_planner_prompt(pack, question, external_knowledge=ek)
        pr = _v18_plan(plan_prompt, pack)
        if pr.get('validation') and getattr(pr['validation'], 'ok', False):
            n_plan_ok += 1
        trace['plan_ok'] = bool(pr.get('validation') and getattr(pr['validation'], 'ok', False))
        
        # Emitter
        emit_prompt = _snow_direct_prompt(question, pack, ek)
        sql_raw = _gen(emit_prompt, max_new=900)
        sql = _extract_sql(sql_raw)
        
        # F1 AST guard (Phase 27 + Phase 28 F4c fallback)
        try:
            sql_fixed, guard_info = guard.guard_and_fix_snow_sql(sql, task_db)
            sql = sql_fixed
        except guard.IdentifierLeakError as e:
            # ... record + continue ...
        
        # Phase 28 F4 wrap (если fixer available)
        if fixer is not None:
            col_types = {(c.field_path or c.column or '').upper(): (c.data_type or '')
                          for c in cat_subset if c.field_path or c.column}
            sql_b, info_b = fixer.wrap_date_fn_on_nondate(sql, col_types)
            sql = sql_b
            n_wrapped += info_b.get('wrapped_n', 0)
        
        # Validators + EXPLAIN
        task_db_all_cols = {(c.field_path or c.column) for c in cat_subset
                              if (c.field_path or c.column)}
        sv_ok, sv_msg = _snow_schema_valid_ast(sql, pack, extra_allowed_cols=task_db_all_cols)
        pa_ok, pa_msg = _snow_parse_ok(sql)
        if sv_ok: n_sv += 1
        if pa_ok: n_parse += 1
        
        if pa_ok:
            ex_ok, ex_class, ex_msg = _snow_explain(
                sql, db=top_t['db'] if top_t else None,
                schema=top_t['schema'] if top_t else None,
            )
        else:
            ex_ok, ex_class, ex_msg = False, 'parse_error', pa_msg
        if ex_ok: n_exec += 1
        
        # Write trace + predictions
        pf.write(json.dumps({...}) + '\n'); pf.flush()
        tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()
    
    except Exception as e:
        # ... record exception ...
```

**Что критично**:
- **Per-task isolation**: each task wrapped в `try/except`. One task's exception не crashes whole run.
- **Counter increments + writes interleaved**: progress.json updates после each task (см. line 560+).
- **`pf.flush()` after every write**: ensures intermediate state persists.
- **Phase 28 F4 conditional gating** (lines 472-481): only if `fixer is not None` — graceful degradation.

#### Excerpt 4 — Periodic flush (Phase 28 hardening, lines 547-560)

```python
if n % 5 == 0:
    try:
        import torch; gc.collect(); torch.cuda.empty_cache()
    except Exception: pass

# Phase 28 FULL hardening: periodic close+reopen of preds/traces every
# 10 tasks forces Drive FUSE to sync to cloud. Without this, the file
# stays open for hours and Drive accumulates writes locally; if the
# kernel dies the cloud-side .jsonl ends up far behind n_total.
if n % 10 == 0:
    try:
        pf.close(); tf.close()
        pf = open(out_dir / 'predictions.jsonl', 'a', encoding='utf-8')
        tf = open(out_dir / 'traces.jsonl', 'a', encoding='utf-8')
    except Exception as _e:
        print(f'[{run_id}] file sync reopen failed at n={n}: {_e}', flush=True)
```

**Что критично**: **Drive FUSE quirk** — Colab's `/content/drive` mount caches appended writes locally; cloud Drive не updates до file close. Phase 28 incident на S2: kernel died at task 119 in-memory, but Drive cloud had only 40 entries — 79 lost. Fix: periodic close+reopen forces sync.

## Bootstrap script: `_phase25_load_models.py`

```python
"""Phase 25 — load planner (Qwen3-Coder-30B-A3B) + emitter (Coder-7B)
into the bridge kernel globals for downstream runners.
Idempotent. Re-run safely: skips if _V18_MODELS_READY=True.
"""
import os, sys, time
DRV = '/content/drive/MyDrive/diploma_plan_sql'
EVAL = DRV + '/repo/src/evaluation'
if EVAL not in sys.path: sys.path.insert(0, EVAL)

g = globals()
if g.get('_V18_MODELS_READY'):
    print('MODELS_ALREADY_READY')
else:
    if not os.environ.get('HF_TOKEN'):
        # Load HF_TOKEN from Drive secrets
        ...
    
    import importlib
    if 'model_registry_v17' in sys.modules:
        importlib.reload(sys.modules['model_registry_v17'])
    from model_registry_v17 import load_model_and_tokenizer

    EMIT_ALIAS = 'qwen2_5_coder_7b'
    PLAN_ALIAS = 'qwen3_coder_30b_bf16'

    tok_b, mdl_b, prof_b = load_model_and_tokenizer(EMIT_ALIAS)
    g['_TOK_EMIT'] = tok_b; g['_MDL_EMIT'] = mdl_b; g['_PROF_EMIT'] = prof_b

    tok_a, mdl_a, prof_a = load_model_and_tokenizer(PLAN_ALIAS)
    g['_TOK_PLAN'] = tok_a; g['_MDL_PLAN'] = mdl_a; g['_PROF_PLAN'] = prof_a

    g['_V18_MODELS_READY'] = True
```

**Что критично**:
- **Idempotent**: `_V18_MODELS_READY` flag skips re-load.
- **HF_TOKEN fallback**: если env vars not set, reads from `secrets/HF_TOKEN.json`.
- **Aliases**: `_TOK_PLAN / _MDL_PLAN / _TOK_EMIT / _MDL_EMIT / _PROF_*` — naming контракт expected by runner's `_gen / _gen_planner`.

## 3-Colab-Runtime Parallelism Pattern

В Phase 22-28 период мы использовали **multiple Colab kernels** одновременно: S1, S2, S3 (по одной A100-80GB на каждый). Each kernel:

- Own bridge URL (Cloudflare tunnel) → own URL file (`tools/.bridge_url`, `tools/.bridge_url_dbt`, etc.)
- Shared Drive mount (`/content/drive/MyDrive/diploma_plan_sql`) — all writes go to one place
- Models loaded per-kernel (~5-10 min cold start)

Coordination через file markers:
- `run_dir/_STARTED` — runner начал
- `run_dir/_DONE` — runner finished
- `run_dir/_RUNNER_ERROR` — runner crashed
- `run_dir/_supervisor_heartbeat.txt` — supervisor liveness (Phase 28)
- `run_dir/_supervisor.log` — supervisor events log
- `run_dir/predictions.jsonl` — task results (resume scaffolding reads)
- `run_dir/traces.jsonl` — per-task diagnostic
- `run_dir/progress.json` — current state

**Phase 23 lesson**: concurrent inference на **single kernel** → CUDA OOM. **Cross-kernel** parallelism (different physical GPUs) — works. **GPU lock** (`gpu_lock_v24.py`) + sequential runner на single kernel — also works.

## Local helpers: `tools/_invoke_remote.py`

```python
"""Helper: send a local script to the remote bridge /exec and print result."""
import urllib.request, json, sys

def invoke(bridge_path, script_path, endpoint='/exec', timeout=120):
    url = open(bridge_path, encoding='utf-8').read().strip() + endpoint
    code = open(script_path, encoding='utf-8').read()
    req = urllib.request.Request(
        url, data=json.dumps({'code': code}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode('utf-8'))
    print(d.get('stdout', ''))
    if d.get('stderr'): print('STDERR:', d['stderr'][:1000])
    if d.get('traceback'): print('TB:', d['traceback'][:1500])

if __name__ == '__main__':
    bridge = sys.argv[1] if len(sys.argv) > 1 else r'd:/HSE/.../tools/.bridge_url'
    script = sys.argv[2] if len(sys.argv) > 2 else None
    invoke(bridge, script)
```

**Что критично**: thin POST wrapper. Bridge URL file + script file → HTTP POST /exec endpoint, returns stdout/stderr/traceback. Сэкономляет много мелких scripts (one-liners) — caller просто passes script path.

## Design decisions, видные в code

### D1. Per-task `try/except` isolation
Single task fault не crashes run. Recorded as exception в traces.jsonl.

### D2. `flush()` after every write
Ensures intermediate state persists.

### D3. Periodic close+reopen (Phase 28)
Forces Drive FUSE sync. Compensates for known Drive append-mode caching behavior.

### D4. Module reload at start (line 333)
Picks up latest module versions from Drive without kernel restart.

### D5. `pk_fk_injected` counter в trace
Per-task diagnostic. Helps audit Phase 27 correction 3 contribution.

### D6. `instance_ids_set` filter parameter
Subset filtering (pilot10, pilot50). Reusable orchestration primitive.

### D7. Resume scaffolding (Phase 28)
Reads existing predictions before opening files in append mode. Critical для multi-day runs.

## Edge cases handled

- **Task без `instance_id`**: fall-back на `f't{n}'`.
- **Empty catalog для `task_db`**: `err['no_catalog_for_task_db'] += 1`, continue.
- **F1 guard raises IdentifierLeakError**: record + continue, don't crash whole run.
- **Fixer module missing** (Phase 27-era code on Phase 28 deployment): graceful `fixer = None`.
- **GPU OOM**: `gc.collect(); torch.cuda.empty_cache()` every 5 tasks.

## Test coverage

**Integration testing only**. Run runner на pilot10 → produces predictions.jsonl + traces.jsonl. Audit those.

**No unit tests** на orchestration logic. Technical debt.

## Known limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | Sequential per-task processing | На 547 tasks ~10-12h wall | Multi-kernel parallelism (S1/S2/S3) |
| L2 | Drive FUSE sync delay | Cloud Drive lags local mount; cross-kernel reads stale | Periodic close+reopen (Phase 28 fix) |
| L3 | Model load 5-10 min cold start | Slow recovery from kernel death | Idempotent `_phase25_load_models.py` + memory note |
| L4 | No retry on transient HTTP/Snow errors | Single network blip → failed task | Phase 31+ — add retry decorator |
| L5 | Snowflake env vars not auto-loaded by notebook | All tasks fail `connect_fail` если forgotten | `_phase28_s1_fix_snowflake.py` script + `colab_session_bringup.md` §2a |

## Evolution history

| Phase | Change |
|---|---|
| **Phase 17-18** | Initial runner (different file, joint emit) |
| **Phase 22 STAGE A2** | Side-channel `all_columns`, join_hints в pack |
| **Phase 24** | Sequential runner v24 (`run_spider2_sequential_v24.py`) + GPU lock |
| **Phase 27** | **`_phase27_snow_runner.py`** introduced. Per-task BM25 partition + AST guard + PK/FK injection. |
| **Phase 28** | Resume scaffolding + periodic flush + F4 wrap hook + F4c fallback. F2a hook **removed** post-revert. |

## Cross-references

- All architecture files в [04_ARCHITECTURE/](../04_ARCHITECTURE/) — runner orchestrates them
- Resilience patterns: [09_resilience_patterns.md](./09_resilience_patterns.md)
- Phase reports — see [11_APPENDIX/04_full_phase_report_index.md](../11_APPENDIX/04_full_phase_report_index.md)
- Per-lane pipeline details: [05_PIPELINES/](../05_PIPELINES/)
- Bridge / tunnel orchestration: [09_resilience_patterns.md](./09_resilience_patterns.md)

## Источники

| Утверждение | Источник |
|---|---|
| Main runner structure | `tools/remote_scripts/_phase27_snow_runner.py` |
| Resume scaffolding (Phase 28) | lines 401-450 |
| Periodic flush (Phase 28) | lines 547-560 |
| `_phase25_load_models.py` | `tools/remote_scripts/_phase25_load_models.py` |
| `_invoke_remote.py` | `tools/_invoke_remote.py` |
| 3-Colab parallelism + GPU lock | `outputs/REPORT_SPIDER2_FULL_DIAGNOSTIC_V23.md`; `outputs/REPORT_PHASE26_RESEARCHER_HANDOFF.md` |
| Drive FUSE sync issue (Phase 28 S2) | conversation log; `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §10 |
