from __future__ import annotations

import copy
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "agomtui-core" / "src"
RUNTIME_SRC = ROOT / "packages" / "agomtui-runtime" / "src"
METADATA_PATH = ROOT / "examples" / "metadata" / "generic_operations.tui_operation_graph.json"
HOST = "127.0.0.1"
PORT = 8040

for package_src in (CORE_SRC, RUNTIME_SRC):
    package_path = str(package_src)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from agomtui_core import build_runtime_action_result, validate_tui_metadata  # noqa: E402
from agomtui_runtime import render_runtime_html, runtime_asset  # noqa: E402


ACCOUNT_ROWS = [
    {"account_id": "ACC-1001", "name": "Core Equity", "status": "active", "limit": 2500000},
    {"account_id": "ACC-2002", "name": "Income Sleeve", "status": "review", "limit": 1500000},
]


def load_metadata() -> dict[str, Any]:
    return validate_tui_metadata(json.loads(METADATA_PATH.read_text(encoding="utf-8")))


METADATA = load_metadata()


def actions_by_key() -> dict[str, dict[str, Any]]:
    return {str(action["key"]): copy.deepcopy(action) for action in METADATA["actions"]}


def build_catalog() -> dict[str, Any]:
    actions = METADATA["actions"]
    groups = []
    for group in METADATA["groups"]:
        modules = []
        for module in METADATA["modules"]:
            if module["group"] != group["key"]:
                continue
            screens = []
            action_count = 0
            for screen in METADATA["screens"]:
                if screen["module_key"] != module["key"]:
                    continue
                screen_action_count = sum(1 for action in actions if action["screen_key"] == screen["key"])
                action_count += screen_action_count
                screens.append(
                    {
                        "key": screen["key"],
                        "label": screen["label"],
                        "view_type": screen["view_type"],
                        "action_count": screen_action_count,
                    }
                )
            modules.append(
                {
                    "key": module["key"],
                    "label": module["label"],
                    "summary": module["summary"],
                    "action_count": action_count,
                    "screens": screens,
                }
            )
        groups.append({"key": group["key"], "label": group["label"], "modules": modules})
    return {
        "default_screen": METADATA["default_screen"],
        "groups": groups,
        "version": METADATA["version"],
        "registry_key": METADATA["registry_key"],
        "host": {"kind": "stdlib-http", "project": "Generic Operations Host"},
    }


def build_screen(screen_key: str) -> dict[str, Any]:
    screen = next((item for item in METADATA["screens"] if item["key"] == screen_key), None)
    if screen is None:
        raise KeyError(screen_key)
    module = next(item for item in METADATA["modules"] if item["key"] == screen["module_key"])
    actions = [copy.deepcopy(action) for action in METADATA["actions"] if action["screen_key"] == screen_key]
    return {"module": copy.deepcopy(module), "screen": copy.deepcopy(screen), "actions": actions}


def execute_action(action_key: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    action = actions_by_key().get(action_key)
    if action is None:
        raise KeyError(action_key)

    if action_key == "operations.accounts.list":
        return build_runtime_action_result(
            action,
            {
                "kind": "datagrid",
                "title": "Accounts",
                "status": "2 accounts",
                "columns": [
                    {"key": "account_id", "label": "Account"},
                    {"key": "name", "label": "Name"},
                    {"key": "status", "label": "Status"},
                    {"key": "limit", "label": "Limit"},
                ],
                "rows": ACCOUNT_ROWS,
                "pager": {"page": 1, "total_pages": 1, "total_rows": len(ACCOUNT_ROWS)},
            },
            raw_response={"items": ACCOUNT_ROWS, "total": len(ACCOUNT_ROWS), "page": 1},
        )

    if action_key == "operations.accounts.detail":
        account_id = str(params.get("account_id") or "ACC-1001")
        row = next((item for item in ACCOUNT_ROWS if item["account_id"] == account_id), ACCOUNT_ROWS[0])
        return build_runtime_action_result(
            action,
            {
                "kind": "detail",
                "title": row["name"],
                "status": row["status"],
                "fields": [
                    {"key": "account_id", "label": "Account", "value": row["account_id"]},
                    {"key": "limit", "label": "Limit", "value": row["limit"]},
                ],
            },
            raw_response={"account": row},
        )

    if action_key == "operations.accounts.adjust-limit":
        return build_runtime_action_result(
            action,
            {
                "kind": "message",
                "title": "Limit update accepted",
                "status": "Queued for host execution",
                "sections": [
                    {
                        "title": "Submitted params",
                        "items": [
                            {"label": "Account", "value": str(params.get("account_id") or "")},
                            {"label": "Limit", "value": str(params.get("limit") or "")},
                        ],
                    }
                ],
            },
            raw_response={"queued": True, "params": params},
        )

    if action_key == "operations.insights.kpi":
        series = [
            {"label": "Open", "value": 42},
            {"label": "In Review", "value": 7},
            {"label": "Resolved", "value": 18},
        ]
        return build_runtime_action_result(
            action,
            {"kind": "kpi_trend", "title": "Operations KPI", "status": "Current day", "series": series},
            raw_response={"series": series},
        )

    raise KeyError(action_key)


class StdlibHostHandler(BaseHTTPRequestHandler):
    server_version = "AgomTuiStdlibHost/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            body = render_runtime_html(
                title="Generic Operations Host",
                home_href="/",
                brand_label="Generic TUI",
                api_base="/api/tui",
                asset_base="/static",
            )
            self.respond(body, "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            try:
                asset = runtime_asset(path.removeprefix("/static/"))
            except FileNotFoundError:
                self.respond_json({"ok": False, "error": f"Unknown asset: {path}"}, HTTPStatus.NOT_FOUND)
                return
            self.respond(asset.body, asset.content_type)
            return
        if path == "/api/tui/catalog/":
            self.respond_json(build_catalog())
            return
        if path.startswith("/api/tui/screens/") and path.endswith("/"):
            screen_key = path.removeprefix("/api/tui/screens/").removesuffix("/")
            try:
                self.respond_json(build_screen(screen_key))
            except KeyError:
                self.respond_json({"ok": False, "error": f"Unknown screen: {screen_key}"}, HTTPStatus.NOT_FOUND)
            return
        self.respond_json({"ok": False, "error": f"Unknown route: {path}"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not (path.startswith("/api/tui/actions/") and path.endswith("/run/")):
            self.respond_json({"ok": False, "error": f"Unknown route: {path}"}, HTTPStatus.NOT_FOUND)
            return
        action_key = path.removeprefix("/api/tui/actions/").removesuffix("/run/")
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.respond_json({"ok": False, "error": "Invalid JSON body"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            self.respond_json(execute_action(action_key, payload.get("params") or {}))
        except KeyError:
            self.respond_json({"ok": False, "error": f"Unknown action: {action_key}"}, HTTPStatus.NOT_FOUND)

    def respond(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.respond(body, "application/json; charset=utf-8", status)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), StdlibHostHandler)
    print(f"Generic operations host: http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
