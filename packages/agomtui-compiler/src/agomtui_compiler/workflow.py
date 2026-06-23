from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agomtui_core import compact_tui_metadata_payload, validate_tui_metadata

from .collector import BaseCollector, CollectionContext, EvidenceBundle
from .publisher import FileArtifactPublisher, PublishResult
from .synthesizer import LlmMetadataSynthesizer, MetadataSynthesisRequest


@dataclass(frozen=True)
class CompilerWorkflowResult:
    """Structured result for one compile-time metadata run."""

    validated_payload: dict[str, Any]
    compacted_payload: dict[str, Any]
    evidence_payload: dict[str, Any]
    publish_result: PublishResult | None
    source_counts: dict[str, int]


class CompilerWorkflow:
    """Compose collectors, one AI synthesizer, validation, and publishing."""

    def __init__(
        self,
        *,
        collectors: list[BaseCollector],
        synthesizer: LlmMetadataSynthesizer,
        publisher: FileArtifactPublisher | None = None,
    ) -> None:
        self.collectors = collectors
        self.synthesizer = synthesizer
        self.publisher = publisher

    def collect(self, context: CollectionContext) -> EvidenceBundle:
        bundle = EvidenceBundle()
        for collector in self.collectors:
            bundle.extend(collector.collect(context))
        return bundle

    def compile(
        self,
        *,
        context: CollectionContext,
        schema_path: Path,
        candidate_path: Path | None = None,
        evidence_path: Path | None = None,
        registry_key: str = "default",
        generation_note: str = "",
    ) -> CompilerWorkflowResult:
        evidence_bundle = self.collect(context)
        schema_text = schema_path.read_text(encoding="utf-8")
        request = MetadataSynthesisRequest(
            schema_text=schema_text,
            evidence=evidence_bundle,
            registry_key=registry_key,
            generation_note=generation_note,
        )
        synthesis = self.synthesizer.synthesize(request)
        validated = validate_tui_metadata(dict(synthesis.candidate_payload))
        compacted = compact_tui_metadata_payload(validated)
        evidence_payload = {
            "version": validated["version"],
            "registry_key": validated.get("registry_key", registry_key),
            "source_evidence_counts": evidence_bundle.counts,
            "source_evidence": evidence_bundle.grouped_payload(),
            "generation_note": generation_note,
            "model_name": synthesis.model_name,
            "reasoning_note": synthesis.reasoning_note,
        }
        publish_result = None
        if self.publisher and candidate_path and evidence_path:
            publish_result = self.publisher.publish(
                candidate_payload=compacted,
                evidence_payload=evidence_payload,
                candidate_path=candidate_path,
                evidence_path=evidence_path,
            )
        return CompilerWorkflowResult(
            validated_payload=validated,
            compacted_payload=compacted,
            evidence_payload=evidence_payload,
            publish_result=publish_result,
            source_counts=dict(evidence_bundle.counts),
        )

    def prompt_preview(
        self,
        *,
        context: CollectionContext,
        schema_path: Path,
        registry_key: str = "default",
        generation_note: str = "",
    ) -> dict[str, Any]:
        evidence_bundle = self.collect(context)
        request = MetadataSynthesisRequest(
            schema_text=schema_path.read_text(encoding="utf-8"),
            evidence=evidence_bundle,
            registry_key=registry_key,
            generation_note=generation_note,
        )
        prompt = self.synthesizer.build_prompt(request)
        return {
            "system": prompt.system,
            "user": prompt.user,
            "constraints": prompt.constraints,
            "source_counts": evidence_bundle.counts,
        }
