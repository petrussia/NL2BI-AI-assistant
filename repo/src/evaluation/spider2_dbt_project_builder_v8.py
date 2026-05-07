"""spider2_dbt_project_builder_v8 — project tree retrieval for the agent.

Re-exports the existing context exporter / prompt builder helpers used by
the v8 agent. The agent reads:
  - dbt_project.yml
  - models/*.sql + sources YAML
  - schema.yml
  - relevant macros / tests
... via `spider2_dbt_bridge.export_task_context`, which serializes the
project tree and produces a snapshot tarball for the model.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'spider2_dbt_bridge'))


def export_task_tree(iid: str) -> bool:
    """Trigger the bridge's project-tree exporter for one task."""
    import subprocess
    cmd = [sys.executable,
            str(REPO / 'spider2_dbt_bridge' / 'export_task_context.py'),
            '--task-id', iid]
    p = subprocess.run(cmd, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=180)
    return p.returncode == 0
