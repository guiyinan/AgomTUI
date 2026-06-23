from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from agomtui_core import (
    GenericRuntimeViewModelBuilder,
    apply_default_field_values,
    build_confirmation_required_result,
    build_missing_fields_result,
    missing_required_fields,
    normalize_runtime_metadata_payload,
    validate_tui_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


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


if __name__ == "__main__":
    unittest.main()
