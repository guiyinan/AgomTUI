from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from agomtui_compiler.cli import StaticCandidateSynthesizer, _build_collectors, _build_request_payload, build_parser
from agomtui_compiler.collector import CollectionContext, DjangoContractManifestCollector, OpenApiSpecCollector
from agomtui_compiler.synthesizer import JsonFileSkillBackend, SkillBackedSynthesizer
from agomtui_compiler.usability import check_tui_metadata_usability
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
        self.assertEqual(item.payload["response"]["fields"][0]["key"], "component")

    def test_openapi_collector_preserves_list_response_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            spec_path = Path(temp_dir) / "openapi.json"
            spec_path.write_text(json.dumps(_paginated_openapi_spec()), encoding="utf-8")
            collector = OpenApiSpecCollector(spec_path)

            items = collector.collect(CollectionContext(project_root=REPO_ROOT, host_kind="django"))

        item = items[0]
        response_fields = item.payload["response"]["fields"]
        self.assertEqual([field["key"] for field in item.payload["parameters"]], ["limit", "offset"])
        self.assertEqual(response_fields[0]["key"], "results")
        self.assertEqual(response_fields[0]["item_fields"][0]["key"], "id")
        self.assertEqual(response_fields[1]["key"], "total")

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
        joined_constraints = "\n".join(payload["constraints"])
        self.assertIn("chart, kpi_trend, or table_chart", joined_constraints)
        self.assertIn("HTMX partials only through host_slot", joined_constraints)

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

    def test_usability_command_does_not_require_evidence_sources(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "check-usability",
                "--metadata-file",
                str(EXAMPLES / "minimal.tui_operation_graph.json"),
            ]
        )

        self.assertEqual(args.command, "check-usability")
        self.assertFalse(args.fail_on_warning)
        self.assertFalse(hasattr(args, "openapi_file"))

    def test_usability_checker_accepts_current_examples_without_errors(self) -> None:
        for name in (
            "minimal.tui_operation_graph.json",
            "rich_components.tui_operation_graph.json",
            "generic_operations.tui_operation_graph.json",
        ):
            with self.subTest(name=name):
                payload = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
                result = check_tui_metadata_usability(payload)
                self.assertTrue(result.ok)
                self.assertEqual(result.error_count, 0)

    def test_usability_checker_reports_blocking_operator_gaps(self) -> None:
        payload = json.loads((EXAMPLES / "minimal.tui_operation_graph.json").read_text(encoding="utf-8"))
        unusable = copy.deepcopy(payload)
        unusable["screens"].append(
            {
                "key": "overview.empty",
                "label": "Empty",
                "module_key": "overview",
                "group": "workbench",
                "summary": "No usable affordances.",
                "view_type": "status",
            }
        )
        unusable["actions"][0]["view_type"] = "chart"
        unusable["actions"][0]["view_model"] = {"kind": "chart", "data_path": "data.rows"}
        unusable["actions"][0]["fields"] = [
            {
                "key": "tenant_id",
                "label": "Tenant ID",
                "input_type": "hidden",
                "required": True,
            }
        ]

        result = check_tui_metadata_usability(unusable)

        self.assertFalse(result.ok)
        self.assertGreaterEqual(result.error_count, 3)
        codes = {issue.code for issue in result.issues}
        self.assertIn("screen.empty", codes)
        self.assertIn("view_model.missing_renderer_path", codes)
        self.assertIn("field.hidden_required_without_default", codes)

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

    def test_compile_enriches_offset_pagination_from_openapi(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spec_path = temp_path / "openapi.json"
            candidate_path = temp_path / "candidate.json"
            spec_path.write_text(json.dumps(_paginated_openapi_spec()), encoding="utf-8")
            candidate_path.write_text(json.dumps(_pagination_candidate_metadata()), encoding="utf-8")
            workflow = CompilerWorkflow(
                collectors=[OpenApiSpecCollector(spec_path)],
                synthesizer=StaticCandidateSynthesizer(candidate_path),
            )

            result = workflow.compile(
                context=CollectionContext(project_root=REPO_ROOT, host_kind="django"),
                schema_path=REPO_ROOT
                / "packages"
                / "agomtui-core"
                / "src"
                / "agomtui_core"
                / "schema"
                / "tui_metadata.schema.v3.json",
            )

        action = result.validated_payload["actions"][0]
        self.assertEqual(action["view_type"], "datagrid")
        self.assertEqual(action["pagination"]["mode"], "offset")
        self.assertEqual(action["pagination"]["limit_param"], "limit")
        self.assertEqual(action["pagination"]["offset_param"], "offset")
        self.assertEqual(action["view_model"]["kind"], "datagrid")
        self.assertEqual(action["view_model"]["rows_path"], "results")
        self.assertEqual(action["view_model"]["total_path"], "total")
        self.assertEqual(action["view_model"]["page_size_path"], "limit")

    def test_compile_skill_result_accepts_rich_component_metadata(self) -> None:
        workflow = CompilerWorkflow(
            collectors=[OpenApiSpecCollector(EXAMPLES / "minimal.openapi.json")],
            synthesizer=SkillBackedSynthesizer(
                JsonFileSkillBackend(str(EXAMPLES / "rich_components.skill_result.json")),
                model_name="json-skill-result",
            ),
        )

        result = workflow.compile(
            context=CollectionContext(project_root=REPO_ROOT, host_kind="django"),
            schema_path=REPO_ROOT / "packages" / "agomtui-core" / "src" / "agomtui_core" / "schema" / "tui_metadata.schema.v3.json",
        )

        kinds = {action["view_model"]["kind"] for action in result.validated_payload["actions"]}
        self.assertEqual({"chart", "image", "table_chart", "host_slot"}, kinds)
        self.assertEqual(result.validated_payload["screens"][0]["dashboard_panels"][2]["kind"], "host_slot")

def _paginated_openapi_spec() -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Pagination API", "version": "1.0.0"},
        "paths": {
            "/api/events/pending/": {
                "get": {
                    "summary": "List pending events",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                        {"name": "offset", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Paginated rows",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "results": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "integer"},
                                                        "title": {"type": "string"},
                                                    },
                                                },
                                            },
                                            "total": {"type": "integer"},
                                            "limit": {"type": "integer"},
                                            "offset": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def _pagination_candidate_metadata() -> dict[str, object]:
    return {
        "schema_version": "tui-metadata.v3",
        "version": "agomtui-workbench.v0",
        "registry_key": "default",
        "default_screen": "events.pending",
        "interaction_model": "published-metadata-to-pc-tools",
        "groups": [{"key": "workbench", "label": "Workbench"}],
        "modules": [
            {
                "key": "events",
                "label": "Events",
                "group": "workbench",
                "summary": "Event review.",
            }
        ],
        "screens": [
            {
                "key": "events.pending",
                "label": "Pending",
                "module_key": "events",
                "group": "workbench",
                "summary": "Review pending events.",
                "view_type": "status",
            }
        ],
        "actions": [
            {
                "key": "events.pending.list",
                "label": "Pending Events",
                "endpoint": "/api/events/pending/",
                "intent": "list_pending_events",
                "screen_key": "events.pending",
                "view_type": "detail",
                "risk": "read",
                "source": "openapi:test",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
