from __future__ import annotations

import copy
import html
import json
import re
import sys
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "packages" / "agomtui-core" / "src"
COMPILER_SRC = ROOT / "packages" / "agomtui-compiler" / "src"
RUNTIME_SRC = ROOT / "packages" / "agomtui-runtime" / "src"
FIXTURES = ROOT / "demo" / "fixtures"
HOST = "127.0.0.1"
PORT = 8020
DJANGO_HOST = "127.0.0.1"
DJANGO_PORT = 8030

for package_src in (CORE_SRC, COMPILER_SRC, RUNTIME_SRC):
    package_path = str(package_src)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from agomtui_core import (  # noqa: E402
    TUI_METADATA_SCHEMA_PATH,
    GovernedActionRunner,
    apply_default_field_values,
    build_confirmation_required_result,
    build_missing_fields_result,
    build_runtime_action_result,
    missing_required_fields,
    normalize_runtime_metadata_payload,
    validate_tui_metadata,
)
from agomtui_compiler.collector import (  # noqa: E402
    CollectionContext,
    DjangoContractManifestCollector,
    OpenApiSpecCollector,
)
from agomtui_compiler.synthesizer import (  # noqa: E402
    MetadataSynthesisRequest,
    MetadataSynthesisResult,
    PromptOnlySynthesizer,
    SkillBackedSynthesizer,
)
from agomtui_compiler.workflow import CompilerWorkflow  # noqa: E402
from agomtui_runtime import render_runtime_html as render_embeddable_runtime_html  # noqa: E402
from agomtui_runtime import runtime_asset  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")


RAW_CANDIDATE = load_json(FIXTURES / "standalone.tui_operation_graph.json")
RAW_SKILL_RESULT = load_json(FIXTURES / "standalone.skill_result.json")
VALIDATED_METADATA = normalize_runtime_metadata_payload(
    validate_tui_metadata(copy.deepcopy(RAW_CANDIDATE))
)
OPENAPI_FIXTURE = load_json(FIXTURES / "standalone.openapi.json")
DJANGO_CONTRACT_FIXTURE = load_json(FIXTURES / "standalone.django_contract_manifest.json")


class InlineCandidateSynthesizer(PromptOnlySynthesizer):
    def __init__(self, candidate_payload: dict[str, Any], *, model_name: str, reasoning_note: str) -> None:
        self._candidate_payload = candidate_payload
        self.model_name = model_name
        self.reasoning_note = reasoning_note

    def synthesize(self, request: MetadataSynthesisRequest) -> MetadataSynthesisResult:
        del request
        return MetadataSynthesisResult(
            candidate_payload=copy.deepcopy(self._candidate_payload),
            model_name=self.model_name,
            reasoning_note=self.reasoning_note,
        )


class InlineSkillBackend:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def complete(self, messages: list[Any]) -> dict[str, Any]:
        del messages
        return copy.deepcopy(self.payload)


def compiler_collectors() -> list[Any]:
    return [
        OpenApiSpecCollector(FIXTURES / "standalone.openapi.json"),
        DjangoContractManifestCollector(FIXTURES / "standalone.django_contract_manifest.json"),
    ]


def compiler_context() -> CollectionContext:
    return CollectionContext(project_root=ROOT, host_kind="django")


def build_compiler_demo() -> dict[str, Any]:
    prompt_synth = PromptOnlySynthesizer()
    workflow = CompilerWorkflow(collectors=compiler_collectors(), synthesizer=prompt_synth)
    evidence_bundle = workflow.collect(compiler_context())
    request = MetadataSynthesisRequest(
        schema_text=TUI_METADATA_SCHEMA_PATH.read_text(encoding="utf-8"),
        evidence=evidence_bundle,
        registry_key="demo",
        generation_note="Standalone compiler walkthrough.",
    )
    prompt = prompt_synth.build_prompt(request)
    messages = prompt_synth.build_messages(request)

    static_workflow = CompilerWorkflow(
        collectors=compiler_collectors(),
        synthesizer=InlineCandidateSynthesizer(
            RAW_CANDIDATE,
            model_name="static-demo-candidate",
            reasoning_note="Curated candidate metadata used by the standalone demo runtime.",
        ),
    )
    static_result = static_workflow.compile(
        context=compiler_context(),
        schema_path=TUI_METADATA_SCHEMA_PATH,
        registry_key="demo",
        generation_note="Standalone demo compile-static walkthrough.",
    )

    skill_workflow = CompilerWorkflow(
        collectors=compiler_collectors(),
        synthesizer=SkillBackedSynthesizer(
            InlineSkillBackend(RAW_SKILL_RESULT),
            model_name="standalone-demo-skill",
        ),
    )
    skill_result = skill_workflow.compile(
        context=compiler_context(),
        schema_path=TUI_METADATA_SCHEMA_PATH,
        registry_key="demo",
        generation_note="Standalone demo compile-skill-result walkthrough.",
    )

    return {
        "inputs": {
            "openapi": OPENAPI_FIXTURE,
            "django_contract_manifest": DJANGO_CONTRACT_FIXTURE,
        },
        "skill_request": {
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "constraints": prompt.constraints,
            "source_counts": dict(evidence_bundle.counts),
            "expected_result_shape": {
                "candidate_payload": "<metadata-json-object>",
                "model_name": "<skill-or-model-name>",
                "reasoning_note": "<optional-short-note>",
            },
        },
        "compile_static": {
            "validated_payload": static_result.validated_payload,
            "compacted_payload": static_result.compacted_payload,
            "evidence_payload": static_result.evidence_payload,
            "source_counts": static_result.source_counts,
        },
        "compile_skill_result": {
            "validated_payload": skill_result.validated_payload,
            "compacted_payload": skill_result.compacted_payload,
            "evidence_payload": skill_result.evidence_payload,
            "source_counts": skill_result.source_counts,
        },
    }


COMPILER_DEMO = build_compiler_demo()

HOST_DEMO_INFO = {
    "project_name": "AgomTradePro Demo Host",
    "environment": "staging",
    "user": "operator.demo",
    "host_kind": "django",
    "metadata_repository": "DjangoPublishedMetadataRepository",
    "action_executor": "DjangoActionExecutor",
    "registry_key": "agomtradepro-staging",
    "openapi_export": "/integration-contracts/openapi.json",
    "django_contract_export": "/integration-contracts/django-contract-manifest.json",
    "published_metadata_export": "/integration-contracts/published-metadata.json",
    "runtime_entry": "/standalone/?mode=integration",
    "catalog_endpoint": "/integration-api/tui/catalog/",
}


