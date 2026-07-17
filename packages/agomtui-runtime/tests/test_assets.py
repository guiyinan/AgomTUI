from __future__ import annotations

import json
import unittest
from hashlib import sha256
from pathlib import Path

from agomtui_runtime import RuntimeAssetNotFound, render_runtime_html, runtime_asset


class RuntimeAssetHelperTests(unittest.TestCase):
    def test_synchronized_runtime_files_match_upstream_manifest_hashes(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (package_root / "reference" / "agomtui-runtime.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        synchronized_files = {
            **{
                f"frontend/agomtui-runtime/src/{name}": package_root
                / "frontend"
                / "src"
                / name
                for name in (
                    "api.js",
                    "dashboard-layout.js",
                    "events.js",
                    "extensions.js",
                    "index.js",
                    "pagination.js",
                    "performance.js",
                    "state.js",
                )
            },
            "static/js/agomtui-runtime-core.js": package_root
            / "reference"
            / "static"
            / "js"
            / "agomtui-runtime-core.js",
            "static/js/tui-workbench.js": package_root
            / "reference"
            / "static"
            / "js"
            / "tui-workbench.js",
            "static/css/tui-workbench.css": package_root
            / "reference"
            / "static"
            / "css"
            / "tui-workbench.css",
        }

        for upstream_path, local_path in synchronized_files.items():
            normalized = local_path.read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(
                sha256(normalized).hexdigest(),
                manifest["files"][upstream_path],
                upstream_path,
            )

    def test_runtime_manifest_keeps_agomtradepro_as_the_only_source_owner(self) -> None:
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "reference"
            / "agomtui-runtime.manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["source_owner"], "AgomTradePro")
        self.assertEqual(manifest["direction"], "AgomTradePro -> AgOMTUI")

        core_schema_path = (
            Path(__file__).resolve().parents[2]
            / "agomtui-core"
            / "src"
            / "agomtui_core"
            / "schema"
            / "tui_metadata.schema.v3.json"
        )
        core_schema = json.loads(core_schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            core_schema["$defs"]["screen"]["properties"]["dashboard_layout"]["enum"],
            manifest["contracts"]["screen_dashboard_layouts"],
        )

        sync_manifest_path = (
            Path(__file__).resolve().parents[3]
            / "sync"
            / "agomtradepro"
            / "runtime-shell.manifest.json"
        )
        sync_manifest = json.loads(sync_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(sync_manifest["source_owner"], "AgomTradePro")
        self.assertEqual(sync_manifest["boundary"]["direction"], "one-way")

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

    def test_runtime_dashboard_flow_and_module_rail_are_content_safe(self) -> None:
        script = runtime_asset("js/tui-workbench.js").body.decode("utf-8")
        css = runtime_asset("css/tui-workbench.css").body.decode("utf-8")

        self.assertIn("function revealModuleScreen(screenButton)", script)
        self.assertIn(
            'screenButton.scrollIntoView({ block: "nearest", inline: "nearest" })',
            script,
        )
        self.assertIn(
            "const contentFlow = desktopColumns === 1 || isOperatorHomeScreen(screen?.key)",
            script,
        )
        self.assertIn(
            "runtimeCore.dashboardDesktopColumns(screen, runtimeConfig.host || {})",
            script,
        )
        self.assertIn("els.moduleTree.hidden = state.railCollapsed", script)
        self.assertIn("els.moduleTree.inert = state.railCollapsed", script)
        self.assertIn(".tui-dashboard-grid.is-content-flow", css)
        self.assertIn(".tui-dashboard-grid.is-content-flow .tui-dash-panel", css)
        self.assertIn(
            ".tui-app.is-rail-collapsed .tui-rail .tui-titlebar-text",
            css,
        )


if __name__ == "__main__":
    unittest.main()
