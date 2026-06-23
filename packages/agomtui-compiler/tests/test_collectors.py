from __future__ import annotations

import unittest
from pathlib import Path

from agomtui_compiler.cli import StaticCandidateSynthesizer, _build_collectors, _build_request_payload, build_parser
from agomtui_compiler.collector import CollectionContext, DjangoContractManifestCollector, OpenApiSpecCollector
from agomtui_compiler.workflow import CompilerWorkflow


REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples" / "metadata"


class CollectorTests(unittest.TestCase):
    def test_openapi_collector_reads_operation(self) -> None:
        collector = OpenApiSpecCollector(EXAMPLES / "minimal.openapi.json")
        items = collector.collect(CollectionContext(project_root=REPO_ROOT, host_kind="django"))
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_type, "openapi")
        self.assertEqual(item.payload["endpoint"], "/api/tui-example/status/")
        self.assertEqual(item.payload["method"], "GET")
        self.assertEqual(item.payload["risk"], "read")

    def test_django_contract_collector_reads_model_and_aggregate(self) -> None:
        collector = DjangoContractManifestCollector(EXAMPLES / "minimal.django_contract_manifest.json")
        items = collector.collect(CollectionContext(project_root=REPO_ROOT, host_kind="django"))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].source_type, "django-model")
        self.assertEqual(items[0].payload["fields"][2]["value_type"], "datetime")
        self.assertEqual(items[1].source_type, "ddd-aggregate")
        self.assertEqual(items[1].payload["commands"][0]["risk"], "write")

    def test_skill_request_counts_real_sources(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "skill-request",
                "--project-root",
                str(REPO_ROOT),
                "--host-kind",
                "django",
                "--openapi-file",
                str(EXAMPLES / "minimal.openapi.json"),
                "--django-contract-file",
                str(EXAMPLES / "minimal.django_contract_manifest.json"),
            ]
        )
        collectors = _build_collectors(args)
        self.assertEqual(len(collectors), 2)
        payload = _build_request_payload(args)
        self.assertEqual(payload["source_counts"]["openapi"], 1)
        self.assertEqual(payload["source_counts"]["django-model"], 1)
        self.assertEqual(payload["source_counts"]["ddd-aggregate"], 1)

    def test_validate_and_compact_commands_do_not_require_evidence_sources(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "validate-metadata",
                "--metadata-file",
                str(EXAMPLES / "minimal.tui_operation_graph.json"),
            ]
        )

        self.assertEqual(args.command, "validate-metadata")
        self.assertFalse(hasattr(args, "openapi_file"))

    def test_compile_applies_manual_overrides_before_publish(self) -> None:
        workflow = CompilerWorkflow(
            collectors=[
                OpenApiSpecCollector(EXAMPLES / "minimal.openapi.json"),
                DjangoContractManifestCollector(EXAMPLES / "minimal.django_contract_manifest.json"),
            ],
            synthesizer=StaticCandidateSynthesizer(EXAMPLES / "minimal.tui_operation_graph.json"),
        )

        result = workflow.compile(
            context=CollectionContext(project_root=REPO_ROOT, host_kind="django"),
            schema_path=REPO_ROOT / "packages" / "agomtui-core" / "src" / "agomtui_core" / "schema" / "tui_metadata.schema.v3.json",
            metadata_overrides=[
                {
                    "registry_key": "default",
                    "source_file": "manual.override.json",
                    "action_patches": {
                        "overview.status": {
                            "risk": "write",
                            "method": "POST",
                            "task_tier": "operation",
                        }
                    },
                    "field_patches": {
                        "overview.status": [
                            {
                                "key": "symbols",
                                "label": "Asset Codes",
                                "input_type": "text",
                                "required": True,
                                "binding": "body",
                            }
                        ]
                    },
                }
            ],
        )

        action = result.validated_payload["actions"][0]
        self.assertEqual(action["risk"], "write")
        self.assertTrue(action["confirmation_required"])
        self.assertEqual(action["fields"][0]["key"], "symbols")
        self.assertEqual(result.evidence_payload["manual_overrides"]["field_patch_count"], 1)


if __name__ == "__main__":
    unittest.main()