ACCOUNT_ROWS = [
    {
        "account_id": "ACC-1001",
        "account_name": "Core Equity",
        "risk_level": "high",
        "nav": "125.4M",
        "cash_pct": "14.2%",
        "status": "观察",
        "owner": "Lina",
        "updated_at": "2026-06-22 09:10",
    },
    {
        "account_id": "ACC-1042",
        "account_name": "Dividend Income",
        "risk_level": "medium",
        "nav": "83.9M",
        "cash_pct": "9.8%",
        "status": "正常",
        "owner": "Yao",
        "updated_at": "2026-06-22 09:12",
    },
    {
        "account_id": "ACC-1088",
        "account_name": "Macro Overlay",
        "risk_level": "high",
        "nav": "41.7M",
        "cash_pct": "28.3%",
        "status": "触发",
        "owner": "Kai",
        "updated_at": "2026-06-22 09:15",
    },
    {
        "account_id": "ACC-1099",
        "account_name": "Credit Rotation",
        "risk_level": "low",
        "nav": "57.2M",
        "cash_pct": "5.4%",
        "status": "正常",
        "owner": "Mira",
        "updated_at": "2026-06-22 09:18",
    },
    {
        "account_id": "ACC-1130",
        "account_name": "Asia Tactical",
        "risk_level": "medium",
        "nav": "63.1M",
        "cash_pct": "11.0%",
        "status": "运行",
        "owner": "Owen",
        "updated_at": "2026-06-22 09:20",
    },
    {
        "account_id": "ACC-1185",
        "account_name": "Hedge Sleeve",
        "risk_level": "high",
        "nav": "18.6M",
        "cash_pct": "31.6%",
        "status": "观察",
        "owner": "Yuki",
        "updated_at": "2026-06-22 09:21",
    },
]

TASK_ROWS = [
    {
        "task_id": "TASK-002",
        "task_type": "Risk refresh",
        "status": "blocked",
        "owner": "Jo",
        "updated_at": "2026-06-22 09:08",
        "priority": "P1",
    },
    {
        "task_id": "TASK-004",
        "task_type": "Trade enrich",
        "status": "queued",
        "owner": "Mai",
        "updated_at": "2026-06-22 09:11",
        "priority": "P2",
    },
    {
        "task_id": "TASK-009",
        "task_type": "FX hedge",
        "status": "running",
        "owner": "Ren",
        "updated_at": "2026-06-22 09:14",
        "priority": "P1",
    },
    {
        "task_id": "TASK-010",
        "task_type": "Daily publish",
        "status": "queued",
        "owner": "Ana",
        "updated_at": "2026-06-22 09:17",
        "priority": "P3",
    },
    {
        "task_id": "TASK-015",
        "task_type": "Compliance note",
        "status": "blocked",
        "owner": "Wei",
        "updated_at": "2026-06-22 09:19",
        "priority": "P2",
    },
    {
        "task_id": "TASK-018",
        "task_type": "Snapshot verify",
        "status": "running",
        "owner": "Ivy",
        "updated_at": "2026-06-22 09:22",
        "priority": "P2",
    },
]

REGIME_SNAPSHOT = {
    "current_regime": "RECOVERY",
    "confidence": "78%",
    "trend": "增长修复",
    "warning": "利率敏感资产仍需观察资金切换速度。",
    "updated_at": "2026-06-22 09:22",
}

RICH_NAV_HISTORY = [
    {"date": "06-17", "nav": 100.0},
    {"date": "06-18", "nav": 101.4},
    {"date": "06-19", "nav": 100.9},
    {"date": "06-20", "nav": 103.2},
    {"date": "06-21", "nav": 104.7},
    {"date": "06-22", "nav": 106.1},
]

RICH_ALLOCATION_ROWS = [
    {"asset": "Equity", "weight": 42, "target": 40, "status": "overweight"},
    {"asset": "Rates", "weight": 18, "target": 20, "status": "watch"},
    {"asset": "Credit", "weight": 24, "target": 25, "status": "aligned"},
    {"asset": "Cash", "weight": 16, "target": 15, "status": "buffer"},
]


def action_index() -> dict[str, dict[str, Any]]:
    return {str(action["key"]): copy.deepcopy(action) for action in VALIDATED_METADATA["actions"]}


ACTIONS_BY_KEY = action_index()
AUDIT_RECORDS: list[dict[str, Any]] = []


class DemoAuditSink:
    def append(self, record: dict[str, Any]) -> None:
        AUDIT_RECORDS.append(copy.deepcopy(record))


class DemoActionExecutor:
    def execute(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any],
        body: dict[str, Any],
        context: Any | None = None,
    ) -> dict[str, Any]:
        del method, endpoint, body
        action_key = str((context or {}).get("action_key") or "")
        return execute_action_logic(action_key, params, confirmed=True)


def verify_demo_reauth(action: dict[str, Any], evidence: dict[str, Any], context: Any | None = None) -> bool:
    del action, context
    return str(evidence.get("credential") or "") == "demo-password"


def get_action(action_key: str) -> dict[str, Any]:
    action = ACTIONS_BY_KEY.get(action_key)
    if not action:
        raise KeyError(action_key)
    return copy.deepcopy(action)


def build_catalog() -> dict[str, Any]:
    actions = VALIDATED_METADATA["actions"]
    modules = VALIDATED_METADATA["modules"]
    screens = VALIDATED_METADATA["screens"]
    groups = []
    for group in VALIDATED_METADATA["groups"]:
        group_modules = []
        for module in modules:
            if module["group"] != group["key"]:
                continue
            module_screens = []
            module_action_count = 0
            for screen in screens:
                if screen["module_key"] != module["key"]:
                    continue
                action_count = sum(1 for action in actions if action["screen_key"] == screen["key"])
                module_action_count += action_count
                module_screens.append(
                    {
                        "key": screen["key"],
                        "label": screen["label"],
                        "view_type": screen["view_type"],
                        "action_count": action_count,
                    }
                )
            group_modules.append(
                {
                    "key": module["key"],
                    "label": module["label"],
                    "summary": module["summary"],
                    "action_count": module_action_count,
                    "screens": module_screens,
                }
            )
        groups.append({"key": group["key"], "label": group["label"], "modules": group_modules})
    return {
        "default_screen": VALIDATED_METADATA["default_screen"],
        "groups": groups,
        "version": VALIDATED_METADATA["version"],
        "registry_key": VALIDATED_METADATA["registry_key"],
    }


def hostify_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(catalog)
    payload["registry_key"] = HOST_DEMO_INFO["registry_key"]
    payload["host"] = {
        "kind": HOST_DEMO_INFO["host_kind"],
        "project": HOST_DEMO_INFO["project_name"],
        "environment": HOST_DEMO_INFO["environment"],
    }
    return payload


def build_screen_spec(screen_key: str) -> dict[str, Any]:
    screen = next((item for item in VALIDATED_METADATA["screens"] if item["key"] == screen_key), None)
    if not screen:
        raise KeyError(screen_key)
    module = next(item for item in VALIDATED_METADATA["modules"] if item["key"] == screen["module_key"])
    actions = [copy.deepcopy(action) for action in VALIDATED_METADATA["actions"] if action["screen_key"] == screen_key]
    enriched_screen = copy.deepcopy(screen)
    enriched_screen.setdefault("status", "online")
    enriched_screen["action_count"] = len(actions)
    return {
        "module": copy.deepcopy(module),
        "screen": enriched_screen,
        "actions": actions,
    }


