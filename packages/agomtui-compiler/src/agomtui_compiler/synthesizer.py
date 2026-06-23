from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .collector import EvidenceBundle


@dataclass(frozen=True)
class CompilerPrompt:
    """One schema-constrained prompt envelope for an LLM synthesizer."""

    system: str
    user: str
    constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillMessage:
    """Structured prompt message for a skill or chat-style LLM backend."""

    role: str
    content: str


@dataclass(frozen=True)
class MetadataSynthesisRequest:
    """Inputs passed into the LLM synthesis boundary."""

    schema_text: str
    evidence: EvidenceBundle
    registry_key: str = "default"
    generation_note: str = ""


@dataclass(frozen=True)
class MetadataSynthesisResult:
    """LLM synthesis output before validation/publish."""

    candidate_payload: dict[str, Any]
    model_name: str
    reasoning_note: str = ""


class LlmMetadataSynthesizer(Protocol):
    """Boundary for AI skill / model-backed metadata synthesis."""

    def build_prompt(self, request: MetadataSynthesisRequest) -> CompilerPrompt:
        """Build a constrained prompt from schema and evidence."""

    def synthesize(self, request: MetadataSynthesisRequest) -> MetadataSynthesisResult:
        """Return one candidate metadata graph."""


class SkillBackend(Protocol):
    """Minimal backend interface for a skill or model runner."""

    def complete(self, messages: list[SkillMessage]) -> dict[str, Any]:
        """Return a JSON-serializable completion result."""


class PromptOnlySynthesizer:
    """Reference synthesizer that emits a prompt but does not call a model."""

    model_name = "prompt-only"

    def build_prompt(self, request: MetadataSynthesisRequest) -> CompilerPrompt:
        grouped_evidence = json.dumps(
            {
                "registry_key": request.registry_key,
                "source_evidence_counts": request.evidence.counts,
                "source_evidence": request.evidence.grouped_payload(),
            },
            ensure_ascii=False,
            indent=2,
        )
        constraints = [
            "Schema exists before AI generation.",
            "Only use fields, widgets, value types, and action shapes that exist in the schema.",
            "Derive field metadata from code evidence, not retellings.",
            "Do not invent visibility rules, confirmation policy, or business-only color logic.",
            "Do not invent product-specific screens, workflow sequencing, or business narratives unless evidence requires them.",
            "Prefer host-agnostic runtime metadata that can be mounted by adapters instead of app-specific page choreography.",
            "Emit one metadata JSON candidate only.",
        ]
        system = (
            "You are a compile-time AgomTUI metadata synthesizer. "
            "You convert code-owned evidence into one schema-valid, host-agnostic metadata graph."
        )
        user = (
            "Generate one candidate TUI metadata graph.\n\n"
            "Schema:\n"
            f"{request.schema_text}\n\n"
            "Evidence:\n"
            f"{grouped_evidence}\n\n"
            "Return JSON only."
        )
        return CompilerPrompt(system=system, user=user, constraints=constraints)

    def build_messages(self, request: MetadataSynthesisRequest) -> list[SkillMessage]:
        prompt = self.build_prompt(request)
        return [
            SkillMessage(role="system", content=prompt.system),
            SkillMessage(
                role="user",
                content=(
                    f"{prompt.user}\n\n"
                    "Hard constraints:\n"
                    + "\n".join(f"- {item}" for item in prompt.constraints)
                ),
            ),
        ]

    def synthesize(self, request: MetadataSynthesisRequest) -> MetadataSynthesisResult:
        raise NotImplementedError(
            "PromptOnlySynthesizer does not call a model. "
            "Use build_prompt() to feed an external AI skill or LLM backend."
        )


class SkillBackedSynthesizer(PromptOnlySynthesizer):
    """Reference synthesizer that delegates prompt execution to a skill backend."""

    def __init__(self, backend: SkillBackend, *, model_name: str = "skill-backend") -> None:
        self.backend = backend
        self.model_name = model_name

    def synthesize(self, request: MetadataSynthesisRequest) -> MetadataSynthesisResult:
        completion = self.backend.complete(self.build_messages(request))
        candidate_payload = completion.get("candidate_payload", completion)
        if not isinstance(candidate_payload, dict):
            raise ValueError("Skill backend must return a JSON object candidate_payload")
        model_name = str(completion.get("model_name") or self.model_name)
        reasoning_note = str(completion.get("reasoning_note") or "")
        return MetadataSynthesisResult(
            candidate_payload=candidate_payload,
            model_name=model_name,
            reasoning_note=reasoning_note,
        )


class JsonFileSkillBackend:
    """Development backend that reads a skill result from a JSON file."""

    def __init__(self, result_path: str) -> None:
        self.result_path = result_path

    def complete(self, messages: list[SkillMessage]) -> dict[str, Any]:
        del messages
        with open(self.result_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Skill result file must contain a JSON object")
        return payload
