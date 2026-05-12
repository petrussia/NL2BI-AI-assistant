# 08.09 — Resilience Patterns

## Покрытие

Этот файл документирует **операционные паттерны** обеспечения robustness в multi-day Colab-based pipeline. **Не один модуль** — а набор concrete techniques learned-the-hard-way через Phase 17-28. Все они сейчас закреплены либо в коде (`_phase27_snow_runner.py`, supervisor scripts), либо в auto-memory (`colab_session_bringup.md`).

Главные паттерны:

| # | Pattern | Where implemented | Phase introduced |
|---|---|---|---|
| 1 | Drive per-task writes | runner's `pf.flush()` after every task | Phase 18 |
| 2 | `_DONE` / `_STARTED` markers | runner writes terminal markers | Phase 18 |
| 3 | Resume from kernel death | runner reads existing predictions.jsonl, skips done iids | Phase 28 |
| 4 | Periodic file close+reopen | runner forces Drive FUSE sync every 10 tasks | Phase 28 |
| 5 | Supervisor with Drive heartbeat | `_phase28_s1_supervisor_v2.py` writes heartbeat file | Phase 28 |
| 6 | Cloudflare tunnel rotation | `sync_bridge_url_from_notebook.py` reads new URL | Phase 17 (matured Phase 26) |
| 7 | Per-kernel model alias mapping | `_TOK_/_MDL_/_PROF_` aliases set by load script | Phase 25 |
| 8 | Snowflake env restore | `_phase28_s1_fix_snowflake.py` loads from Drive secrets | Phase 28 |
| 9 | Bridge HTTP timeout chunking | step-by-step driver splits large uploads | Phase 28 |
| 10 | GPU OOM mitigation | `gc.collect() + torch.cuda.empty_cache()` every 5 tasks; GPU lock + sequential runner | Phase 23-24 |
| 11 | Module reload at runner start | `importlib.reload(...)` для each evaluation module | Phase 18+ |
| 12 | Memory file (auto-loaded) | `colab_session_bringup.md` + `MEMORY.md` index | Phase 28 |

## Pattern 1: Drive per-task writes

Each task writes single line into `predictions.jsonl` + `traces.jsonl` immediately после processing. `pf.flush()` flushes Python buffer к OS; OS writes to Drive FUSE.

```python
pf.write(json.dumps({...}) + '\n'); pf.flush()
tf.write(json.dumps(trace, default=str) + '\n'); tf.flush()

# Update progress.json (atomic-ish rewrite — small file)
with open(out_dir / 'progress.json', 'w') as f:
    f.write(json.dumps({
        'n_total': n, 'plan_ok': n_plan_ok, 'schema_valid': n_sv,
        'parse_ok': n_parse, 'execute_ok': n_exec,
        # ...
    }, default=str))
```

**Why critical**: на кеrnel crash mid-run, all data до crash сохранена. **Без** per-task writes (batching, e.g., flush every 50 tasks) — кernel crash на task 49 of 50 → lose all 49.

## Pattern 2: `_DONE` / `_STARTED` markers

```python
# At start
(out_dir / '_STARTED').write_text(json.dumps({
    'run_id': run_id, 'phase': 27, 'mode': 'F1_snow', 'ts': time.time()}))

# At end
(out_dir / '_DONE').write_text(json.dumps({
    'n_total': n, 'plan_ok': n_plan_ok, 'schema_valid': n_sv,
    'parse_ok': n_parse, 'execute_ok': n_exec,
    'wall_sec': round(time.time()-t0, 1), 'ts': time.time()}))
```

**Why critical**:
- `_STARTED` lets external observers know run is alive (timestamp).
- `_DONE` is the **handoff signal** — supervisor watches for it.

If runner crashes mid-run, `_STARTED` exists but `_DONE` doesn't. This distinguishes incomplete runs from completed.

## Pattern 3: Resume from kernel death (Phase 28)

```python
done_iids = set()
n_res_sv = n_res_parse = n_res_exec = n_res_plan = 0
pf_path = out_dir / 'predictions.jsonl'
if pf_path.exists():
    with open(pf_path, encoding='utf-8') as f:
        for ln in f:
            p = json.loads(ln)
            iid = p.get('instance_id')
            if iid:
                done_iids.add(iid)
                if p.get('explain_ok'): n_res_exec += 1
                if p.get('schema_valid'): n_res_sv += 1
                if p.get('parse_ok'): n_res_parse += 1

# Filter tasks
tasks = [t for t in tasks if t.get('instance_id') not in done_iids]

# Open files in APPEND mode
pf = open(out_dir / 'predictions.jsonl', 'a', encoding='utf-8')
tf = open(out_dir / 'traces.jsonl', 'a', encoding='utf-8')
```

