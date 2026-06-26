from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agomtui_core import apply_tui_metadata_overrides, compact_tui_metadata_payload, validate_tui_metadata

from .collector import BaseCollector, CollectionContext, EvidenceBundle
from .enrichment import enrich_metadata_from_evidence
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
        metadata_overrides: list[dict[str, Any]] | None = None,
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
        candidate_payload = dict(synthesis.candidate_payload)
        for overrides in metadata_overrides or []:
            candidate_payload = apply_tui_metadata_overrides(candidate_payload, overrides)
        candidate_payload = enrich_metadata_from_evidence(candidate_payload, evidence_bundle)
        validated = validate_tui_metadata(candidate_payload)
        compacted = compact_tui_metadata_payload(validated)
        evidence_payload = {
            "version": validated["version"],
            "registry_key": validated.get("registry_key", registry_key),
            "source_evidence_counts": evidence_bundle.counts,
            "source_evidence": evidence_bundle.grouped_payload(),
            "generation_note": generation_note,
            "model_name": synthesis.model_name,
            "reasoning_note": synthesis.reasoning_note,
            "manual_overrides": _override_summary(metadata_overrides or []),
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


def _override_summary(metadata_overrides: list[dict[str, Any]]) -> dict[str, Any]:
    action_patch_count = 0
    field_patch_count = 0
    remove_field_count = 0
    files = []
    for overrides in metadata_overrides:
        action_patch_count += len(overrides.get("action_patches") or {})
        field_patch_count += sum(len(items or []) for items in (overrides.get("field_patches") or {}).values())
        remove_field_count += sum(len(items or []) for items in (overrides.get("remove_fields") or {}).values())
        source = str(overrides.get("source_file") or "").strip()
        if source:
            files.append(source)
    return {
        "applied": bool(metadata_overrides),
        "files": files,
        "action_patch_count": action_patch_count,
        "field_patch_count": field_patch_count,
        "remove_field_count": remove_field_count,
    }
