from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from contracts.common import ArtifactRef


_SAFE_ID = re.compile(r"^[a-zA-Z0-9_.:-]+$")


class LocalArtifactStore:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        artifact_type: str,
        title: str,
        payload: dict[str, Any],
        request_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        artifact_id = f"{request_id}-{artifact_type}-{uuid.uuid4().hex[:8]}"
        data = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "title": title,
            "payload": payload,
            "metadata": metadata or {},
        }
        path = self._path_for(artifact_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            uri=f"/api/artifacts/{artifact_id}",
            payload=payload,
            metadata=metadata or {},
        )

    def save_response(self, request_id: str, payload: dict[str, Any]) -> None:
        path = self._path_for(f"{request_id}-response")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read(self, artifact_id: str) -> dict[str, Any] | None:
        if not _SAFE_ID.match(artifact_id):
            return None
        path = self._path_for(artifact_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _path_for(self, artifact_id: str) -> Path:
        return self.artifact_dir / f"{artifact_id}.json"
