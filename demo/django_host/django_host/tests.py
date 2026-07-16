from __future__ import annotations

from django.test import Client, SimpleTestCase


class DjangoHostDemoTests(SimpleTestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_host_home_page_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Real Django Host")
        self.assertContains(response, "Open Django-Mounted TUI")
        self.assertContains(response, "AgomTUI Django Host")

    def test_host_tui_uses_local_runtime_assets(self) -> None:
        response = self.client.get("/tui/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/tui/static/css/tui-workbench.css")
        self.assertContains(response, "AgomTUI Host")

    def test_runtime_asset_endpoint_serves_css(self) -> None:
        response = self.client.get("/tui/static/css/tui-workbench.css")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/css; charset=utf-8")
        self.assertContains(response, ".tui-shell")

    def test_catalog_endpoint_returns_host_payload(self) -> None:
        response = self.client.get("/api/tui/catalog/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["host"]["project"], "AgomTradePro Demo Host")
        self.assertEqual(payload["default_screen"], "command-center.overview")

    def test_bootstrap_endpoint_returns_catalog_and_screen(self) -> None:
        response = self.client.get("/api/tui/bootstrap/?screen_key=missing-screen")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["contract"], "tui-bootstrap.v1")
        self.assertEqual(payload["requested_screen"], "missing-screen")
        self.assertEqual(payload["resolved_screen"], "command-center.overview")
        self.assertTrue(payload["restored"])
        self.assertEqual(payload["screen"]["screen"]["key"], "command-center.overview")

    def test_host_runtime_action_executes(self) -> None:
        response = self.client.post(
            "/api/tui/actions/execution.tasks.ai-brief/run/",
            data='{"params":{"task_id":"TASK-002"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["host"]["project"], "AgomTradePro Demo Host")
        self.assertEqual(payload["view_model"]["title"], "AI Operator Brief")