def hostify_screen_spec(screen_spec: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(screen_spec)
    payload["host"] = {
        "kind": HOST_DEMO_INFO["host_kind"],
        "project": HOST_DEMO_INFO["project_name"],
        "environment": HOST_DEMO_INFO["environment"],
        "user": HOST_DEMO_INFO["user"],
    }
    payload["screen"]["status"] = "online"
    return payload


def paged_rows(rows: list[dict[str, Any]], page: int, page_size: int = 4) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    safe_page = min(max(page, 1), total_pages)
    start = (safe_page - 1) * page_size
    end = start + page_size
    return rows[start:end], {
        "page": safe_page,
        "total_pages": total_pages,
        "total_rows": total_rows,
        "has_previous": safe_page > 1,
        "has_next": safe_page < total_pages,
    }


def response(action_key: str, view_model: dict[str, Any], *, raw: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_runtime_action_result(
        get_action(action_key),
        view_model,
        raw_response=raw
        or {
            "action_key": action_key,
            "generated_at": utc_now(),
        },
    )


def hostify_action_result(result: dict[str, Any], *, api_base: str = "/integration-api/tui") -> dict[str, Any]:
    payload = copy.deepcopy(result)
    payload.setdefault("debug", {})
    raw_response = payload["debug"].get("raw_response") or {}
    if not isinstance(raw_response, dict):
        raw_response = {"value": raw_response}
    raw_response.update(
        {
            "host_project": HOST_DEMO_INFO["project_name"],
            "host_kind": HOST_DEMO_INFO["host_kind"],
            "environment": HOST_DEMO_INFO["environment"],
            "request_user": HOST_DEMO_INFO["user"],
            "metadata_repository": HOST_DEMO_INFO["metadata_repository"],
            "action_executor": HOST_DEMO_INFO["action_executor"],
            "api_base": api_base,
        }
    )
    payload["debug"]["raw_response"] = raw_response
    payload["host"] = {
        "project": HOST_DEMO_INFO["project_name"],
        "environment": HOST_DEMO_INFO["environment"],
        "user": HOST_DEMO_INFO["user"],
    }
    return payload


def message_view(title: str, status: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {"kind": "message", "title": title, "status": status, "sections": sections}


def detail_view(title: str, status: str, fields: list[dict[str, Any]], nested: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {"kind": "detail", "title": title, "status": status, "fields": fields}
    if nested:
        payload["nested"] = nested
    return payload


def datagrid_view(
    title: str,
    status: str,
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    pager: dict[str, Any] | None = None,
    empty_message: str = "暂无可显示数据。",
) -> dict[str, Any]:
    payload = {
        "kind": "datagrid",
        "title": title,
        "status": status,
        "columns": columns,
        "rows": rows,
        "empty_message": empty_message,
    }
    if pager:
        payload["pager"] = pager
    return payload


def account_columns() -> list[dict[str, str]]:
    return [
        {"key": "account_id", "label": "Account ID"},
        {"key": "account_name", "label": "Account"},
        {"key": "risk_level", "label": "Risk"},
        {"key": "nav", "label": "NAV"},
        {"key": "cash_pct", "label": "Cash %"},
        {"key": "status", "label": "Status"},
        {"key": "owner", "label": "Owner"},
    ]


def task_columns() -> list[dict[str, str]]:
    return [
        {"key": "task_id", "label": "Task"},
        {"key": "task_type", "label": "Type"},
        {"key": "status", "label": "Status"},
        {"key": "priority", "label": "Priority"},
        {"key": "owner", "label": "Owner"},
        {"key": "updated_at", "label": "Updated"},
    ]


def filter_accounts(risk_level: str) -> list[dict[str, Any]]:
    if risk_level in {"", "all"}:
        return copy.deepcopy(ACCOUNT_ROWS)
    return [copy.deepcopy(row) for row in ACCOUNT_ROWS if row["risk_level"] == risk_level]


def filter_tasks(status: str) -> list[dict[str, Any]]:
    if status in {"", "all"}:
        return copy.deepcopy(TASK_ROWS)
    return [copy.deepcopy(row) for row in TASK_ROWS if row["status"] == status]


def find_account(account_id: str) -> dict[str, Any]:
    for row in ACCOUNT_ROWS:
        if row["account_id"] == account_id:
            return copy.deepcopy(row)
    raise KeyError(account_id)


def find_task(task_id: str) -> dict[str, Any]:
    for row in TASK_ROWS:
        if row["task_id"] == task_id:
            return copy.deepcopy(row)
    raise KeyError(task_id)


def handle_action(
    action_key: str,
    params: dict[str, Any],
    confirmed: bool,
    confirmation_evidence: dict[str, Any] | None = None,
    reauth_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = get_action(action_key)
    if confirmed and not confirmation_evidence:
        confirmation_evidence = {"confirmed": True, "confirmed_at": utc_now()}
    return GovernedActionRunner(DemoActionExecutor(), DemoAuditSink(), reauth_verifier=verify_demo_reauth).execute(
        action,
        params,
        context={"action_key": action_key},
        actor=HOST_DEMO_INFO["user"],
        confirmed=confirmed,
        confirmation_evidence=confirmation_evidence,
        reauth_evidence=reauth_evidence,
    )


def execute_action_logic(action_key: str, params: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    page = int(params.get("page") or 1)
    if action_key == "command-center.regime-status":
        return response(
            action_key,
            detail_view(
                "Macro Regime",
                "正常 / 已发布",
                [
                    {"key": "current_regime", "label": "Current Regime", "value": REGIME_SNAPSHOT["current_regime"]},
                    {"key": "confidence", "label": "Confidence", "value": REGIME_SNAPSHOT["confidence"]},
                    {"key": "trend", "label": "Trend", "value": REGIME_SNAPSHOT["trend"]},
                    {"key": "warning", "label": "Warning", "value": REGIME_SNAPSHOT["warning"]},
                ],
            ),
            raw={"source": "/api/demo/regime/current/", "snapshot": REGIME_SNAPSHOT, "generated_at": utc_now()},
        )
    if action_key == "command-center.account-positions":
        rows = copy.deepcopy(ACCOUNT_ROWS[:4])
        return response(
            action_key,
            datagrid_view("Account Pressure", "观察 / 首页摘录", account_columns(), rows),
            raw={"source": "/api/demo/accounts/", "panel": "account-positions", "generated_at": utc_now()},
        )
    if action_key == "command-center.task-monitor":
        rows = copy.deepcopy(TASK_ROWS[:4])
        return response(
            action_key,
            datagrid_view("Task Queue", "运行 / 首页摘录", task_columns(), rows),
            raw={"source": "/api/demo/tasks/", "panel": "task-monitor", "generated_at": utc_now()},
        )
    if action_key == "command-center.nav-trend":
        points = [{"label": row["date"], "value": row["nav"]} for row in RICH_NAV_HISTORY]
        return response(
            action_key,
            {
                "kind": "chart",
                "renderer": "line",
                "chart_type": "line",
                "title": "NAV Trend",
                "status": "正常 / Metadata Renderer",
                "series": [{"name": "NAV", "points": points}],
                "empty_message": "No NAV history available.",
            },
            raw={"source": "/api/demo/rich/nav-trend/", "data": {"history": copy.deepcopy(RICH_NAV_HISTORY)}, "generated_at": utc_now()},
        )
    if action_key == "command-center.allocation-table-chart":
        rows = copy.deepcopy(RICH_ALLOCATION_ROWS)
        columns = [
            {"key": "asset", "label": "Asset"},
            {"key": "weight", "label": "Weight %"},
            {"key": "target", "label": "Target %"},
            {"key": "status", "label": "Status"},
        ]
        points = [{"label": row["asset"], "value": row["weight"]} for row in rows]
        return response(
            action_key,
            {
                "kind": "table_chart",
                "title": "Allocation Table + Chart",
                "status": "正常 / Metadata Renderer",
                "chart": {
                    "kind": "chart",
                    "renderer": "bar",
                    "chart_type": "bar",
                    "title": "Allocation Weight",
                    "series": [{"name": "Weight", "points": points}],
                    "empty_message": "No allocation data available.",
                },
                "table": datagrid_view("Allocation Rows", "正常 / 同源表格", columns, rows),
                "empty_message": "No allocation data available.",
            },
            raw={"source": "/api/demo/rich/allocation/", "data": {"rows": rows}, "generated_at": utc_now()},
        )
    if action_key == "command-center.host-partial":
        partial_html = (
            '<div class="tui-host-partial-demo">'
            "<strong>Controlled host partial</strong>"
            "<span>This HTML is only inserted when allowHostHtmlSlots is enabled by the host.</span>"
            "</div>"
        )
        return response(
            action_key,
            {
                "kind": "host_slot",
                "renderer": "host-slot",
                "title": "Host Partial Slot",
                "status": "安全 / 默认禁用 HTML 插入",
                "slot_key": "rich-components-demo",
                "partial_html": partial_html,
                "fallback_message": "Host partial rendering is disabled until the host enables HTML slots.",
            },
            raw={"source": "/api/demo/rich/host-partial/", "data": {"partial_html": partial_html}, "generated_at": utc_now()},
        )
    if action_key in {"execution.accounts.list", "param.execution.accounts.filter-risk"}:
        risk_level = str(params.get("risk_level") or ("high" if action_key.startswith("param.") else "all"))
        rows, pager = paged_rows(filter_accounts(risk_level), page)
        title = "Account Grid" if risk_level == "all" else f"Account Grid / Risk = {risk_level}"
        return response(
            action_key,
            datagrid_view(title, "正常 / 账户快照", account_columns(), rows, pager=pager),
            raw={
                "source": "/api/demo/accounts/",
                "params": {"risk_level": risk_level, "page": page},
                "generated_at": utc_now(),
            },
        )
    if action_key == "execution.accounts.detail":
        account = find_account(str(params.get("account_id") or ACCOUNT_ROWS[0]["account_id"]))
        return response(
            action_key,
            detail_view(
                f"Account {account['account_id']}",
                "正常 / 详情",
                [
                    {"key": "account_id", "label": "Account ID", "value": account["account_id"]},
                    {"key": "account_name", "label": "Account", "value": account["account_name"]},
                    {"key": "risk_level", "label": "Risk", "value": account["risk_level"]},
                    {"key": "nav", "label": "NAV", "value": account["nav"]},
                    {"key": "cash_pct", "label": "Cash %", "value": account["cash_pct"]},
                    {"key": "owner", "label": "Owner", "value": account["owner"]},
                    {"key": "updated_at", "label": "Updated", "value": account["updated_at"]},
                ],
                nested=[
                    {"label": "Trade tickets", "count": 3},
                    {"label": "Risk alerts", "count": 1},
                ],
            ),
            raw={"source": f"/api/demo/accounts/{account['account_id']}/", "record": account, "generated_at": utc_now()},
        )
    if action_key == "execution.accounts.rebalance":
        action = get_action(action_key)
        resolved_params = apply_default_field_values(action, params)
        missing = missing_required_fields(action, resolved_params)
        if missing:
            return build_missing_fields_result(action, missing)
        payload = {
            "account_id": str(resolved_params.get("account_id") or ""),
            "target_weight": str(resolved_params.get("target_weight") or ""),
            "note": str(resolved_params.get("note") or ""),
        }
        preview = message_view(
            "Rebalance Preview",
            "等待确认",
            [
                {
                    "title": "Pending Request",
                    "body": [
                        "This mock adapter is exercising the confirmed write path.",
                        "In a real host, permission checks and audit storage happen after the runtime action-runner call.",
                    ],
                    "rows": [
                        {"label": "Account", "value": payload["account_id"] or "未提供"},
                        {"label": "Target Weight", "value": f"{payload['target_weight']}%"},
                    ],
                }
            ],
        )
        if not confirmed:
            return build_confirmation_required_result(
                action,
                title="Confirm Rebalance",
                message=f"Submit rebalance request for {payload['account_id'] or 'this account'} to {payload['target_weight'] or '?'}%?",
                confirm_label="Submit Request",
                cancel_label="Cancel",
                view_model=preview,
            )
        return response(
            action_key,
            message_view(
                "Rebalance Submitted",
                "成功 / 已确认",
                [
                    {
                        "title": "Dispatch Result",
                        "body": [
                            "Request moved through the same runtime action contract as read-only views.",
                            "This standalone demo stops at the adapter boundary instead of touching a real order service.",
                        ],
                        "rows": [
                            {"label": "Account", "value": payload["account_id"]},
                            {"label": "Target Weight", "value": f"{payload['target_weight']}%"},
                            {"label": "Request ID", "value": "REQ-ACCT-9201"},
                        ],
                    }
                ],
            ),
            raw={"source": "/api/demo/accounts/rebalance/", "payload": payload, "confirmed": True, "generated_at": utc_now()},
        )
    if action_key == "execution.tasks.queue":
        status_filter = str(params.get("status") or "all")
        rows, pager = paged_rows(filter_tasks(status_filter), page)
        title = "Task Queue" if status_filter == "all" else f"Task Queue / Status = {status_filter}"
        return response(
            action_key,
            datagrid_view(title, "运行 / 队列工位", task_columns(), rows, pager=pager),
            raw={"source": "/api/demo/tasks/", "params": {"status": status_filter, "page": page}, "generated_at": utc_now()},
        )
    if action_key == "execution.tasks.detail":
        task = find_task(str(params.get("task_id") or TASK_ROWS[0]["task_id"]))
        return response(
            action_key,
            detail_view(
                f"Task {task['task_id']}",
                "正常 / 队列详情",
                [
                    {"key": "task_id", "label": "Task ID", "value": task["task_id"]},
                    {"key": "task_type", "label": "Type", "value": task["task_type"]},
                    {"key": "status", "label": "Status", "value": task["status"]},
                    {"key": "priority", "label": "Priority", "value": task["priority"]},
                    {"key": "owner", "label": "Owner", "value": task["owner"]},
                    {"key": "updated_at", "label": "Updated", "value": task["updated_at"]},
                ],
                nested=[
                    {"label": "Blocking checks", "count": 2},
                    {"label": "Downstream jobs", "count": 1},
                ],
            ),
            raw={"source": f"/api/demo/tasks/{task['task_id']}/", "record": task, "generated_at": utc_now()},
        )
    if action_key == "execution.tasks.retry":
        action = get_action(action_key)
        resolved_params = apply_default_field_values(action, params)
        missing = missing_required_fields(action, resolved_params)
        if missing:
            return build_missing_fields_result(action, missing)
        payload = {
            "task_id": str(resolved_params.get("task_id") or ""),
            "reason": str(resolved_params.get("reason") or ""),
        }
        preview = message_view(
            "Retry Preview",
            "等待确认",
            [
                {
                    "title": "Pending Retry",
                    "body": ["This path exists to prove that the runtime can govern a write action through adapter confirmation."],
                    "rows": [
                        {"label": "Task", "value": payload["task_id"] or "未提供"},
                        {"label": "Reason", "value": payload["reason"] or "No extra note"},
                    ],
                }
            ],
        )
        if not confirmed:
            return build_confirmation_required_result(
                action,
                title="Confirm Retry",
                message=f"Retry blocked task {payload['task_id'] or '?'}?",
                confirm_label="Retry Task",
                cancel_label="Keep Blocked",
                view_model=preview,
            )
        return response(
            action_key,
            message_view(
                "Retry Accepted",
                "成功 / 已重新排队",
                [
                    {
                        "title": "Queue Update",
                        "body": [
                            "Task moved back into the runnable queue.",
                            "Real hosts would now enqueue a job or call an orchestration service.",
                        ],
                        "rows": [
                            {"label": "Task", "value": payload["task_id"]},
                            {"label": "New Status", "value": "queued"},
                        ],
                    }
                ],
            ),
            raw={"source": "/api/demo/tasks/retry/", "payload": payload, "confirmed": True, "generated_at": utc_now()},
        )
    if action_key == "execution.tasks.ai-brief":
        task = find_task(str(params.get("task_id") or TASK_ROWS[0]["task_id"]))
        return response(
            action_key,
            message_view(
                "AI Operator Brief",
                "已生成 / 模拟结果",
                [
                    {
                        "title": "What changed",
                        "body": [
                            f"{task['task_id']} is {task['status']} because an upstream dependency did not publish on time.",
                            "The standalone demo uses a mocked brief here; the compiler page shows where a real model boundary would sit.",
                        ],
                        "rows": [
                            {"label": "Task", "value": task["task_id"]},
                            {"label": "Owner", "value": task["owner"]},
                        ],
                    },
                    {
                        "title": "Recommended next move",
                        "body": [
                            "Inspect the blocked dependency, retry once after input freshness is restored, and avoid duplicate manual intervention.",
                        ],
                        "rows": [],
                    },
                ],
            ),
            raw={"source": "/api/demo/tasks/ai-brief/", "task": task, "generated_at": utc_now()},
        )
    if action_key == "macro-regime.snapshot":
        return response(
            action_key,
            detail_view(
                "Regime Explanation",
                "正常 / 研究快照",
                [
                    {"key": "current_regime", "label": "Current Regime", "value": REGIME_SNAPSHOT["current_regime"]},
                    {"key": "confidence", "label": "Confidence", "value": REGIME_SNAPSHOT["confidence"]},
                    {"key": "trend", "label": "Trend", "value": REGIME_SNAPSHOT["trend"]},
                    {"key": "warning", "label": "Watchpoint", "value": REGIME_SNAPSHOT["warning"]},
                    {"key": "updated_at", "label": "Updated", "value": REGIME_SNAPSHOT["updated_at"]},
                ],
                nested=[
                    {"label": "Signals used", "count": 4},
                    {"label": "Open watchpoints", "count": 2},
                ],
            ),
            raw={"source": "/api/demo/regime/current/", "snapshot": REGIME_SNAPSHOT, "generated_at": utc_now()},
        )
    if action_key == "macro-regime.watchpoints":
        return response(
            action_key,
            message_view(
                "Regime Watchpoints",
                "观察 / 说明",
                [
                    {
                        "title": "Current posture",
                        "body": [
                            "Recovery remains the dominant regime, but rate-sensitive sleeves are still reacting unevenly.",
                            "Use the execution workspaces to validate whether individual queues or accounts need intervention.",
                        ],
                        "rows": [
                            {"label": "Regime", "value": REGIME_SNAPSHOT["current_regime"]},
                            {"label": "Confidence", "value": REGIME_SNAPSHOT["confidence"]},
                        ],
                    }
                ],
            ),
            raw={"source": "/api/demo/regime/current/", "snapshot": REGIME_SNAPSHOT, "generated_at": utc_now()},
        )
    raise KeyError(action_key)


def esc(value: Any) -> str:
    return html.escape(str(value))


def json_html(payload: Any) -> str:
    return f"<pre>{esc(json.dumps(payload, ensure_ascii=False, indent=2))}</pre>"


def layout(title: str, body: str, *, active: str) -> bytes:
    nav_items = [
        ("overview", "/", "Product"),
        ("standalone", "/standalone/", "Standalone"),
        ("compiler", "/compiler/", "Compiler"),
        ("integration", "/integration/", "Host Demo"),
        ("migration", "/migration/", "Migration"),
    ]
    nav = "".join(
        f'<a href="{href}" class="{"is-active" if key == active else ""}">{label}</a>'
        for key, href, label in nav_items
    )
    html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07111a;
      --bg-strong: #0d1824;
      --panel: #132434;
      --panel-alt: #1a3044;
      --text: #e9f1f7;
      --muted: #9ab0bf;
      --accent: #78e7c8;
      --accent-strong: #f3ba4f;
      --danger: #f57575;
      --border: #274157;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(120, 231, 200, 0.08), transparent 30%),
        radial-gradient(circle at left center, rgba(243, 186, 79, 0.07), transparent 25%),
        var(--bg);
      color: var(--text);
    }}
    a {{ color: inherit; text-decoration: none; }}
    code, pre {{
      font-family: "IBM Plex Mono", "Cascadia Code", Consolas, monospace;
    }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 1px solid var(--border);
      background: rgba(7, 17, 26, 0.92);
      backdrop-filter: blur(12px);
    }}
    .topbar-inner {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }}
    .brand {{
      display: grid;
      gap: 4px;
    }}
    .brand strong {{
      font-size: 1.15rem;
      font-weight: 700;
    }}
    .brand span {{
      color: var(--muted);
      font-size: 0.92rem;
    }}
    nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    nav a {{
      padding: 8px 12px;
      border: 1px solid var(--border);
      background: rgba(19, 36, 52, 0.7);
      color: var(--muted);
    }}
    nav a.is-active {{
      color: var(--text);
      border-color: var(--accent);
      background: rgba(120, 231, 200, 0.12);
    }}
    main {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 28px 24px 56px;
      display: grid;
      gap: 24px;
    }}
    .hero {{
      display: grid;
      gap: 16px;
      padding: 24px;
      border: 1px solid var(--border);
      background: linear-gradient(135deg, rgba(19, 36, 52, 0.96), rgba(12, 22, 32, 0.96));
    }}
    .hero h1, .hero h2 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 1.05;
    }}
    .hero p {{
      margin: 0;
      max-width: 72ch;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.65;
    }}
    .hero-actions, .inline-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border: 1px solid var(--accent);
      background: rgba(120, 231, 200, 0.12);
      color: var(--text);
      font-weight: 600;
    }}
    .button.alt {{
      border-color: var(--border);
      background: rgba(19, 36, 52, 0.7);
      color: var(--muted);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .metric, .panel {{
      border: 1px solid var(--border);
      background: rgba(19, 36, 52, 0.82);
      padding: 18px;
    }}
    .metric strong {{
      display: block;
      font-size: 1.8rem;
      color: var(--accent);
    }}
    .metric span {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
    }}
    .panel h2, .panel h3 {{
      margin: 0 0 10px;
      font-size: 1.05rem;
    }}
    .panel p, .panel li {{
      color: var(--muted);
      line-height: 1.65;
    }}
    .panel ul, .panel ol {{
      margin: 12px 0 0;
      padding-left: 20px;
    }}
    .panel pre {{
      margin: 0;
      overflow: auto;
      padding: 14px;
      background: rgba(7, 17, 26, 0.82);
      border: 1px solid rgba(39, 65, 87, 0.9);
      color: #dce9f3;
      font-size: 0.9rem;
      line-height: 1.45;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 18px;
    }}
    .section-title {{
      margin: 0 0 8px;
      font-size: 1.35rem;
    }}
    .eyebrow {{
      color: var(--accent-strong);
      text-transform: uppercase;
      font-size: 0.82rem;
      letter-spacing: 0.08em;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--accent);
      font-weight: 600;
    }}
    .status::before {{
      content: "";
      width: 8px;
      height: 8px;
      background: var(--accent);
      border-radius: 999px;
      box-shadow: 0 0 12px rgba(120, 231, 200, 0.7);
    }}
    @media (max-width: 760px) {{
      .topbar-inner {{
        align-items: start;
        flex-direction: column;
      }}
      main {{
        padding: 18px 16px 36px;
      }}
      .hero {{
        padding: 18px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-inner">
        <a class="brand" href="/">
          <strong>AgomTUI Standalone Demo</strong>
          <span>Runtime shell, compiler walkthrough, host integration, migration path</span>
        </a>
        <nav>{nav}</nav>
      </div>
    </header>
    <main>{body}</main>
  </div>
</body>
</html>"""
    return html_text.encode("utf-8")


def render_runtime_html(
    *,
    title: str,
    home_href: str,
    brand_label: str,
    api_base: str,
    asset_base: str = "/standalone/static",
) -> bytes:
    return render_embeddable_runtime_html(
        title=title,
        home_href=home_href,
        brand_label=brand_label,
        api_base=api_base,
        asset_base=asset_base,
    )


def runtime_asset_payload(relative: str) -> tuple[bytes, str]:
    asset = runtime_asset(relative)
    return asset.body, asset.content_type


def local_url(port: int, path: str = "/") -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"http://{HOST}:{port}{normalized}"


def overview_page() -> bytes:
    metrics = f"""
    <section class="metrics">
      <div class="metric"><strong>{len(VALIDATED_METADATA['screens'])}</strong><span>runtime screens in the demo metadata graph</span></div>
      <div class="metric"><strong>{len(VALIDATED_METADATA['actions'])}</strong><span>actions routed through the same adapter contract</span></div>
      <div class="metric"><strong>{sum(COMPILER_DEMO['skill_request']['source_counts'].values())}</strong><span>code-owned evidence items in the compiler walkthrough</span></div>
      <div class="metric"><strong>4</strong><span>tour stops: standalone, compiler, integration, migration</span></div>
    </section>
    """
    cards = """
    <section class="grid">
      <a class="panel" href="/standalone/">
        <h2>Standalone Runtime</h2>
        <p>Open the extracted TUI shell with a mock `/api/tui/*` adapter so the workbench runs without the original business system.</p>
      </a>
      <a class="panel" href="/compiler/">
        <h2>Compiler Walkthrough</h2>
        <p>Inspect the OpenAPI and Django contract inputs, the generated skill request payload, and the compiled metadata artifacts.</p>
      </a>
      <a class="panel" href="/integration/">
        <h2>Host Integration</h2>
        <p>Open a host-project shell and launch the same runtime again through a separate `/integration-api/tui/*` adapter surface.</p>
      </a>
      <a class="panel" href="/migration/">
        <h2>Migration Path</h2>
        <p>Read the concrete extraction sequence for moving from the demo into a real standalone product and back into a host project.</p>
      </a>
    </section>
    """
    body = f"""
    <section class="hero">
      <div class="eyebrow">Product Surface</div>
      <h1>One repo, four visible proof points.</h1>
      <p>This demo turns the extracted AgomTUI pieces into something you can open immediately: a runtime workbench that no longer depends on the original business app, a compiler walkthrough driven by OpenAPI and Django contracts, a host integration demo, and a migration checklist for real adoption.</p>
      <div class="hero-actions">
        <a class="button" href="/standalone/">Open Standalone Demo</a>
        <a class="button alt" href="/compiler/">Inspect Compiler Output</a>
      </div>
      <div class="status">Local server ready on http://{HOST}:{PORT}/</div>
    </section>
    {metrics}
    {cards}
    <section class="two-col">
      <div class="panel">
        <h2 class="section-title">What this proves</h2>
        <ul>
          <li>The extracted runtime can boot from published metadata and an adapter contract instead of the original business application.</li>
          <li>The compiler boundary is explicit: source evidence in, metadata candidate out, deterministic validation after generation.</li>
          <li>The same shell and metadata graph can be mounted again under a host-project route with a different API base and home navigation.</li>
        </ul>
      </div>
      <div class="panel">
        <h2 class="section-title">Run from the repo</h2>
        {json_html({"command": "python demo\\\\standalone_server.py", "url": f"http://{HOST}:{PORT}/", "standalone_entry": f"http://{HOST}:{PORT}/standalone/", "integration_entry": f"http://{HOST}:{PORT}/integration/", "integration_runtime_entry": f"http://{HOST}:{PORT}/integration-tui/"})}
      </div>
    </section>
    """
    return layout("AgomTUI Standalone Demo", body, active="overview")


def compiler_page() -> bytes:
    skill_request = COMPILER_DEMO["skill_request"]
    compile_static = COMPILER_DEMO["compile_static"]
    compile_skill = COMPILER_DEMO["compile_skill_result"]
    body = f"""
    <section class="hero">
      <div class="eyebrow">Compiler Surface</div>
      <h1>Code-owned evidence in, reviewed metadata artifact out.</h1>
      <p>This page uses the same compiler packages in the repository. It loads the demo OpenAPI and Django contract fixture, builds the skill request payload, then validates and compacts both a curated candidate and a skill-style result.</p>
      <div class="inline-actions">
        <a class="button" href="/standalone/">See the runtime consume the published graph</a>
        <a class="button alt" href="/integration/">Inspect the host integration demo</a>
      </div>
    </section>
    <section class="two-col">
      <div class="panel">
        <h2>OpenAPI Input</h2>
        <p>The compiler reads host-owned endpoint evidence, including path parameters, request bodies, and response contracts.</p>
        {json_html(COMPILER_DEMO["inputs"]["openapi"])}
      </div>
      <div class="panel">
        <h2>Django Contract Input</h2>
        <p>The compiler also reads machine-generated model and aggregate contracts instead of product prose.</p>
        {json_html(COMPILER_DEMO["inputs"]["django_contract_manifest"])}
      </div>
    </section>
    <section class="two-col">
      <div class="panel">
        <h2>Skill Request Payload</h2>
        <p>This is the envelope an external AI skill or model runner would receive.</p>
        {json_html(skill_request)}
      </div>
      <div class="panel">
        <h2>Compile Static Result</h2>
        <p>The current skeleton already validates and compacts a curated candidate without a live LLM backend.</p>
        {json_html({"source_counts": compile_static["source_counts"], "compacted_payload": compile_static["compacted_payload"], "evidence_payload": compile_static["evidence_payload"]})}
      </div>
    </section>
    <section class="panel">
      <h2>Compile Skill Result</h2>
      <p>This route simulates the later product boundary where an external skill returns one JSON object containing <code>candidate_payload</code>, <code>model_name</code>, and an optional <code>reasoning_note</code>.</p>
      {json_html({"source_counts": compile_skill["source_counts"], "compacted_payload": compile_skill["compacted_payload"], "evidence_payload": compile_skill["evidence_payload"]})}
    </section>
    """
    return layout("Compiler Walkthrough", body, active="compiler")


def host_page() -> bytes:
    registry_state = {
        "project": HOST_DEMO_INFO["project_name"],
        "environment": HOST_DEMO_INFO["environment"],
        "metadata_registry_key": HOST_DEMO_INFO["registry_key"],
        "runtime_entry": HOST_DEMO_INFO["runtime_entry"],
        "catalog_endpoint": HOST_DEMO_INFO["catalog_endpoint"],
        "export_endpoints": [
            HOST_DEMO_INFO["openapi_export"],
            HOST_DEMO_INFO["django_contract_export"],
            HOST_DEMO_INFO["published_metadata_export"],
        ],
    }
    body = f"""
    <section class="hero">
      <div class="eyebrow">Host Project</div>
      <h1>{HOST_DEMO_INFO["project_name"]}</h1>
      <p>This page acts like the containing Django project. It owns the user session, published metadata registry, evidence export endpoints, and the host-mounted TUI route. The runtime itself is still the same extracted shell.</p>
      <div class="hero-actions">
        <a class="button" href="{HOST_DEMO_INFO["runtime_entry"]}">Open Host-Mounted TUI</a>
        <a class="button alt" href="/integration/">Inspect Adapter Contract</a>
      </div>
      <div class="status">{HOST_DEMO_INFO["host_kind"]} host shell / {HOST_DEMO_INFO["environment"]} / user {HOST_DEMO_INFO["user"]}</div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Host-owned responsibilities</h2>
        <ul>
          <li>Serve authenticated pages and map the runtime into a host route such as <code>/integration-tui/</code>.</li>
          <li>Load one approved published metadata artifact through the metadata repository adapter.</li>
          <li>Execute internal business actions with user context and return view models back to the runtime.</li>
          <li>Export OpenAPI and Django contracts so the compiler can regenerate metadata safely.</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Registry state</h2>
        {json_html(registry_state)}
      </div>
    </section>
    """
    return layout("AgomTradePro Host Demo", body, active="integration")


def integration_page() -> bytes:
    screen_spec = hostify_screen_spec(build_screen_spec("execution.accounts"))
    sample_action_result = hostify_action_result(handle_action("execution.accounts.list", {"page": 1}, confirmed=False))
    body = f"""
    <section class="hero">
      <div class="eyebrow">Host Integration</div>
      <h1>Mount the same runtime twice: once standalone, once under a host project shell.</h1>
      <p>The extracted shell already assumes a host-facing adapter API. This repo now demonstrates that explicitly in two ways: the in-process integration mode uses <code>/integration-api/tui/*</code>, and the real Django host demo uses the same contract on a separate process and port.</p>
      <div class="inline-actions">
        <a class="button" href="/standalone/?mode=integration">Open Host-Mounted Runtime</a>
        <a class="button alt" href="{local_url(DJANGO_PORT)}">Open Real Django Host</a>
        <a class="button alt" href="/migration/">Open Migration Checklist</a>
      </div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Host-mounted runtime endpoints</h2>
        <ul>
          <li><code>GET /integration-api/tui/catalog/</code>: return group, module, and screen navigation plus <code>default_screen</code>.</li>
          <li><code>GET /integration-api/tui/screens/&lt;screen_key&gt;/</code>: return one module, one screen, and the actions available on that screen.</li>
          <li><code>POST /integration-api/tui/actions/&lt;action_key&gt;/run/</code>: run one host action and return a renderable <code>view_model</code>.</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Django-style adapter responsibilities</h2>
        <ul>
          <li>Metadata repository: load one validated published metadata artifact for the runtime.</li>
          <li>Action executor: call internal endpoints or services with user context and return serializable view models.</li>
          <li>Contract exporter: emit OpenAPI JSON and Django aggregate manifests for the compiler.</li>
          <li>Host wiring: auth, permission checks, audit storage, and template/static mounting stay inside the host.</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Real Django host demo</h2>
        <ul>
          <li><code>{local_url(DJANGO_PORT, "/")}</code>: Django host home page</li>
          <li><code>{local_url(DJANGO_PORT, "/tui/")}</code>: same runtime mounted by Django</li>
          <li><code>{local_url(DJANGO_PORT, "/api/tui/catalog/")}</code>: Django-backed catalog endpoint</li>
        </ul>
      </div>
    </section>
    <section class="two-col">
      <div class="panel">
        <h2>Host screen payload</h2>
        <p>The host route returns this shape from <code>/integration-api/tui/screens/execution.accounts/</code>. The runtime consumes it exactly the same way as the standalone variant.</p>
        {json_html(screen_spec)}
      </div>
      <div class="panel">
        <h2>Host action result</h2>
        <p>This is a representative result from <code>/integration-api/tui/actions/execution.accounts.list/run/</code>. The extra host debug fields show where a Django adapter would inject request user, environment, repository, and executor context.</p>
        {json_html(sample_action_result)}
      </div>
    </section>
    """
    return layout("Host Integration Demo", body, active="integration")


def migration_page() -> bytes:
    body = """
    <section class="hero">
      <div class="eyebrow">Migration Path</div>
      <h1>Move from reference extraction to productized adapters.</h1>
      <p>The goal is not to clone a Django template split. The durable product boundary is schema-first metadata, a compile-time promotion pipeline, and a runtime shell served through host adapters.</p>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Phase 1</h2>
        <ul>
          <li>Keep `agomtui-core` framework-free: schema, validator, compactor, contracts.</li>
          <li>Keep `agomtui-runtime` as a host-agnostic shell asset package.</li>
          <li>Expose compile-time evidence with OpenAPI and Django contract exports.</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Phase 2</h2>
        <ul>
          <li>Replace static candidate loading with a real external LLM or skill backend.</li>
          <li>Move host-specific auth, permission, and audit logic into adapters.</li>
          <li>Remove business vocabulary from the product core unless it sits behind an adapter or vocabulary pack.</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Phase 3</h2>
        <ul>
          <li>Add package-level tests and CI around compiler, runtime contract, and adapters.</li>
          <li>Ship one official Django adapter with metadata repository, action executor, and export commands.</li>
          <li>Decide whether published metadata lives in files, a registry table, or a hosted service.</li>
        </ul>
      </div>
    </section>
    <section class="two-col">
      <div class="panel">
        <h2>Host checklist</h2>
        <ol>
          <li>Export OpenAPI JSON and one Django contract manifest from the host codebase.</li>
          <li>Run the compiler skill-request flow and obtain one candidate payload.</li>
          <li>Validate, compact, and publish the approved artifact.</li>
          <li>Implement `/api/tui/catalog/`, `/api/tui/screens/{key}/`, and `/api/tui/actions/{key}/run/` in the host.</li>
          <li>Mount the runtime shell and point it at the published artifact and action runner.</li>
        </ol>
      </div>
      <div class="panel">
        <h2>Repository docs to read next</h2>
        <ul>
          <li><code>README.md</code>: product boundary and package split.</li>
          <li><code>docs/README.md</code>: development documentation map.</li>
          <li><code>docs/architecture/compiler-architecture.md</code>: collectors, synthesizer, validation, publisher.</li>
          <li><code>docs/migration/migration-plan.md</code>: extraction phases.</li>
          <li><code>adapters/django/README.md</code>: first adapter scope.</li>
        </ul>
      </div>
    </section>
    """
    return layout("Migration Checklist", body, active="migration")


class DemoRequestHandler(BaseHTTPRequestHandler):
    server_version = "AgomTuiStandaloneDemo/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.respond_html(overview_page())
            return
        if path == "/standalone/":
            mode = (parse_qs(parsed.query).get("mode") or ["standalone"])[0]
            if mode == "integration":
                self.respond_html(
                    render_runtime_html(
                        title="AgomTUI Host Workbench",
                        home_href="/integration/",
                        brand_label="AgomTUI Host",
                        api_base="/integration-api/tui",
                    )
                )
            else:
                self.respond_html(
                    render_runtime_html(
                        title="AgomTUI Standalone Workbench",
                        home_href="/",
                        brand_label="AgomTUI",
                        api_base="/api/tui",
                    )
                )
            return
        if path == "/compiler/":
            self.respond_html(compiler_page())
            return
        if path == "/integration/":
            self.respond_html(integration_page())
            return
        if path == "/integration-tui/":
            self.respond_html(
                render_runtime_html(
                    title="AgomTUI Host Workbench",
                    home_href="/integration/",
                    brand_label="AgomTUI Host",
                    api_base="/integration-api/tui",
                )
            )
            return
        if path == "/migration/":
            self.respond_html(migration_page())
            return
        if path == "/healthz":
            self.respond_json({"ok": True, "timestamp": utc_now()})
            return
        if path == "/api/tui/catalog/":
            self.respond_json(build_catalog())
            return
        if path == "/integration-api/tui/catalog/":
            self.respond_json(hostify_catalog(build_catalog()))
            return
        match = re.fullmatch(r"/api/tui/screens/(?P<screen_key>[^/]+)/", path)
        if match:
            screen_key = match.group("screen_key")
            try:
                self.respond_json(build_screen_spec(screen_key))
            except KeyError:
                self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown screen: {screen_key}")
            return
        match = re.fullmatch(r"/integration-api/tui/screens/(?P<screen_key>[^/]+)/", path)
        if match:
            screen_key = match.group("screen_key")
            try:
                self.respond_json(hostify_screen_spec(build_screen_spec(screen_key)))
            except KeyError:
                self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown screen: {screen_key}")
            return
        if path == HOST_DEMO_INFO["openapi_export"]:
            self.respond_json(OPENAPI_FIXTURE)
            return
        if path == HOST_DEMO_INFO["django_contract_export"]:
            self.respond_json(DJANGO_CONTRACT_FIXTURE)
            return
        if path == HOST_DEMO_INFO["published_metadata_export"]:
            self.respond_json(VALIDATED_METADATA)
            return
        if path.startswith("/api/demo/compiler/"):
            self.respond_compiler_api(path)
            return
        if path.startswith("/standalone/static/"):
            self.respond_runtime_asset(path)
            return
        self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown route: {path}")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        host_mode = False
        match = re.fullmatch(r"/api/tui/actions/(?P<action_key>[^/]+)/run/", parsed.path)
        if not match:
            match = re.fullmatch(r"/integration-api/tui/actions/(?P<action_key>[^/]+)/run/", parsed.path)
            host_mode = bool(match)
        if not match:
            self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown route: {parsed.path}")
            return
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.respond_error_json(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
            return
        params = body.get("params") or {}
        confirmed = bool(body.get("confirmed"))
        confirmation_evidence = body.get("confirmation") if isinstance(body.get("confirmation"), dict) else None
        reauth_evidence = body.get("reauth") if isinstance(body.get("reauth"), dict) else None
        try:
            result = handle_action(match.group("action_key"), params, confirmed, confirmation_evidence, reauth_evidence)
        except KeyError as error:
            self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown action: {error.args[0]}")
            return
        if host_mode:
            result = hostify_action_result(result)
        self.respond_json(result)

    def respond_compiler_api(self, path: str) -> None:
        mapping = {
            "/api/demo/compiler/openapi/": COMPILER_DEMO["inputs"]["openapi"],
            "/api/demo/compiler/django-contract/": COMPILER_DEMO["inputs"]["django_contract_manifest"],
            "/api/demo/compiler/skill-request/": COMPILER_DEMO["skill_request"],
            "/api/demo/compiler/compile-static/": COMPILER_DEMO["compile_static"],
            "/api/demo/compiler/compile-skill-result/": COMPILER_DEMO["compile_skill_result"],
        }
        payload = mapping.get(path)
        if payload is None:
            self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown compiler route: {path}")
            return
        self.respond_json(payload)

    def respond_runtime_asset(self, path: str) -> None:
        relative = path.removeprefix("/standalone/static/")
        try:
            body, mime = runtime_asset_payload(relative)
        except FileNotFoundError:
            self.respond_error_json(HTTPStatus.NOT_FOUND, f"Unknown asset: {path}")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, body: bytes) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_error_json(self, status: HTTPStatus, message: str) -> None:
        self.respond_json({"ok": False, "error": message}, status=status)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        sys.stderr.write(f"[{timestamp}] {self.address_string()} {format % args}\n")


def create_demo_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, PORT), DemoRequestHandler)


def main() -> None:
    server = create_demo_server()
    print(f"AgomTUI standalone demo running on http://{HOST}:{PORT}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
