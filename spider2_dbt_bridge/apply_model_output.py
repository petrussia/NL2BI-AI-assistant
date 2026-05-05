"""apply_model_output.py — parse data/spider2_dbt/tasks/<TASK_ID>/model_response.txt
into one or more file edits and ship them to the per-task workspace on the
server. NEVER touches `vendor/Spider2/spider2-dbt/examples/<iid>/` directly;
always operates inside `/home/denis/dbt/outputs/colab_bridge/tasks/<iid>/workspace/`
which is a copy-on-write of the example dir.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from ssh_utils import (
    load_config, ssh_run, scp_to_remote, ensure_remote_dir,
    local_task_path, task_workspace_path,
)


_FENCE_RE = re.compile(
    r'```(?P<lang>[A-Za-z]+)?\s*(?P<attrs>[^\n]*)?\n(?P<body>.*?)```',
    re.DOTALL,
)


def _parse_fenced_blocks(text: str) -> list[dict]:
    out = []
    for m in _FENCE_RE.finditer(text):
        lang = (m.group('lang') or '').lower()
        attrs = (m.group('attrs') or '').strip()
        body = m.group('body')
        attrs_kv = {}
        for kv in re.findall(r'(\w+)=([^\s]+)', attrs):
            attrs_kv[kv[0]] = kv[1]
        out.append({'lang': lang, 'body': body, 'attrs': attrs_kv})
    return out


def _materialize_action(blocks: list[dict], task_id: str,
                          workspace_dir: Path) -> tuple[str, list[Path]]:
    """Materialize one of: SQL block with `path=...` attr -> write that file.
    Diff block -> save as patch.diff. Returns ('sql_file' | 'diff' | 'none',
    list of files written under workspace_dir).

    workspace_dir is a LOCAL staging dir we mirror to the server.
    """
    written: list[Path] = []
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Prefer SQL block with explicit path; else first diff
    sql_block = None
    diff_block = None
    for b in blocks:
        if b['lang'] in ('sql', '') and b['attrs'].get('path'):
            sql_block = b; break
    if sql_block is None:
        for b in blocks:
            if b['lang'] == 'diff':
                diff_block = b; break

    if sql_block is not None:
        path = sql_block['attrs']['path']
        # Refuse traversal / absolute paths
        if path.startswith('/') or '..' in Path(path).parts:
            raise ValueError(f'unsafe path in fenced block: {path!r}')
        target = workspace_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sql_block['body'], encoding='utf-8')
        written.append(target)
        return ('sql_file', written)

    if diff_block is not None:
        target = workspace_dir / 'patch.diff'
        target.write_text(diff_block['body'], encoding='utf-8')
        written.append(target)
        return ('diff', written)

    # No block: if response is a bare SQL statement, fall back to writing
    # a default-named file
    return ('none', written)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--model-response', default=None,
                     help='Defaults to data/spider2_dbt/tasks/<TASK_ID>/model_response.txt')
    ap.add_argument('--default-model-path', default='models/output.sql',
                     help='If response is bare SQL with no path attr, write to this.')
    ap.add_argument('--config', default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    iid = args.task_id

    response_path = (Path(args.model_response) if args.model_response
                       else local_task_path(cfg, iid) / 'model_response.txt')
    if not response_path.exists():
        print(f'FAIL: model response not found: {response_path}')
        return 2

    text = response_path.read_text(encoding='utf-8')
    blocks = _parse_fenced_blocks(text)

    local_ws = local_task_path(cfg, iid) / 'workspace_staging'
    if local_ws.exists():
        # Clear staged dir to avoid stale files
        for p in sorted(local_ws.rglob('*'), reverse=True):
            try:
                if p.is_file() or p.is_symlink(): p.unlink()
                elif p.is_dir(): p.rmdir()
            except Exception: pass
    local_ws.mkdir(parents=True, exist_ok=True)

    kind, written = _materialize_action(blocks, iid, local_ws)
    if kind == 'none':
        # Fallback: treat the entire response as a new SQL file
        target = local_ws / args.default_model_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.strip(), encoding='utf-8')
        written = [target]
        kind = 'fallback_sql_file'

    print(f'PARSED: kind={kind} files={[p.name for p in written]}')

    # Push to server: workspace_dir on server = task_workspace_path/workspace
    remote_workspace = f'{task_workspace_path(cfg, iid)}/workspace'
    remote_incoming = f'{task_workspace_path(cfg, iid)}/incoming'
    ensure_remote_dir(cfg, remote_workspace)
    ensure_remote_dir(cfg, remote_incoming)

    # 1. Copy raw response to incoming/ for audit
    cp = scp_to_remote(cfg, response_path, f'{remote_incoming}/model_response.txt')
    if cp.returncode != 0:
        print(f'WARN: scp model_response.txt failed: {cp.stderr[:200]}')

    # 2. Make sure workspace is initialized as a copy of the example dir,
    #    so the model's edits compose with the existing files.
    #    Use `cp -R` (rsync may be absent on minimal servers).
    src_dir = f'{cfg.remote_spider2_dbt}/examples/{iid}'
    init_cmd = (
        f'mkdir -p {shlex.quote(remote_workspace)} && '
        f'if [ ! -f {shlex.quote(remote_workspace)}/dbt_project.yml ]; then '
        f'  cp -RTu {shlex.quote(src_dir)} {shlex.quote(remote_workspace)} && '
        f'  rm -rf {shlex.quote(remote_workspace)}/dbt_packages '
        f'         {shlex.quote(remote_workspace)}/target '
        f'         {shlex.quote(remote_workspace)}/logs; '
        f'fi'
    )
    r = ssh_run(cfg, init_cmd, timeout=120)
    if r.returncode != 0:
        print(f'WARN: workspace init failed: {r.stderr[:200]}')

    # 3. Copy each staged file into the remote workspace
    for p in written:
        rel = p.relative_to(local_ws).as_posix()
        remote_path = f'{remote_workspace}/{rel}'
        ensure_remote_dir(cfg,
                            f'{remote_workspace}/{Path(rel).parent.as_posix()}'
                            if '/' in rel else remote_workspace)
        cp = scp_to_remote(cfg, p, remote_path)
        if cp.returncode != 0:
            print(f'WARN: scp {rel} failed: {cp.stderr[:200]}')
        else:
            print(f'  PUSHED {rel} -> {remote_path}')

    # 4. If diff form, apply it on the server
    if kind == 'diff':
        diff_remote = f'{remote_workspace}/patch.diff'
        apply_cmd = (f'cd {shlex.quote(remote_workspace)} && '
                       f'git apply --whitespace=nowarn -p1 patch.diff || '
                       f'patch -p1 < patch.diff')
        r = ssh_run(cfg, apply_cmd, timeout=30)
        print(f'  DIFF_APPLY rc={r.returncode} '
              f'stdout={r.stdout[:200]} stderr={r.stderr[:200]}')

    # Manifest
    manifest = {
        'task_id': iid, 'kind': kind,
        'files_pushed': [p.relative_to(local_ws).as_posix() for p in written],
        'remote_workspace': remote_workspace,
        'remote_incoming': remote_incoming,
        'response_chars': len(text),
        'fenced_blocks_n': len(blocks),
    }
    (local_task_path(cfg, iid) / 'apply_manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'WROTE: {local_task_path(cfg, iid) / "apply_manifest.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
