from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from agomtui_core import (
    GenericRuntimeViewModelBuilder,
    GovernedActionRunner,
    TuiMetadataValidationError,
    apply_tui_metadata_overrides,
    apply_default_field_values,
    build_confirmation_required_result,
    build_missing_fields_result,
    compact_tui_metadata_payload,
    missing_required_fields,
    normalize_runtime_metadata_payload,
    validate_tui_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


class SpyExecutor:
    def __init__(self, result: dict[str, object] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = result or {
            "response": {"status_code": 200},
            "view_model": {"kind": "message", "title": "OK"},
        }

    def execute(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(dict(kwargs))
        return self.result


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def append(self, record: dict[str, object]) -> None:
        self.records.append(record)


class RuntimeHelpersTests(unittest.TestCase):
    def test_missing_fields_result_uses_normalized_required_fields(self) -> None:
        action = {
            "key": "execution.accounts.rebalance",
            "label": "Submit Rebalance",
            "method": "POST",
            "risk": "write",
            "fields": [
                {"key": "account_id", "label": "Account ID", "required": True},
                {"key": "trade_date", "label": "Trade Date", "required": True, "default": "2026-06-23"},
            ],
        }

        resolved = apply_default_field_values(action, {})
        missing = missing_required_fields(action, resolved)

        self.assertEqual(resolved["trade_date"], "2026-06-23")
        self.assertEqual([field["key"] for field in missing], ["account_id"])

        result = build_missing_fields_result(action, missing)
        self.assertFalse(result["confirmation_required"])
        self.assertEqual(result["response"]["status_code"], 400)
        self.assertEqual(result["missing_fields"][0]["placeholder"], "Enter Account ID")

    def test_confirmation_required_result_uses_standard_contract(self) -> None:
        action = {
            "key": "execution.tasks.retry",
            "label": "Retry Task",
            "method": "POST",
            "risk": "write",
        }

        result = build_confirmation_required_result(
            action,
            message="Retry task TASK-9?",
            confirm_label="Retry",
            cancel_label="Keep Blocked",
        )

        self.assertTrue(result["confirmation_required"])
        self.assertEqual(result["response"]["status_code"], 409)
        self.assertEqual(result["confirmation"]["confirm_label"], "Retry")
        self.assertEqual(result["view_model"]["status"], "Pending confirmation")

    def test_generic_view_model_builder_infers_datagrid(self) -> None:
        builder = GenericRuntimeViewModelBuilder()
        action = {
            "key": "execution.accounts.list",
            "label": "Account Grid",
            "view_type": "datagrid",
            "view_model": {
                "rows_path": "items",
                "total_path": "total",
                "page_path": "page",
            },
        }
        payload = {
            "items": [
                {"account_id": "ACC-1", "nav": 123.4, "status": "ok"},
                {"account_id": "ACC-2", "nav": 98.7, "status": "warn"},
            ],
            "total": 2,
            "page": 1,
        }

        view_model = builder.infer(action=action, payload=payload, status_code=200)

        self.assertEqual(view_model["kind"], "datagrid")
        self.assertEqual(view_model["pager"]["total_rows"], 2)
        self.assertEqual(view_model["rows"][0]["account_id"], "ACC-1")
        self.assertEqual(view_model["columns"][0]["label"], "Account ID")

    def test_generic_view_model_builder_uses_offset_pagination_contract(self) -> None:
        builder = GenericRuntimeViewModelBuilder()
        action = {
            "key": "execution.events.list",
            "label": "Events",
            "view_type": "datagrid",
            "pagination": {
                "mode": "offset",
                "offset_param": "offset",
                "limit_param": "limit",
            },
            "view_model": {
                "rows_path": "results",
                "total_path": "total",
            },
        }
        payload = {
            "results": [{"id": index, "title": f"Event {index}"} for index in range(20, 40)],
            "total": 45,
        }

        view_model = builder.infer(
            action=action,
            payload=payload,
            status_code=200,
            request_params={"offset": 20, "limit": 20},
        )

        self.assertEqual(view_model["pager"]["mode"], "offset")
        self.assertEqual(view_model["pager"]["offset"], 20)
        self.assertEqual(view_model["pager"]["page"], 2)
        self.assertEqual(view_model["pager"]["page_size"], 20)
        self.assertTrue(view_model["pager"]["has_previous"])
        self.assertTrue(view_model["pager"]["has_next"])

    def test_generic_view_model_builder_detects_password_challenge(self) -> None:
        builder = GenericRuntimeViewModelBuilder()
        action = {
            "key": "shared.secret.detail",
            "label": "Shared Secret",
            "view_type": "detail",
        }
        payload = {
            "detail": "Password required for this artifact.",
            "requires_password": True,
        }

        view_model = builder.infer(action=action, payload=payload, status_code=401)

        self.assertEqual(view_model["kind"], "detail")
        self.assertEqual(view_model["status"], "Password required")
        self.assertTrue(any(field["key"] == "next_step" for field in view_model["fields"]))

    def test_runtime_metadata_normalization_applies_patches_and_hooks(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        duplicated = copy.deepcopy(payload["actions"][0])
        duplicated["key"] = "overview.audit"
        duplicated["label"] = "Audit Detail"
        payload["actions"].append(duplicated)
        validated = validate_tui_metadata(payload)

        def hook(current: dict[str, object]) -> dict[str, object]:
            updated = copy.deepcopy(current)
            coverage = dict(updated.get("coverage_summary") or {})
            coverage["hook_applied"] = 1
            updated["coverage_summary"] = coverage
            return updated

        normalized = normalize_runtime_metadata_payload(
            validated,
            redundant_screen_action_keys={"overview.home": {"overview.audit"}},
            action_patches={
                "overview.status": {
                    "view_model": {"rows_path": "items"},
                    "description": "Patched for runtime inference.",
                }
            },
            hooks=[hook],
        )

        self.assertEqual(len(normalized["actions"]), 1)
        self.assertEqual(normalized["actions"][0]["view_model"]["rows_path"], "items")
        self.assertEqual(normalized["coverage_summary"]["runtime_pruned_redundant_screen_actions"], 1)
        self.assertEqual(normalized["coverage_summary"]["runtime_patched_actions"], 1)
        self.assertEqual(normalized["coverage_summary"]["hook_applied"], 1)

    def test_runtime_metadata_normalization_applies_screen_patches(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )

        normalized = normalize_runtime_metadata_payload(
            validate_tui_metadata(payload),
            screen_patches={
                "overview.home": {
                    "dashboard_panels": [
                        {
                            "key": "status",
                            "title": "Status",
                            "kind": "detail",
                            "action_key": "overview.status",
                            "target_screen": "overview.home",
                        }
                    ]
                }
            },
        )

        panel = normalized["screens"][0]["dashboard_panels"][0]
        self.assertEqual(panel["target_screen"], "overview.home")
        self.assertEqual(normalized["coverage_summary"]["runtime_patched_screens"], 1)

    def test_runtime_metadata_screen_patch_skips_panels_with_unknown_actions(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )

        normalized = normalize_runtime_metadata_payload(
            validate_tui_metadata(payload),
            screen_patches={
                "overview.home": {
                    "summary": "Patched summary should not survive when all panels are invalid.",
                    "dashboard_panels": [
                        {
                            "key": "missing",
                            "title": "Missing",
                            "kind": "detail",
                            "action_key": "overview.missing",
                            "target_screen": "overview.home",
                        }
                    ]
                }
            },
        )

        self.assertEqual(normalized["screens"][0]["dashboard_panels"], [])
        self.assertEqual(normalized["screens"][0]["summary"], "Open the primary status view.")
        self.assertNotIn("runtime_patched_screens", normalized.get("coverage_summary", {}))

    def test_runtime_metadata_screen_patch_keeps_known_panels_when_others_are_unknown(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )

        normalized = normalize_runtime_metadata_payload(
            validate_tui_metadata(payload),
            screen_patches={
                "overview.home": {
                    "dashboard_panels": [
                        {
                            "key": "status",
                            "title": "Status",
                            "kind": "detail",
                            "action_key": "overview.status",
                            "target_screen": "overview.home",
                        },
                        {
                            "key": "missing",
                            "title": "Missing",
                            "kind": "detail",
                            "action_key": "overview.missing",
                            "target_screen": "overview.home",
                        },
                    ]
                }
            },
        )

        self.assertEqual(
            [panel["action_key"] for panel in normalized["screens"][0]["dashboard_panels"]],
            ["overview.status"],
        )
        self.assertEqual(normalized["coverage_summary"]["runtime_patched_screens"], 1)

    def test_metadata_overrides_patch_actions_and_fields_before_validation(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )

        patched = apply_tui_metadata_overrides(
            payload,
            {
                "registry_key": "default",
                "action_patches": {
                    "overview.status": {
                        "risk": "write",
                        "method": "POST",
                        "task_group": "00 Governed Actions",
                        "executor": "sync_latest_quotes",
                    }
                },
                "field_patches": {
                    "overview.status": [
                        {
                            "key": "symbols",
                            "label": "Asset Codes",
                            "input_type": "text",
                            "value_type": "string",
                            "required": True,
                            "binding": "body",
                            "placeholder": "AAPL,MSFT",
                        }
                    ]
                },
            },
        )

        validated = validate_tui_metadata(patched)
        action = validated["actions"][0]

        self.assertEqual(action["risk"], "write")
        self.assertTrue(action["confirmation_required"])
        self.assertTrue(action["audit_required"])
        self.assertEqual(action["sensitive_level"], "high")
        self.assertEqual(action["executor"], "sync_latest_quotes")
        self.assertEqual(action["fields"][0]["key"], "symbols")

    def test_metadata_accepts_runtime_pagination_aliases_and_file_input(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["field_aliases"] = {
            "company.keyword": ["keyword", "name", "companyName", "company_name"],
            "company.id": ["id", "cid", "companyId", "company_id"],
        }
        payload["actions"][0]["fields"] = [
            {
                "key": "keyword",
                "label": "Keyword",
                "semantic": "company.keyword",
                "aliases": ["creditCode", "credit_code"],
            },
            {
                "key": "csv_text",
                "label": "CSV File",
                "input_type": "file",
                "accept": ".csv,text/csv",
            },
            {
                "key": "pageNum",
                "label": "Page",
                "input_type": "number",
                "default": 1,
            },
            {
                "key": "pageSize",
                "label": "Page Size",
                "input_type": "number",
                "default": 10,
            },
        ]
        payload["actions"][0]["pagination"] = {
            "mode": "page",
            "page_param": "pageNum",
            "page_size_param": "pageSize",
        }

        validated = validate_tui_metadata(payload)
        action = validated["actions"][0]

        self.assertEqual(action["fields"][0]["semantic"], "company.keyword")
        self.assertEqual(action["fields"][1]["input_type"], "file")
        self.assertEqual(action["fields"][1]["value_type"], "string")
        self.assertEqual(action["pagination"]["page_param"], "pageNum")

    def test_governed_action_cannot_disable_confirmation_or_audit(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["actions"][0].update(
            {
                "risk": "write",
                "method": "POST",
                "confirmation_required": False,
                "audit_required": False,
            }
        )

        with self.assertRaises(TuiMetadataValidationError):
            validate_tui_metadata(payload)

    def test_metadata_accepts_rich_component_view_models(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["screens"][0]["view_type"] = "chart"
        payload["screens"][0]["dashboard_panels"] = [
            {
                "key": "trend-panel",
                "title": "Trend",
                "kind": "chart",
                "action_key": "overview.status",
                "target_screen": "overview.home",
            },
            {
                "key": "slot-panel",
                "title": "Host Slot",
                "kind": "host_slot",
                "target_screen": "overview.home",
            },
        ]
        payload["actions"][0].update(
            {
                "view_type": "table_chart",
                "view_model": {
                    "kind": "table_chart",
                    "renderer": "echarts",
                    "chart_type": "line",
                    "data_path": "data.history",
                    "x_path": "date",
                    "y_path": "value",
                    "table_rows_path": "data.rows",
                    "slot_key": "overview-slot",
                    "fallback_message": "Host content disabled.",
                },
            }
        )

        validated = validate_tui_metadata(payload)
        compacted = compact_tui_metadata_payload(validated)

        self.assertEqual(validated["actions"][0]["view_model"]["renderer"], "echarts")
        self.assertEqual(validated["screens"][0]["dashboard_panels"][0]["target_screen"], "overview.home")
        self.assertEqual(compacted["actions"][0]["view_model"]["kind"], "table_chart")

    def test_metadata_rejects_unknown_dashboard_target_screen(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["screens"][0]["dashboard_panels"] = [
            {
                "key": "status-panel",
                "title": "Status",
                "kind": "detail",
                "action_key": "overview.status",
                "target_screen": "missing.screen",
            }
        ]

        with self.assertRaises(TuiMetadataValidationError):
            validate_tui_metadata(payload)

    def test_metadata_accepts_image_view_models(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["screens"][0]["dashboard_panels"] = [
            {
                "key": "preview",
                "title": "Preview",
                "kind": "image",
                "action_key": "overview.status",
            }
        ]
        payload["actions"][0].update(
            {
                "view_type": "image",
                "view_model": {
                    "kind": "image",
                    "url_path": "data.image_url",
                    "alt_path": "data.alt",
                    "caption_path": "data.caption",
                },
            }
        )

        validated = validate_tui_metadata(payload)

        self.assertEqual(validated["actions"][0]["view_model"]["kind"], "image")
        self.assertEqual(validated["screens"][0]["dashboard_panels"][0]["kind"], "image")

    def test_metadata_accepts_user_experience_and_semantic_contract(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["screens"][0]["user_experience"] = {
            "journey": "workspace",
            "primary_task": "Review the current system status.",
            "primary_outcome": "Know whether the host is healthy enough to continue.",
            "empty_state_hint": "Run the main status check first.",
            "next_step_hint": "Move to the next operator task after the status check.",
        }
        payload["actions"][0]["result_semantics"] = ["primary_status"]
        payload["actions"][0]["fields"] = [
            {
                "key": "operator_prompt",
                "label": "Operator Prompt",
                "input_type": "textarea",
                "value_type": "string",
                "presentation_semantic": "prompt_text",
                "required": False,
            }
        ]
        payload["screens"][0]["dashboard_panels"] = [
            {
                "key": "status-panel",
                "title": "Status",
                "kind": "detail",
                "action_key": "overview.status",
                "target_screen": "overview.home",
                "user_priority": "p0",
                "presentation_semantic": "primary_status",
            }
        ]

        validated = validate_tui_metadata(payload)

        self.assertEqual(validated["screens"][0]["user_experience"]["journey"], "workspace")
        self.assertEqual(validated["actions"][0]["result_semantics"], ["primary_status"])
        self.assertEqual(validated["actions"][0]["fields"][0]["presentation_semantic"], "prompt_text")
        self.assertEqual(validated["screens"][0]["dashboard_panels"][0]["user_priority"], "p0")

    def test_metadata_accepts_and_compacts_dashboard_layout_contract(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(
                encoding="utf-8"
            )
        )
        payload["screens"][0]["dashboard_layout"] = "task_flow"

        validated = validate_tui_metadata(payload)
        compacted = compact_tui_metadata_payload(validated)

        self.assertEqual(validated["screens"][0]["dashboard_layout"], "task_flow")
        self.assertEqual(compacted["screens"][0]["dashboard_layout"], "task_flow")

    def test_metadata_rejects_unknown_dashboard_layout(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(
                encoding="utf-8"
            )
        )
        payload["screens"][0]["dashboard_layout"] = "masonry"

        with self.assertRaises(TuiMetadataValidationError):
            validate_tui_metadata(payload)

    def test_metadata_rejects_prompt_presentation_semantic_without_textarea(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["actions"][0]["fields"] = [
            {
                "key": "operator_prompt",
                "label": "Operator Prompt",
                "input_type": "text",
                "value_type": "string",
                "presentation_semantic": "prompt_text",
                "required": False,
            }
        ]

        with self.assertRaises(TuiMetadataValidationError):
            validate_tui_metadata(payload)

    def test_metadata_rejects_unsafe_renderer_name(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "examples" / "metadata" / "minimal.tui_operation_graph.json").read_text(encoding="utf-8")
        )
        payload["actions"][0]["view_model"] = {
            "kind": "chart",
            "renderer": "<script>",
        }

        with self.assertRaises(TuiMetadataValidationError):
            validate_tui_metadata(payload)

    def test_generic_view_model_builder_builds_chart_from_paths(self) -> None:
        builder = GenericRuntimeViewModelBuilder()
        action = {
            "key": "overview.nav",
            "label": "NAV Trend",
            "view_type": "chart",
            "view_model": {
                "kind": "chart",
                "chart_type": "line",
                "data_path": "history",
                "x_path": "date",
                "y_path": "nav",
            },
        }

        view_model = builder.infer(
            action=action,
            payload={"history": [{"date": "D1", "nav": 1.0}, {"date": "D2", "nav": 1.2}]},
            status_code=200,
        )

        self.assertEqual(view_model["kind"], "chart")
        self.assertEqual(view_model["series"][0]["points"][1]["label"], "D2")
        self.assertEqual(view_model["series"][0]["points"][1]["value"], 1.2)

    def test_generic_view_model_builder_builds_table_chart_and_host_slot(self) -> None:
        builder = GenericRuntimeViewModelBuilder()
        table_action = {
            "key": "overview.table_chart",
            "label": "Table Chart",
            "view_type": "table_chart",
            "view_model": {
                "kind": "table_chart",
                "data_path": "history",
                "x_path": "label",
                "y_path": "value",
                "table_rows_path": "rows",
            },
        }
        slot_action = {
            "key": "overview.slot",
            "label": "Slot",
            "view_type": "host_slot",
            "view_model": {
                "kind": "host_slot",
                "slot_key": "overview-slot",
                "partial_path": "partial",
            },
        }

        table_model = builder.infer(
            action=table_action,
            payload={
                "history": [{"label": "A", "value": 3}],
                "rows": [{"asset": "A", "weight": 0.4}],
            },
            status_code=200,
        )
        slot_model = builder.infer(
            action=slot_action,
            payload={"partial": "<div hx-get=\"/api/demo/partial/\">Ready</div>"},
            status_code=200,
        )

        self.assertEqual(table_model["kind"], "table_chart")
        self.assertEqual(table_model["table"]["rows"][0]["asset"], "A")
        self.assertEqual(slot_model["kind"], "host_slot")
        self.assertIn("hx-get", slot_model["partial_html"])

    def test_generic_view_model_builder_builds_image_from_url_paths(self) -> None:
        builder = GenericRuntimeViewModelBuilder()
        action = {
            "key": "overview.preview",
            "label": "Preview Image",
            "view_type": "image",
            "view_model": {
                "kind": "image",
                "url_path": "data.image_url",
                "alt_path": "data.alt",
                "caption_path": "data.caption",
            },
        }

        view_model = builder.infer(
            action=action,
            payload={
                "data": {
                    "image_url": "https://example.test/chart.png",
                    "alt": "Rendered chart",
                    "caption": "Latest generated chart.",
                }
            },
            status_code=200,
        )
        inferred_from_string = builder.infer(
            action={"key": "overview.raw_image", "label": "Raw Image", "view_type": "auto"},
            payload="https://example.test/photo.webp",
            status_code=200,
        )

        self.assertEqual(view_model["kind"], "image")
        self.assertEqual(view_model["url"], "https://example.test/chart.png")
        self.assertEqual(view_model["alt"], "Rendered chart")
        self.assertEqual(view_model["caption"], "Latest generated chart.")
        self.assertEqual(inferred_from_string["kind"], "image")
        self.assertEqual(inferred_from_string["url"], "https://example.test/photo.webp")

    def test_generic_view_model_builder_allows_svg_data_images_by_default(self) -> None:
        svg_data_url = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E"

        view_model = GenericRuntimeViewModelBuilder().infer(
            action={"key": "overview.svg", "label": "SVG Preview", "view_type": "auto"},
            payload=svg_data_url,
            status_code=200,
        )
        disabled_model = GenericRuntimeViewModelBuilder(allow_svg_data_images=False).infer(
            action={"key": "overview.svg", "label": "SVG Preview", "view_type": "auto"},
            payload=svg_data_url,
            status_code=200,
        )

        self.assertEqual(view_model["kind"], "image")
        self.assertEqual(view_model["url"], svg_data_url)
        self.assertEqual(disabled_model["kind"], "message")

    def test_reference_runtime_exposes_rich_renderer_contract(self) -> None:
        runtime_js = (
            REPO_ROOT
            / "packages"
            / "agomtui-runtime"
            / "reference"
            / "static"
            / "js"
            / "tui-workbench.js"
        ).read_text(encoding="utf-8")

        self.assertIn("window.AgomTUIRenderers", runtime_js)
        self.assertIn("registerRenderer", runtime_js)
        self.assertIn("renderImageMarkup", runtime_js)
        self.assertIn("showImagePreview", runtime_js)
        self.assertIn("data-image-preview", runtime_js)
        self.assertIn("allowSvgDataImages", runtime_js)
        self.assertIn("allowHostHtmlSlots", runtime_js)
        self.assertIn("window.htmx.process", runtime_js)

    def test_governed_runner_blocks_unconfirmed_action_before_executor_and_audits_attempt(self) -> None:
        action = {
            "key": "execution.accounts.rebalance",
            "label": "Submit Rebalance",
            "method": "POST",
            "endpoint": "/api/demo/accounts/rebalance/",
            "risk": "write",
            "confirmation_required": True,
            "audit_required": True,
            "sensitive_level": "high",
            "fields": [{"key": "account_id", "label": "Account ID", "required": True}],
        }
        executor = SpyExecutor()
        audit = MemoryAuditSink()

        result = GovernedActionRunner(executor, audit).execute(
            action,
            {"account_id": "ACC-1"},
            actor="operator.demo",
        )

        self.assertTrue(result["confirmation_required"])
        self.assertEqual(executor.calls, [])
        self.assertEqual(audit.records[0]["outcome"], "blocked_confirmation_required")
        self.assertEqual(audit.records[0]["actor"], "operator.demo")

    def test_governed_runner_blocks_missing_fields_before_executor_and_audits_attempt(self) -> None:
        action = {
            "key": "execution.tasks.retry",
            "label": "Retry Task",
            "method": "POST",
            "endpoint": "/api/demo/tasks/retry/",
            "risk": "write",
            "confirmation_required": True,
            "audit_required": True,
            "fields": [{"key": "task_id", "label": "Task ID", "required": True}],
        }
        executor = SpyExecutor()
        audit = MemoryAuditSink()

        result = GovernedActionRunner(executor, audit).execute(action, {}, actor="operator.demo")

        self.assertEqual(result["response"]["status_code"], 400)
        self.assertEqual(result["missing_fields"][0]["key"], "task_id")
        self.assertEqual(executor.calls, [])
        self.assertEqual(audit.records[0]["outcome"], "rejected_missing_fields")

    def test_governed_runner_blocks_reauth_before_executor_and_audits_attempt(self) -> None:
        action = {
            "key": "admin.secrets.rotate",
            "label": "Rotate Secret",
            "method": "POST",
            "endpoint": "/api/demo/secrets/rotate/",
            "risk": "admin",
            "confirmation_required": True,
            "requires_password": True,
            "audit_required": True,
            "fields": [{"key": "secret_id", "label": "Secret ID", "required": True}],
        }
        executor = SpyExecutor()
        audit = MemoryAuditSink()

        result = GovernedActionRunner(executor, audit).execute(
            action,
            {"secret_id": "SEC-1"},
            actor="operator.demo",
            confirmed=True,
            confirmation_evidence={"confirmed": True, "confirmed_at": "2026-06-23T10:00:00Z"},
        )

        self.assertTrue(result["password_challenge_required"])
        self.assertEqual(executor.calls, [])
        self.assertEqual(audit.records[0]["outcome"], "blocked_reauth_required")

    def test_governed_runner_executes_only_after_pipeline_and_masks_audit_params(self) -> None:
        action = {
            "key": "admin.secrets.rotate",
            "label": "Rotate Secret",
            "method": "POST",
            "endpoint": "/api/demo/secrets/rotate/",
            "risk": "admin",
            "confirmation_required": True,
            "requires_password": True,
            "audit_required": True,
            "sensitive_level": "critical",
            "fields": [
                {"key": "secret_id", "label": "Secret ID", "required": True},
                {"key": "new_password", "label": "New Password", "required": True},
            ],
        }
        executor = SpyExecutor()
        audit = MemoryAuditSink()

        result = GovernedActionRunner(
            executor,
            audit,
            reauth_verifier=lambda action, evidence, context: evidence.get("credential") == "valid-password",
        ).execute(
            action,
            {"secret_id": "SEC-1", "new_password": "raw-secret"},
            actor="operator.demo",
            confirmed=True,
            confirmation_evidence={"confirmed": True, "confirmed_at": "2026-06-23T10:00:00Z"},
            reauth_evidence={
                "credential": "valid-password",
                "verified": True,
                "verified_at": "2026-06-23T10:00:02Z",
                "method": "password",
            },
        )

        self.assertEqual(result["response"]["status_code"], 200)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(audit.records[0]["outcome"], "succeeded")
        self.assertEqual(audit.records[0]["params"]["new_password"], "***")
        self.assertTrue(audit.records[0]["confirmation"]["confirmed"])
        self.assertTrue(audit.records[0]["reauth"]["verified"])

    def test_audit_required_action_cannot_execute_without_audit_sink(self) -> None:
        action = {
            "key": "execution.accounts.rebalance",
            "label": "Submit Rebalance",
            "method": "POST",
            "endpoint": "/api/demo/accounts/rebalance/",
            "risk": "write",
            "confirmation_required": True,
            "audit_required": True,
        }
        executor = SpyExecutor()

        with self.assertRaises(RuntimeError):
            GovernedActionRunner(executor).execute(
                action,
                {},
                confirmed=True,
                confirmation_evidence={"confirmed": True},
            )
        self.assertEqual(executor.calls, [])


if __name__ == "__main__":
    unittest.main()
