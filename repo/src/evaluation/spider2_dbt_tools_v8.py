"""spider2_dbt_tools_v8 — DBT shell tooling shim.

Re-exports SSH command helpers used by the agent. Future split-points:
- per-tool wrappers for dbt deps / run / test that surface structured
  return codes instead of raw rc.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'spider2_dbt_bridge'))

from ssh_utils import (  # noqa: F401
    load_config, ssh_run, scp_to_remote, scp_from_remote,
    ensure_remote_dir, local_task_path,
)
