from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

from agomtui_core import validate_tui_metadata

UsabilitySeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class UsabilityIssue:
    severity: UsabilitySeverity
    code: str
    message: str
    path: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


@dataclass(frozen=True)
class UsabilityCheckResult:
    ok: bool
    error_count: int
    warning_count: int
    issues: tuple[UsabilityIssue, ...]
    summary: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "summary": self.summary,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def check_tui_metadata_usability(payload: dict[str, Any]) -> UsabilityCheckResult:
    """Run automated usability checks against one validated metadata graph.

    Schema validation answers "is this safe to load?". These rules answer
    whether the published graph has enough navigation, action, and renderer
    affordances for an operator to use without guessing.
    """

    metadata = validate_tui_metadata(payload)
    issues: list[UsabilityIssue] = []

    screens = list(_dict_items(metadata.get("screens")))
    actions = list(_dict_items(metadata.get("actions")))
    actions_by_key = {str(action["key"]): action for action in actions}
    actions_by_screen = _group_actions_by_screen(actions)

    for index, screen in enumerate(screens):
        _check_screen(
            screen=screen,
            screen_index=index,
            actions_by_key=actions_by_key,
            actions_on_screen=actions_by_screen.get(str(screen["key"]), []),
            issues=issues,
        )

    for index, action in enumerate(actions):
        _check_action(action=action, action_index=index, issues=issues)

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    return UsabilityCheckResult(
        ok=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        issues=tuple(issues),
        summary={
            "groups": len(list(_dict_items(metadata.get("groups")))),
            "modules": len(list(_dict_items(metadata.get("modules")))),
            "screens": len(screens),
            "actions": len(actions),
        },
    )


def _check_screen(
    *,
    screen: dict[str, Any],
    screen_index: int,
    actions_by_key: dict[str, dict[str, Any]],
    actions_on_screen: list[dict[str, Any]],
    issues: list[UsabilityIssue],
) -> None:
    screen_key = str(screen["key"])
    path = f"screens[{screen_index}]"
    panels = list(_dict_items(screen.get("dashboard_panels")))
    default_action_key = str(screen.get("default_action_key") or "").strip()

    if not actions_on_screen and not panels:
        _add_issue(
            issues,
            "error",
            "screen.empty",
            f"Screen has no actions or dashboard panels: {screen_key}",
            path,
        )

    if not default_action_key and not panels and len(actions_on_screen) > 1:
        _add_issue(
            issues,
            "warning",
            "screen.missing_default_action",
            f"Screen has multiple actions but no default_action_key: {screen_key}",
            path,
        )

    if default_action_key:
        default_action = actions_by_key.get(default_action_key)
        if default_action and str(default_action.get("screen_key")) != screen_key:
            _add_issue(
                issues,
                "error",
                "screen.default_action_cross_screen",
                f"default_action_key points to another screen: {screen_key}.{default_action_key}",
                f"{path}.default_action_key",
            )

    seen_action_labels: dict[str, str] = {}
    for action in actions_on_screen:
        label = str(action.get("label") or "").strip().casefold()
        if not label:
            continue
        existing_key = seen_action_labels.get(label)
        if existing_key:
            _add_issue(
                issues,
                "warning",
                "action.duplicate_label_on_screen",
                f"Actions share the same label on one screen: {existing_key}, {action['key']}",
                f"actions.{action['key']}.label",
            )
        else:
            seen_action_labels[label] = str(action["key"])

    for panel_index, panel in enumerate(panels):
        panel_path = f"{path}.dashboard_panels[{panel_index}]"
        panel_kind = str(panel.get("kind") or "")
        action_key = str(panel.get("action_key") or "").strip()
        if panel_kind != "placeholder" and not action_key:
            _add_issue(
                issues,
                "warning",
                "panel.missing_action",
                f"Dashboard panel has no action_key: {screen_key}.{panel.get('key')}",
                panel_path,
            )
            continue
        panel_action = actions_by_key.get(action_key)
        if panel_action and str(panel_action.get("screen_key")) != screen_key:
            _add_issue(
                issues,
                "error",
                "panel.action_cross_screen",
                f"Dashboard panel points to an action on another screen: {screen_key}.{panel.get('key')}",
                f"{panel_path}.action_key",
            )