**Why critical**: combined with Pattern 1 (per-task writes), this lets a new runner pick up exactly where the dead one stopped. Counters restored from previously written records.

**Phase 28 hardening**: previously runner opened files в `'w'` mode (overwrite). Crash at task 100 → restart truncates predictions.jsonl. Phase 28 changed to `'a'` mode + skip-done-iids check.

## Pattern 4: Periodic file close+reopen (Phase 28)

```python
if n % 10 == 0:
    try:
        pf.close(); tf.close()
        pf = open(out_dir / 'predictions.jsonl', 'a', encoding='utf-8')
        tf = open(out_dir / 'traces.jsonl', 'a', encoding='utf-8')
    except Exception as _e:
        print(f'[{run_id}] file sync reopen failed at n={n}: {_e}', flush=True)
```

**Why critical**: **Colab Drive FUSE quirk**. Files opened в `'a'` mode keep append cache **locally** до `close()`. Cloud Drive (visible to other kernels OR after kernel restart) sees stale state until close.

**Phase 28 S2 incident** demonstrated this: predictions.jsonl had n=119 in-memory counters, but only 40 lines on cloud Drive. Когда S2 kernel died, 79 unsynced entries lost.

Fix: close+reopen every 10 tasks → max 10-task data loss window on crash. Total throughput cost: negligible (file I/O is fast).

## Pattern 5: Supervisor with Drive heartbeat (Phase 28)

`_phase28_s1_supervisor_v2.py` — daemon thread watching for `_DONE` marker, auto-launching Lite chain после Snow completion. Plus **Drive heartbeat** для external monitoring:

```python
def _supervisor():
    log('supervisor v2 started — watching for SNOW _DONE')
    last_hb = 0
    n_polls = 0
    while True:
        try:
            n_polls += 1
            now = time.time()
            # Heartbeat every 5 min
            if now - last_hb >= 300:
                try:
                    snow_n = -1
                    pj = SNOW_DIR / 'progress.json'
                    if pj.exists():
                        snow_n = json.loads(pj.read_text()).get('n_total', -1)
                    snow_chain_alive = any(t.name == 'Phase28FullS1Chain' and t.is_alive()
                                            for t in threading.enumerate())
                    HEARTBEAT.write_text(
                        f'ts={time.strftime("%Y-%m-%d %H:%M:%S")} '
                        f'poll={n_polls} '
                        f'snow_progress={snow_n}/547 '
                        f'snow_chain_alive={snow_chain_alive} '
                        f'snow_done={(SNOW_DIR / "_DONE").exists()}\n')
                    last_hb = now
                except Exception as e:
                    log(f'heartbeat write failed: {e}')
            # ... check _DONE, fire handoff ...
            time.sleep(60)
        except Exception as e:
            log(f'supervisor outer loop exception: {e}')
            time.sleep(60)
```

**Why critical**:
- **Drive heartbeat file** updated every 5 min — observable externally без bridge.
- **Outer `try/except`** — transient errors не kill watcher.
- **Integrity check** (not shown above): verifies pf row count matches progress.n_total before firing handoff (no race с FUSE sync lag).

## Pattern 6: Cloudflare tunnel rotation

`trycloudflare.com` rotates subdomain on every restart. Bridge URL изменяется → local `tools/.bridge_url` стiale. Tool: `sync_bridge_url_from_notebook.py`:

```python
def main():
    with NB.open(encoding='utf-8') as f:
        nb = json.load(f)
    
    candidate_urls = []
    for c in nb.get('cells', []):
        cid = c.get('id') or ''
        # ONLY look at the canonical bridge setup cell
        if cid != '07-agent-bridge-setup':
            continue
        # Parse outputs of cell 07
        for output_text in iter_output_text(c):
            urls = URL_RE.findall(output_text)
            candidate_urls.extend(urls)
    
    if candidate_urls:
        # Take the latest (last-printed URL)
        OUT.write_text(candidate_urls[-1].strip() + '\n', encoding='utf-8')
```

**Why critical**:
- **Specific cell ID lookup** — avoid picking up stale URLs from other cells (e.g., readiness check cell).
- **Last-printed wins** — multiple URL prints в cell output (e.g., re-run history) — taking last reflects most recent state.
- **Manual fallback** if notebook hasn't been saved with new URL: paste URL directly into `tools/.bridge_url`.

## Pattern 7: Per-kernel model alias mapping

Different load scripts use different alias schemes:

| Script | Sets variables |
|---|---|
| Notebook cells in `example_agent_setup_clean.ipynb` (if any) | (varies) |
| `_phase25_load_models.py` | `tok_a, mdl_a, prof_a, tok_b, mdl_b, prof_b` + `_TOK_PLAN, _MDL_PLAN, _PROF_PLAN, _TOK_EMIT, _MDL_EMIT, _PROF_EMIT` |
| `_phase28_s2_load_models_bg.py` | Same as above, background thread |

