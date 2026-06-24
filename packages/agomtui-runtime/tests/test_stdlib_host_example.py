from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HOST_EXAMPLE = REPO_ROOT / "examples" / "hosts" / "stdlib_host.py"


def load_host_module():
    spec = importlib.util.spec_from_file_location("stdlib_host_example", HOST_EXAMPLE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load stdlib host example")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StdlibHostExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.host = load_host_module()

    def test_catalog_is_host_neutral(self) -> None:
        catalog = self.host.build_catalog()

        self.assertEqual(catalog["default_screen"], "operations.accounts")
        self.assertEqual(catalog["host"]["kind"], "stdlib-http")

    def test_screen_exposes_generic_actions(self) -> None:
        screen = self.host.build_screen("operations.accounts")

        action_keys = {action["key"] for action in screen["actions"]}
        self.assertIn("operations.accounts.list", action_keys)
        self.assertIn("operations.accounts.adjust-limit", action_keys)

    def test_action_result_uses_runtime_contract(self) -> None:
        result = self.host.execute_action("operations.accounts.list")

        self.assertEqual(result["response"]["status_code"], 200)
        self.assertEqual(result["view_model"]["kind"], "datagrid")
        self.assertGreaterEqual(len(result["view_model"]["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
