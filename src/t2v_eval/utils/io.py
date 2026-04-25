"""Small, dependency-light file IO helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PathLike = str | Path


def ensure_parent(path: PathLike) -> Path:
    """Create the parent directory for a file path and return it as Path."""

    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def read_json(path: PathLike) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: PathLike, data: Any, *, indent: int = 2) -> Path:
    resolved = ensure_parent(path)
    resolved.write_text(
        json.dumps(data, ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )
    return resolved


def read_jsonl(path: PathLike) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_no} is not an object: {path}")
            rows.append(value)
    return rows


def write_jsonl(path: PathLike, rows: Iterable[Mapping[str, Any]]) -> Path:
    resolved = ensure_parent(path)
    with resolved.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    return resolved


def read_yaml(path: PathLike) -> Any:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to read YAML files.") from exc
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def write_yaml(path: PathLike, data: Any) -> Path:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to write YAML files.") from exc
    resolved = ensure_parent(path)
    resolved.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return resolved


def read_csv(path: PathLike) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: PathLike, rows: Sequence[Mapping[str, Any]]) -> Path:
    resolved = ensure_parent(path)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(str(key))

    with resolved.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return resolved
