from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agomtui_core import TUI_METADATA_SCHEMA_PATH

from .collector import (
    CollectionContext,
    DjangoContractManifestCollector,
    JsonEvidenceCollector,
    OpenApiSpecCollector,
)
from .publisher import FileArtifactPublisher
from .synthesizer import (
    JsonFileSkillBackend,
    MetadataSynthesisRequest,
    MetadataSynthesisResult,
    PromptOnlySynthesizer,
    SkillBackedSynthesizer,
)
from .workflow import CompilerWorkflow


class StaticCandidateSynthesizer(PromptOnlySynthesizer):
    """Reference synthesizer for demos and manual review loops."""

    def __init__(self, candidate_path: Path) -> None:
        self.candidate_path = candidate_path
        self.model_name = "static-candidate"

    def synthesize(self, request: MetadataSynthesisRequest) -> MetadataSynthesisResult:
        del request
        candidate = json.loads(self.candidate_path.read_text(encoding="utf-8"))
        return MetadataSynthesisResult(
            candidate_payload=candidate,
            model_name=self.model_name,
            reasoning_note="Loaded from a curated candidate file. Replace with a real LLM backend.",
        )


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--evidence-file", action="append", default=[], help="Normalized evidence JSON")
    parser.add_argument("--openapi-file", action="append", default=[], help="OpenAPI JSON specification")
    parser.add_argument(
        "--django-contract-file",
        action="append",
        default=[],
        help="Django-exported model and aggregate contract manifest JSON",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgomTUI compiler skeleton")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prompt = subparsers.add_parser("prompt-preview", help="Render the LLM prompt envelope from evidence")
    prompt.add_argument("--project-root", default=".", help="Host project root")
    prompt.add_argument("--host-kind", default="generic", help="Host type label")
    _add_source_arguments(prompt)
    prompt.add_argument("--schema-path", default=str(TUI_METADATA_SCHEMA_PATH), help="Schema path")

    skill_request = subparsers.add_parser(
        "skill-request",
        help="Emit a structured request payload for an AI skill or chat-style model backend",
    )
    skill_request.add_argument("--project-root", default=".", help="Host project root")
    skill_request.add_argument("--host-kind", default="generic", help="Host type label")
    _add_source_arguments(skill_request)
    skill_request.add_argument("--schema-path", default=str(TUI_METADATA_SCHEMA_PATH), help="Schema path")

    compile_cmd = subparsers.add_parser("compile-static", help="Validate and publish from a curated candidate")
    compile_cmd.add_argument("--project-root", default=".", help="Host project root")
    compile_cmd.add_argument("--host-kind", default="generic", help="Host type label")
    _add_source_arguments(compile_cmd)
    compile_cmd.add_argument("--candidate-file", required=True, help="Curated candidate metadata JSON")
    compile_cmd.add_argument("--schema-path", default=str(TUI_METADATA_SCHEMA_PATH), help="Schema path")
    compile_cmd.add_argument("--output", required=True, help="Published compact metadata output path")
    compile_cmd.add_argument("--evidence-output", required=True, help="Evidence artifact output path")

    compile_skill = subparsers.add_parser(
        "compile-skill-result",
        help="Validate and publish from a JSON result produced by an AI skill backend",
    )
    compile_skill.add_argument("--project-root", default=".", help="Host project root")
    compile_skill.add_argument("--host-kind", default="generic", help="Host type label")
    _add_source_arguments(compile_skill)
    compile_skill.add_argument("--skill-result-file", required=True, help="AI skill result JSON")
    compile_skill.add_argument("--schema-path", default=str(TUI_METADATA_SCHEMA_PATH), help="Schema path")
    compile_skill.add_argument("--output", required=True, help="Published compact metadata output path")
    compile_skill.add_argument("--evidence-output", required=True, help="Evidence artifact output path")

    return parser


def _build_context(args: argparse.Namespace) -> CollectionContext:
    return CollectionContext(
        project_root=Path(args.project_root).resolve(),
        host_kind=args.host_kind,
    )


def _has_source_args(args: argparse.Namespace) -> bool:
    return bool(args.evidence_file or args.openapi_file or args.django_contract_file)


def _build_collectors(args: argparse.Namespace) -> list[Any]:
    collectors: list[Any] = []
    for path in args.evidence_file:
        collectors.append(JsonEvidenceCollector(Path(path).resolve()))
    for path in args.openapi_file:
        collectors.append(OpenApiSpecCollector(Path(path).resolve()))
    for path in args.django_contract_file:
        collectors.append(DjangoContractManifestCollector(Path(path).resolve()))
    return collectors


def _build_request_payload(args: argparse.Namespace) -> dict[str, Any]:
    context = _build_context(args)
    synthesizer = PromptOnlySynthesizer()
    workflow = CompilerWorkflow(
        collectors=_build_collectors(args),
        synthesizer=synthesizer,
    )
    evidence_bundle = workflow.collect(context)
    synthesis_request = MetadataSynthesisRequest(
        schema_text=Path(args.schema_path).resolve().read_text(encoding="utf-8"),
        evidence=evidence_bundle,
    )
    prompt = synthesizer.build_prompt(synthesis_request)
    messages = synthesizer.build_messages(synthesis_request)
    return {
        "messages": [
            {"role": message.role, "content": message.content}
            for message in messages
        ],
        "constraints": prompt.constraints,
        "source_counts": dict(evidence_bundle.counts),
        "expected_result_shape": {
            "candidate_payload": "<metadata-json-object>",
            "model_name": "<skill-or-model-name>",
            "reasoning_note": "<optional-short-note>",
        },
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not _has_source_args(args):
        parser.error("At least one evidence source is required. Use --openapi-file, --django-contract-file, or --evidence-file.")

    if args.command == "prompt-preview":
        workflow = CompilerWorkflow(
            collectors=_build_collectors(args),
            synthesizer=PromptOnlySynthesizer(),
        )
        print(
            json.dumps(
                workflow.prompt_preview(
                    context=_build_context(args),
                    schema_path=Path(args.schema_path).resolve(),
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "skill-request":
        print(
            json.dumps(
                _build_request_payload(args),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "compile-static":
        workflow = CompilerWorkflow(
            collectors=_build_collectors(args),
            synthesizer=StaticCandidateSynthesizer(Path(args.candidate_file).resolve()),
            publisher=FileArtifactPublisher(),
        )
        generation_note = "Compiled via agomtui-compiler static workflow."
    else:
        workflow = CompilerWorkflow(
            collectors=_build_collectors(args),
            synthesizer=SkillBackedSynthesizer(
                JsonFileSkillBackend(args.skill_result_file),
                model_name="json-skill-result",
            ),
            publisher=FileArtifactPublisher(),
        )
        generation_note = "Compiled via agomtui-compiler skill-backed workflow."

    result = workflow.compile(
        context=_build_context(args),
        schema_path=Path(args.schema_path).resolve(),
        candidate_path=Path(args.output).resolve(),
        evidence_path=Path(args.evidence_output).resolve(),
        generation_note=generation_note,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(result.publish_result.candidate_path) if result.publish_result else "",
                "evidence_output": str(result.publish_result.evidence_path) if result.publish_result else "",
                "source_counts": result.source_counts,
                "version": result.validated_payload["version"],
                "schema_version": result.validated_payload["schema_version"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
