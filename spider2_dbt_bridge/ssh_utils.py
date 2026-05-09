"""SSH/SCP helper for the Spider2-DBT bridge. Stdlib + OpenSSH only.

Reads connection info from `spider2_dbt_bridge/config.yaml` (falls back to
`config.example.yaml`), or accepts CLI flags at the call site.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / 'spider2_dbt_bridge' / 'config.yaml'
EXAMPLE_CONFIG = REPO / 'spider2_dbt_bridge' / 'config.example.yaml'


@dataclass
class BridgeConfig:
    ssh_user: str
    ssh_host: str
    ssh_extra_opts: list[str]
    remote_project: str
    remote_spider2_dbt: str
    remote_bridge_root: str
    remote_workspace_root: str
    local_data_root: Path
    refuse_full_benchmark: bool
    dbt_timeout_s: int
    run_dbt_deps: bool


def _yaml_loads(text: str) -> dict:
    """Minimal YAML reader — supports the simple structure used by our example.
    Avoids a hard PyYAML dependency on the local machine.
    """
    out: dict = {}
    stack: list[tuple[int, dict]] = [(-1, out)]

    def push(parent_indent: int, key: str, value):
        while stack and stack[-1][0] >= parent_indent:
            stack.pop()
        stack[-1][1][key] = value

    pending_list_key: str | None = None
    pending_list_indent = -1
    pending_list_target: list = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith('#'): continue
        indent = len(line) - len(line.lstrip(' '))
        stripped = line.strip()
        if stripped.startswith('-'):
            if pending_list_key is None: continue
            val = stripped[1:].strip().strip('"').strip("'")
            pending_list_target.append(val)
            continue
        if pending_list_key is not None and indent <= pending_list_indent:
            pending_list_key = None

        if ':' not in stripped: continue
        key, _, val = stripped.partition(':')
        key = key.strip(); val = val.strip()
        if not val:
            new = {}
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack[-1][1][key] = new
            stack.append((indent, new))
            continue
        # inline scalar or list start
        if val == '':
            stack[-1][1][key] = {}
            continue
        # strip quotes
        v = val.strip('"').strip("'")
        # may also be a key for an upcoming list
        if v == '':
            stack[-1][1][key] = []
            pending_list_key = key
            pending_list_indent = indent
            pending_list_target = stack[-1][1][key]
            continue
        # cast simple bools/ints
        if v.lower() in ('true', 'yes'): v = True
        elif v.lower() in ('false', 'no'): v = False
        else:
            try: v = int(v)
            except ValueError: pass
        stack[-1][1][key] = v
    return out


def load_config(path: str | None = None) -> BridgeConfig:
    if path:
        cfg_path = Path(path)
    elif DEFAULT_CONFIG.exists():
        cfg_path = DEFAULT_CONFIG
    elif EXAMPLE_CONFIG.exists():
        cfg_path = EXAMPLE_CONFIG
    else:
        raise FileNotFoundError('No config.yaml or config.example.yaml found')
    raw = _yaml_loads(cfg_path.read_text(encoding='utf-8'))
    ssh = raw.get('ssh', {}) or {}
    rem = raw.get('remote', {}) or {}
    loc = raw.get('local', {}) or {}
    bri = raw.get('bridge', {}) or {}
    return BridgeConfig(
        ssh_user=str(ssh.get('user') or 'denis'),
        ssh_host=str(ssh.get('host') or '103.54.18.91'),
        ssh_extra_opts=list(ssh.get('extra_opts') or
                              ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']),
        remote_project=str(rem.get('project_path') or '/home/denis/dbt'),
        remote_spider2_dbt=str(rem.get('spider2_dbt_root')
                                  or '/home/denis/dbt/vendor/Spider2/spider2-dbt'),
        remote_bridge_root=str(rem.get('bridge_root') or '/home/denis/dbt/colab_bridge'),
        remote_workspace_root=str(rem.get('workspace_root')
                                    or '/home/denis/dbt/outputs/colab_bridge/tasks'),
        local_data_root=REPO / str(loc.get('data_root') or 'data/spider2_dbt'),
        refuse_full_benchmark=bool(bri.get('refuse_full_benchmark', True)),
        dbt_timeout_s=int(bri.get('dbt_timeout_s', 300)),
        run_dbt_deps=bool(bri.get('run_dbt_deps', True)),
    )


def _ssh_base(cfg: BridgeConfig) -> list[str]:
    return ['ssh', *cfg.ssh_extra_opts, f'{cfg.ssh_user}@{cfg.ssh_host}']


def _scp_base(cfg: BridgeConfig) -> list[str]:
    # Use only the pre-defined extra_opts compatible with scp
    safe = [o for o in cfg.ssh_extra_opts if o not in ('-tt',)]
    return ['scp', *safe]


def ssh_run(cfg: BridgeConfig, remote_cmd: str, *,
              timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a shell command on the remote and capture stdout/stderr.

    `remote_cmd` is the command string as it would appear on the remote
    shell. It is NOT shell-quoted here — caller should pass a single
    well-formed string (use `shlex.quote` for paths with spaces).
    """
    cmd = [*_ssh_base(cfg), remote_cmd]
    return subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', timeout=timeout)


def scp_to_remote(cfg: BridgeConfig, local_path: str | Path,
                    remote_path: str, *, recursive: bool = False,
                    timeout: int = 120) -> subprocess.CompletedProcess:
    args = ['-r'] if recursive else []
    cmd = [*_scp_base(cfg), *args, str(local_path),
            f'{cfg.ssh_user}@{cfg.ssh_host}:{remote_path}']
    return subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', timeout=timeout)


def scp_from_remote(cfg: BridgeConfig, remote_path: str,
                      local_path: str | Path, *, recursive: bool = False,
                      timeout: int = 120) -> subprocess.CompletedProcess:
    args = ['-r'] if recursive else []
    cmd = [*_scp_base(cfg), *args,
            f'{cfg.ssh_user}@{cfg.ssh_host}:{remote_path}', str(local_path)]
    return subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', timeout=timeout)


def ensure_remote_dir(cfg: BridgeConfig, remote_dir: str) -> None:
    res = ssh_run(cfg, f'mkdir -p {shlex.quote(remote_dir)}')
    if res.returncode != 0:
        raise RuntimeError(f'mkdir -p {remote_dir} failed: {res.stderr.strip()}')


def task_workspace_path(cfg: BridgeConfig, task_id: str) -> str:
    return f'{cfg.remote_workspace_root.rstrip("/")}/{task_id}'


def local_task_path(cfg: BridgeConfig, task_id: str) -> Path:
    return cfg.local_data_root / 'tasks' / task_id
