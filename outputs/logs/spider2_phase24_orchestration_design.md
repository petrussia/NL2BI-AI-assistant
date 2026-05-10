# Phase 24 — sequential orchestration design

## Why we need this

Phase 23 launched three BG runners (Lite-BQ FULL + Lite-Snow + Spider2-Snow)
in the same Colab kernel. With 79.5 GB of the A100's 80 GB pre-allocated to
the planner+emitter weights, only ~6 GB headroom remained for activation
memory. A single 30B-MoE forward pass on a multi-thousand-token prompt can
spike to 30–40 GB of activations. Three concurrent calls produced cascading
OOM that poisoned the BQ runner state and forced Phase 23 to be a partial /
cancelled diagnostic.

**Lesson:** at this VRAM budget, only ONE forward pass at a time is safe.

## Phase 24 lock design

### File-based exclusive lock on Drive

`outputs/runtime/gpu_inference.lock` — single file, JSON-encoded
`{run_id, host, pid, ts_start}`. Implemented in
`repo/src/evaluation/gpu_lock_v24.py`.

- **Acquire**: atomic `O_CREAT | O_EXCL` create. If the file exists and
  records a live PID on the same host, acquisition FAILS and the
  attempted run aborts. If the lock is stale (foreign host or dead PID),
  it is force-broken with the prior content recorded in `_FORCE_BROKEN`.
- **Release**: idempotent unlink. The orchestrator releases on
  normal completion AND on exception via try/finally.

### Run-level isolation

The orchestrator (`tools/run_spider2_sequential_v24.py`) MUST:

1. Acquire the lock before launching any inference job.
2. Refuse to launch a second job while the first is active.
3. After completion: `torch.cuda.empty_cache()` + `gc.collect()`,
   release lock, write `_DONE`/`_FAILED` into the run dir.
4. Each job runs as a SINGLE BG thread (not multiple parallel threads
   for "speed").

### Cross-benchmark policy

The lock is benchmark-agnostic. While the lock is held by ANY of:
- Lite-BQ
- Lite-Snow
- Spider2-Snow
- DBT inference

— no other benchmark can launch. This is the entire point: Phase 23 showed
that even cross-benchmark concurrency triggers cascading OOM.

### What the lock does NOT cover

- In-process threading races: still need `threading.Lock` around
  `model.generate` if a single runner uses multiple in-process threads.
  Phase 24 deliberately uses single-thread runners to side-step this.
- Cross-host concurrency: lock is host-aware. If two different machines
  both try to launch on the same Drive, the second still acquires
  (foreign-host PIDs are treated as stale). Out of scope; the bridge is
  always one Colab kernel.
- Inference inside DBT remote (separate machine): out of scope; that's
  a different GPU context. But Phase 24 does NOT run DBT.

## Orchestrator API

```
python tools/run_spider2_sequential_v24.py \
    --benchmark lite_bq \
    --run-id lite_bq_v24_pilot50 \
    --pilot50  # OR --full
```

Modes implemented in Phase 24:
- `--benchmark lite_bq --pilot50`
- `--benchmark lite_bq --full` (gate-checked: refuses unless prior
  pilot50 metrics file shows sv≥60% AND dry_run_ok≥50%)

NOT implemented (deferred):
- `--benchmark snow_full` — needs Snow auth fix first
- `--benchmark dbt_full` — separate orchestration; out of Phase 24 scope
- `--benchmark lite_snow` — same Snow auth blocker

## Failure modes covered

| failure | response |
|---|---|
| Lock held by other run | refuse to launch; print active holder; exit 1 |
| Bridge unreachable | refuse to launch; suggest `tools/exec_remote.py --health` |
| GPU < 8 GB free at start | refuse to launch; print mem info; exit 1 |
| Pilot50 gate not cleared | refuse FULL launch; redirect to bug-fix |
| BG runner crashes mid-run | _FAILED written; lock released; predictions/traces preserved |
| Tunnel rotates mid-run | run continues on bridge; orchestrator re-polls |
