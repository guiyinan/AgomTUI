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
        self.assertIn('"allowSvgDataImages": true', body)
        self.assertIn("/host/static/css/tui-workbench.css?v=", body)
        self.assertIn("/host/static/js/agomtui-runtime-core.js?v=", body)
        self.assertIn("/host/static/js/tui-workbench.js?v=", body)

    def test_render_runtime_html_can_disable_svg_data_images(self) -> None:
        body = render_runtime_html(
            title="Host Runtime",
            home_href="/host/",
            brand_label="Host TUI",
            api_base="/host-api/tui",
            asset_base="/host/static",
            allow_svg_data_images=False,
        ).decode("utf-8")

        self.assertIn('"allowSvgDataImages": false', body)

    def test_runtime_asset_serves_css_with_content_type(self) -> None:
        asset = runtime_asset("css/tui-workbench.css")

        self.assertEqual(asset.content_type, "text/css; charset=utf-8")
        self.assertIn(b".tui-shell", asset.body)

    def test_runtime_asset_rejects_path_traversal(self) -> None:
        with self.assertRaises(RuntimeAssetNotFound):
            runtime_asset("../tui_workbench.reference.html")

    def test_runtime_js_supports_legacy_limit_offset_pager_mode(self) -> None:
        asset = runtime_asset("js/tui-workbench.js").body.decode("utf-8")

        self.assertIn('pager.pagination_mode || pager.mode || ""', asset)
        self.assertIn('pagerMode === "limit_offset" ? "offset" : pagerMode', asset)

    def test_runtime_js_uses_metadata_dashboard_targets(self) -> None:
        asset = runtime_asset("js/tui-workbench.js").body.decode("utf-8")

        self.assertIn("function dashboardTargetScreen(panel)", asset)
        self.assertIn('return String(panel.target_screen || panel.screen_key || "");', asset)
        self.assertNotIn('"account-positions": "execution.accounts"', asset)
        self.assertNotIn('account: "execution.accounts"', asset)

    def test_runtime_js_missing_fields_modal_reuses_field_renderer(self) -> None:
        asset = runtime_asset("js/tui-workbench.js").body.decode("utf-8")

        self.assertIn("const promptAction = result.action || currentAction(actionKey)", asset)
        self.assertIn("renderField(promptAction", asset)
        self.assertIn("coerceFieldValue(field, input.value, input.checked)", asset)
        self.assertIn('form.querySelector("select, input, textarea")?.focus()', asset)

    def test_runtime_js_uses_favorite_copy_instead_of_pin_copy(self) -> None:
        asset = runtime_asset("js/tui-workbench.js").body.decode("utf-8")

        self.assertIn("收藏工作区", asset)
        self.assertNotIn("置顶工作区", asset)

    def test_runtime_js_suppresses_default_auto_run_before_catalog_drilldown(self) -> None:
        asset = runtime_asset("js/tui-workbench.js").body.decode("utf-8")

        self.assertIn("loadScreen(normalizedKey, { suppressAutoAction: true })", asset)
        self.assertIn("function renderScreen(screenSpec, options = {})", asset)
        self.assertIn("function loadScreen(screenKey, options = {})", asset)
        self.assertIn("defaultAction && !options.suppressAutoAction", asset)


if __name__ == "__main__":
    unittest.main()
