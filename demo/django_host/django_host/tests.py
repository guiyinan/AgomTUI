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

    def test_catalog_endpoint_returns_host_payload(self) -> None:
        response = self.client.get("/api/tui/catalog/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["host"]["project"], "AgomTradePro Demo Host")
        self.assertEqual(payload["default_screen"], "command-center.overview")

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
