"""gpu_lock_v24 — Drive-file lock for sequential GPU inference runs.

Phase 24 motivation: Phase 23's concurrent BG runners on a single
A100 80GB caused cascading CUDA OOM. This module enforces "ONE
inference run at a time" at the run-orchestrator level.

Lock semantics:
- Lock file lives at `<DRIVE>/outputs/runtime/gpu_inference.lock`.
- The file's content is JSON: {"run_id", "host", "pid", "ts_start"}.
- Acquire: create the file atomically (open with x mode). If it
  exists and the recorded process is still alive on this host, the
  acquire fails. If the recorded process is stale (host different
  or PID dead), the lock is forcibly broken with a written
  `_FORCE_BROKEN` reason.
- Release: delete the file. Idempotent.
- A separate _STARTED marker is written into the run dir; on
  release, the run dir gets _DONE or _FAILED.

This is a coarse lock — does NOT protect against in-process
threading races (use threading.Lock for that). It protects against
launching a *second* benchmark while a *first* is still active.
"""
from __future__ import annotations

import json
import os
import socket
import time
import errno
from pathlib import Path


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError as e:
        if e.errno == errno.ESRCH:
            return False
        return True


class GPULock:
    def __init__(self, lock_path: Path):
        self.lock_path = Path(lock_path)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._held = False
        self._info = None

    def is_held_by_other(self) -> dict | None:
        if not self.lock_path.is_file():
            return None
        try:
            data = json.loads(self.lock_path.read_text())
        except Exception:
            data = {'run_id': '?', 'pid': None, 'host': '?'}
        host = socket.gethostname()
        pid = data.get('pid')
        # If host matches and pid alive → held by other
        if data.get('host') == host and pid and _is_pid_alive(int(pid)):
            return data
        # Otherwise stale (foreign host or dead pid) — return None to allow break
        return None

    def acquire(self, run_id: str) -> dict:
        existing = self.is_held_by_other()
        if existing:
            return {'acquired': False, 'reason': 'held_by_other', 'holder': existing}
        # If a stale lock file exists, break it
        if self.lock_path.is_file():
            try:
                stale = json.loads(self.lock_path.read_text())
            except Exception:
                stale = {}
            self.lock_path.write_text(json.dumps({
                'run_id': run_id,
                'host': socket.gethostname(),
                'pid': os.getpid(),
                'ts_start': time.time(),
                '_FORCE_BROKEN': stale,
            }))
            self._held = True
            self._info = {'run_id': run_id, 'broke_stale': stale}
            return {'acquired': True, 'broke_stale': stale}
        # Atomic create
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                payload = json.dumps({
                    'run_id': run_id,
                    'host': socket.gethostname(),
                    'pid': os.getpid(),
                    'ts_start': time.time(),
                }).encode('utf-8')
                os.write(fd, payload)
            finally:
                os.close(fd)
            self._held = True
            self._info = {'run_id': run_id}
            return {'acquired': True}
        except FileExistsError:
            return {'acquired': False, 'reason': 'race_lost'}

    def release(self) -> bool:
        if not self.lock_path.is_file():
            self._held = False
            return False
        try:
            self.lock_path.unlink()
            self._held = False
            return True
        except Exception:
            return False

    def __enter__(self):
        if not self._held:
            raise RuntimeError('GPULock used as context manager without prior acquire()')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


def free_gpu_cache():
    """Best-effort GPU cache release. Safe to call repeatedly."""
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            torch.cuda.empty_cache()
    except Exception:
        pass


def gpu_mem_info_gb() -> dict | None:
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info()
        return {
            'free_gb': round(free / (1024 ** 3), 2),
            'total_gb': round(total / (1024 ** 3), 2),
            'alloc_gb': round(torch.cuda.memory_allocated() / (1024 ** 3), 2),
        }
    except Exception:
        return None
