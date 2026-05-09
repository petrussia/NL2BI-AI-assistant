"""spider2_dbt_agent_v8 — code-generation agent facade for Spider2-DBT 68.

Wraps the existing `spider2_dbt_bridge.run_dbt_ablation` pipeline as the
Phase 3 entry point. The actual workflow (export context → build prompt
→ inference → apply → dbt deps → dbt run → dbt test → official_eval) is
implemented in the bridge module; this module exposes a clean v8 API:

    run_dbt_v8(iid, variant='v4', max_new=1500) -> dict
        { instance_id, variant, status, apply_kind, pushed_files,
          dbt_deps_rc, dbt_run_rc, dbt_test_rc, pass_n, err_n,
          official_score, official_rc, wall_time_s }

V4 (diff-form) emerged as the winning variant from the n=6 smoke
ablation (commit 8f57eea: V4 helpful=1, harmful=0).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'spider2_dbt_bridge'))


def run_dbt_v8(iid: str, variant: str = 'v4',
                 *, max_new: int = 1500) -> dict:
    """Run a single Spider2-DBT task end-to-end. Variant 'v4' = diff-form
    (winner of the V1/V2/V4 ablation in commit 8f57eea).
    """
    from ssh_utils import load_config
    from run_dbt_ablation import (
        _ensure_context, _build_prompt, _inference,
        _per_variant_apply, _per_variant_eval, _prepare_floor_workspace,
    )
    cfg = load_config(REPO / 'spider2_dbt_bridge' / 'config.example.yaml')
    t0 = time.time()
    if not _ensure_context(iid, cfg):
        return {'instance_id': iid, 'variant': variant, 'status': 'context_export_failed',
                 'wall_time_s': round(time.time() - t0, 2)}
    if variant == 'v0_floor':
        ws, manifest = _prepare_floor_workspace(cfg, iid)
        eval_metrics = _per_variant_eval(cfg, iid, variant, ws)
        return {'instance_id': iid, 'variant': variant, 'status': 'done',
                 **manifest, **eval_metrics,
                 'wall_time_s': round(time.time() - t0, 2)}

    if not _build_prompt(iid, variant):
        return {'instance_id': iid, 'variant': variant,
                 'status': 'prompt_build_failed',
                 'wall_time_s': round(time.time() - t0, 2)}
    if not _inference(iid, variant, max_new=max_new):
        return {'instance_id': iid, 'variant': variant, 'status': 'inference_failed',
                 'wall_time_s': round(time.time() - t0, 2)}
    ws, manifest = _per_variant_apply(cfg, iid, variant)
    if not ws:
        return {'instance_id': iid, 'variant': variant, 'status': 'apply_failed',
                 **manifest, 'wall_time_s': round(time.time() - t0, 2)}
    eval_metrics = _per_variant_eval(cfg, iid, variant, ws)
    return {'instance_id': iid, 'variant': variant, 'status': 'done',
             **manifest, **eval_metrics,
             'wall_time_s': round(time.time() - t0, 2)}