Runner expects `_TOK_/_MDL_/_PROF_` aliases. Если только `tok_a/mdl_a` style present → runner crashes `KeyError('_TOK_EMIT')`.

Launch scripts (`_phase28_launch_s1_snow_full.py`) defensively alias:

```python
for k in ['_TOK_EMIT', '_MDL_EMIT', '_PROF_EMIT', '_TOK_PLAN', '_MDL_PLAN', '_PROF_PLAN']:
    if k not in g:
        src_map = {'_TOK_EMIT':'tok_b','_MDL_EMIT':'mdl_b','_PROF_EMIT':'prof_b',
                   '_TOK_PLAN':'tok_a','_MDL_PLAN':'mdl_a','_PROF_PLAN':'prof_a'}
        s = src_map.get(k)
        if s and s in g:
            g[k] = g[s]
            print(f'  ALIASED: {k} <- {s}')
```

**Why critical**: kernel state may have models loaded под одно naming, runner expects другое. Defensive alias glue.

## Pattern 8: Snowflake env restore (Phase 28)

`_snow_connect()` reads `SNOWFLAKE_*` env vars **directly from `os.environ`**. On fresh kernel — these vars **not auto-loaded** by notebook cells.

Phase 28 incident: forgot to set env vars after kernel restart. 64 tasks failed `connect_fail` before detection. Fix script:

```python
# _phase28_s1_fix_snowflake.py
SECRETS = Path('/content/drive/MyDrive/diploma_plan_sql/secrets/snowflake.json')
sf = json.loads(SECRETS.read_text(encoding='utf-8'))

key_map = {
    'account': 'SNOWFLAKE_ACCOUNT', 'user': 'SNOWFLAKE_USER',
    'password': 'SNOWFLAKE_PASSWORD', 'role': 'SNOWFLAKE_ROLE',
    'warehouse': 'SNOWFLAKE_WAREHOUSE', 'database': 'SNOWFLAKE_DATABASE',
}
for k, v in sf.items():
    env = key_map.get(k) or key_map.get(k.lower())
    if env and v:
        os.environ[env] = str(v)

# Test connect
c = snowflake.connector.connect(...)
c.cursor().execute('SELECT CURRENT_TIMESTAMP()').fetchone()

# Clean prior connect_fail entries from predictions.jsonl + traces.jsonl
bad_iids = {p['instance_id'] for p in preds
             if p.get('explain_class') == 'connect_fail'}
# ... rewrite files без bad_iids ...
```

**Why critical**: env var setup это **operational state**, не code state. Easy to forget. Memory note (`colab_session_bringup.md` §2a) — primary safeguard.

## Pattern 9: Bridge HTTP timeout chunking (Phase 28)

`_invoke_remote.py` default timeout = 120s. Long-running operations (model load) — 5-10 min. Solution: **launch in background thread**, immediate return from `/exec`, then poll status:

```python
# _phase28_s2_load_models_bg.py
def _load():
    try:
        g['_MODEL_LOAD_STATUS'] = 'in_progress'
        tok_b, mdl_b, prof_b = load_model_and_tokenizer(EMIT_ALIAS)
        # ... аналогично планер ...
        g['_V18_MODELS_READY'] = True
        g['_MODEL_LOAD_STATUS'] = 'done'
    except Exception as e:
        g['_MODEL_LOAD_STATUS'] = f'error: {e}'

t = threading.Thread(target=_load, name='Phase28S2ModelLoad', daemon=True)
t.start()
print('thread started')
```

External polling:
```python
# Local script polls /exec with simple status check
curl -s "${URL}/exec" -d '{"code":"print(g.get(\"_MODEL_LOAD_STATUS\"))"}'
```

**Why critical**: HTTP timeout не должен equal task completion time. Decouple через background thread + status flag.

Similar pattern для large payload uploads: `_send_phase28_step_by_step.py` splits module uploads в separate small `/exec` calls вместо one large script.

## Pattern 10: GPU OOM mitigation

Phase 23 incident: concurrent inference within single kernel → CUDA OOM на A100 80 GB (76 GB model + activation buffers). Resolution:

1. **GPU lock** (`gpu_lock_v24.py`): file-based mutex preventing concurrent inference в same kernel.
2. **Sequential runner**: process tasks one-at-a-time, no batching.
3. **Periodic cache clear**: `gc.collect() + torch.cuda.empty_cache()` каждые 5 tasks.

```python
if n % 5 == 0:
    try:
        import torch; gc.collect(); torch.cuda.empty_cache()
    except Exception: pass
```

