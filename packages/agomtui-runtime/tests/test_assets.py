from __future__ import annotations

import unittest

from agomtui_runtime import RuntimeAssetNotFound, render_runtime_html, runtime_asset


class RuntimeAssetHelperTests(unittest.TestCase):
    def test_render_runtime_html_injects_host_routes(self) -> None:
        body = render_runtime_html(
            title="Host Runtime",
            home_href="/host/",
            brand_label="Host TUI",
            api_base="/host-api/tui",
            asset_base="/host/static",
        ).decode("utf-8")

        self.assertIn("<title>Host Runtime</title>", body)
        self.assertIn('href="/host/"', body)
        self.assertIn(">Host TUI<", body)
        self.assertIn('"apiBase": "/host-api/tui"', body)
        self.assertIn("/host/static/css/tui-workbench.css?v=", body)
        self.assertIn("/host/static/js/tui-workbench.js?v=", body)

    def test_runtime_asset_serves_css_with_content_type(self) -> None:
        asset = runtime_asset("css/tui-workbench.css")

        self.assertEqual(asset.content_type, "text/css; charset=utf-8")
        self.assertIn(b".tui-shell", asset.body)

    def test_runtime_asset_rejects_path_traversal(self) -> None:
        with self.assertRaises(RuntimeAssetNotFound):
            runtime_asset("../tui_workbench.reference.html")


if __name__ == "__main__":
    unittest.main()
