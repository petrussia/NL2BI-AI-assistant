"""Reproducibility helpers for local and Colab runs."""

from __future__ import annotations

import os
import platform
import random
import subprocess
import sys
from pathlib import Path
from typing import Any


def set_seed(seed: int = 42) -> int:
    """Set deterministic seeds for standard Python and NumPy if installed."""

    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ModuleNotFoundError:
        pass
    return seed


def git_sha(repo_dir: str | Path = ".") -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(repo_dir),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_status_short(repo_dir: str | Path = ".") -> str | None:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=Path(repo_dir),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def pip_freeze() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def runtime_info(repo_dir: str | Path = ".") -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "git_sha": git_sha(repo_dir),
        "git_status": git_status_short(repo_dir),
        "t2v_drive_root": os.environ.get("T2V_DRIVE_ROOT"),
        "seed_env": os.environ.get("PYTHONHASHSEED"),
    }
    try:
        import psutil

        memory = psutil.virtual_memory()
        info["memory_total_mb"] = round(memory.total / (1024 * 1024), 2)
        info["memory_available_mb"] = round(memory.available / (1024 * 1024), 2)
    except ModuleNotFoundError:
        info["memory_total_mb"] = None
        info["memory_available_mb"] = None
    return info
