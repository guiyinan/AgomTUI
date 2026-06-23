from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublishResult:
    """Paths and hashes produced by one publish step."""

    candidate_path: Path
    evidence_path: Path


class FileArtifactPublisher:
    """Write candidate graph and evidence bundle to disk."""

    def publish(
        self,
        *,
        candidate_payload: dict[str, Any],
        evidence_payload: dict[str, Any],
        candidate_path: Path,
        evidence_path: Path,
    ) -> PublishResult:
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(
            json.dumps(candidate_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evidence_path.write_text(
            json.dumps(evidence_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return PublishResult(candidate_path=candidate_path, evidence_path=evidence_path)