def _check_action(*, action: dict[str, Any], action_index: int, issues: list[UsabilityIssue]) -> None:
    action_key = str(action["key"])
    path = f"actions[{action_index}]"
    risk = str(action.get("risk") or "read")
    method = str(action.get("method") or "GET").upper()
    fields = list(_dict_items(action.get("fields")))
    view_model = dict(action.get("view_model") or {})
    view_kind = str(view_model.get("kind") or action.get("view_type") or "auto")

    _check_action_view_model(
        action_key=action_key,
        path=f"{path}.view_model",
        view_kind=view_kind,
        view_model=view_model,
        issues=issues,
    )
    _check_action_fields(action_key=action_key, path=f"{path}.fields", fields=fields, issues=issues)
    _check_action_pagination(
        action_key=action_key,
        path=f"{path}.pagination",
        view_kind=view_kind,
        view_model=view_model,
        fields=fields,
        pagination=action.get("pagination"),
        issues=issues,
    )

    if risk in {"write", "admin"} and method != "GET" and not str(action.get("executor") or "").strip():
        _add_issue(
            issues,
            "warning",
            "action.missing_executor_label",
            f"Governed action has no executor label for host routing clarity: {action_key}",
            f"{path}.executor",
        )

    if risk in {"write", "admin", "unsafe"} and not fields:
        _add_issue(
            issues,
            "warning",
            "action.no_operator_inputs",
            f"High-impact action has no visible operator inputs: {action_key}",
            f"{path}.fields",
        )


def _check_action_view_model(
    *,
    action_key: str,
    path: str,
    view_kind: str,
    view_model: dict[str, Any],
    issues: list[UsabilityIssue],
) -> None:
    required_by_kind = {
        "chart": ("data_path", "x_path", "y_path"),
        "image": ("url_path",),
        "kpi_trend": ("data_path", "label_path", "value_path"),
        "table_chart": ("table_rows_path",),
        "host_slot": ("slot_key", "partial_path", "fallback_message"),
    }
    for key in required_by_kind.get(view_kind, ()):
        if not str(view_model.get(key) or "").strip():
            _add_issue(
                issues,
                "error",
                "view_model.missing_renderer_path",
                f"{view_kind} action is missing view_model.{key}: {action_key}",
                f"{path}.{key}",
            )

    if view_kind == "datagrid" and not str(view_model.get("rows_path") or "").strip():
        _add_issue(
            issues,
            "warning",
            "view_model.missing_rows_path",
            f"Datagrid action has no rows_path, so runtime must guess row data: {action_key}",
            f"{path}.rows_path",
        )


def _check_action_fields(
    *,
    action_key: str,
    path: str,
    fields: list[dict[str, Any]],
    issues: list[UsabilityIssue],
) -> None:
    seen_keys: set[str] = set()
    for index, field in enumerate(fields):
        field_key = str(field.get("key") or "")
        field_path = f"{path}[{index}]"
        if field_key in seen_keys:
            _add_issue(
                issues,
                "error",
                "field.duplicate_key",
                f"Action has duplicate field key: {action_key}.{field_key}",
                field_path,
            )
        seen_keys.add(field_key)

        input_type = str(field.get("input_type") or "text")
        required = bool(field.get("required"))
        has_default = field.get("default") not in (None, "")
        placeholder = str(field.get("placeholder") or "").strip()

        if input_type == "hidden" and required and not has_default:
            _add_issue(
                issues,
                "error",
                "field.hidden_required_without_default",
                f"Required hidden field has no default value: {action_key}.{field_key}",
                f"{field_path}.default",
            )

        if input_type == "select" and not field.get("options"):
            _add_issue(
                issues,
                "error",
                "field.empty_select_options",
                f"Select field has no options for the operator to choose: {action_key}.{field_key}",
                f"{field_path}.options",
            )

        if required and input_type != "hidden" and not has_default and not placeholder:
            _add_issue(
                issues,
                "warning",
                "field.required_without_hint",
                f"Required field has no default or placeholder hint: {action_key}.{field_key}",
                field_path,
            )


def _check_action_pagination(
    *,
    action_key: str,
    path: str,
    view_kind: str,
    view_model: dict[str, Any],
    fields: list[dict[str, Any]],
    pagination: Any,
    issues: list[UsabilityIssue],
) -> None:
    if pagination:
        return
    if view_kind != "datagrid":
        return
    field_keys = {_normalize_field_key(str(field.get("key") or "")) for field in fields}
    has_offset_pair = {"offset", "limit"}.issubset(field_keys) or {"start", "limit"}.issubset(field_keys)
    has_page_pair = bool(field_keys & {"page", "pagenum", "pageno"}) and bool(
        field_keys & {"pagesize", "limit", "size"}
    )
    if str(view_model.get("total_path") or "").strip() or has_offset_pair or has_page_pair:
        _add_issue(
            issues,
            "warning",
            "pagination.missing_contract",
            f"Datagrid action appears paginated but has no action.pagination contract: {action_key}",
            path,
        )


def _normalize_field_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _group_actions_by_screen(actions: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for action in actions:
        grouped.setdefault(str(action.get("screen_key") or ""), []).append(action)
    return grouped


def _dict_items(value: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(value, list):
        return ()
    return (item for item in value if isinstance(item, dict))


def _add_issue(
    issues: list[UsabilityIssue],
    severity: UsabilitySeverity,
    code: str,
    message: str,
    path: str,
) -> None:
    issues.append(UsabilityIssue(severity=severity, code=code, message=message, path=path))