**Cross-kernel parallelism** (S1/S2/S3) — completely separate GPUs, no shared CUDA state. Works without GPU lock.

## Pattern 11: Module reload at runner start

```python
for mod in ['schema_linking_v18', 'schema_pack_builder_v18',
            'structured_plan_v18', 'snow_identifier_guard_v27',
            'snow_dialect_fixer_v28']:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
```

**Why critical**: developer edits module locally → uploads to Drive → runner re-launches → reload picks up new code **without kernel restart** (saves 5-10 min model reload).

**Caveat**: `importlib.reload` doesn't reload module's transitive dependencies. If module A imports B and B changed — A's reference to B is stale. We handle this by explicitly reloading **the dependency tree** (e.g., `schema_pack_builder_v18` depends on `schema_linking_v18` — both in reload list).

## Pattern 12: Memory file (auto-loaded)

`C:\Users\dlaze\.claude\projects\d--HSE--------NL2BI-AI-assistant\memory\colab_session_bringup.md` — sticky cross-conversation reference. Loaded automatically by Claude в начале each conversation through Claude Code's memory system.

Contents (см. `MEMORY.md` index for full list):
- Bridge URL refresh workflow (Pattern 6)
- Stack verification check (`_phase28_full_verify_stack.py`)
- Model load steps (Pattern 7)
- Snowflake env restore (Pattern 8) — **critical section §2a**
- Runner + modules upload
- Resume trigger
- Heartbeat monitor
- Known kernel-vs-tunnel split
- What NOT to do

**Why critical**: institutional memory. Phase 28 incident про forgotten Snowflake env — **now documented** in section §2a, prevents recurrence in future restarts.

## Tying it together: standard kernel restart sequence

```bash
# 1. Sync new bridge URL
python tools/sync_bridge_url_from_notebook.py \
  --notebook notebooks/example_agent_setup_clean.ipynb \
  --out tools/.bridge_url

# 2. Health probe
curl -s -m 10 "$(cat tools/.bridge_url)/health"

# 3. BG load models (4-10 min)
python tools/_invoke_remote.py tools/.bridge_url \
  tools/remote_scripts/_phase28_s2_load_models_bg.py

# 4. CRITICAL: Snowflake env restore + cleanup
python tools/_invoke_remote.py tools/.bridge_url \
  tools/remote_scripts/_phase28_s1_fix_snowflake.py

# 5. Upload runner
python tools/_upload_runner_both.py

# 6. Verify stack (expect 20/20)
python tools/_invoke_remote.py tools/.bridge_url \
  tools/remote_scripts/_phase28_full_verify_stack.py

# 7. Re-trigger Snow chain (resume picks up from Drive's predictions)
python tools/_invoke_remote.py tools/.bridge_url \
  tools/remote_scripts/_phase28_launch_s1_snow_full.py

# 8. Install supervisor v2
python tools/_invoke_remote.py tools/.bridge_url \
  tools/remote_scripts/_phase28_s1_supervisor_v2.py
```

Standard recovery time: ~10-15 min wall (5-10 min model load + 2-5 min orchestration).

## Cross-references

- All other tools files в [08_CUSTOM_TOOLS/](.) — each pattern interacts с specific tool
- Architecture: [04_ARCHITECTURE/](../04_ARCHITECTURE/) — overall pipeline structure
- Phase reports история incidents: [11_APPENDIX/04_full_phase_report_index.md](../11_APPENDIX/04_full_phase_report_index.md)
- Memory note (auto-loaded reference): `colab_session_bringup.md` (in user's `.claude/projects/.../memory/` directory)
- Phase 23 GPU OOM: [06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases_overview.md)
- Phase 28 Drive FUSE incident: [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md) + conversation log

## Источники

| Pattern | Source |
|---|---|
| Per-task writes + markers | `tools/remote_scripts/_phase27_snow_runner.py` |
| Resume scaffolding | `tools/remote_scripts/_phase27_snow_runner.py` lines 401-450 |
| Periodic flush | lines 547-560 |
| Supervisor v2 + heartbeat | `tools/remote_scripts/_phase28_s1_supervisor_v2.py` |
| Bridge URL sync | `tools/sync_bridge_url_from_notebook.py` |
| Snowflake env restore | `tools/remote_scripts/_phase28_s1_fix_snowflake.py` |
| GPU lock | `repo/src/evaluation/gpu_lock_v24.py`; `outputs/REPORT_SPIDER2_FULL_DIAGNOSTIC_V23.md` |
| Memory file | `C:\Users\dlaze\.claude\projects\d--HSE--------NL2BI-AI-assistant\memory\colab_session_bringup.md` |
