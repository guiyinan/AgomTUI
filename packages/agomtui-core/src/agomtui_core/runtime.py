"""Framework-free server-side runtime helpers for AgomTUI adapters."""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from math import ceil
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .metadata import validate_tui_metadata

RuntimeMetadataHook = Callable[[dict[str, Any]], dict[str, Any]]
TUI_AUDIT_SCHEMA_VERSION = "tui-audit.v1"

_IDENTIFIER_FIELDS = {
    "id",
    "pk",
    "key",
    "code",
    "symbol",
    "account_id",
    "portfolio_id",
    "task_id",
    "request_id",
    "report_id",
    "snapshot_id",
    "run_id",
}
_IMAGE_URL_KEYS = (
    "image_url",
    "imageUrl",
    "img_url",
    "imgUrl",
    "thumbnail_url",
    "thumbnailUrl",
    "preview_url",
    "previewUrl",
    "cover_url",
    "coverUrl",
    "avatar_url",
    "avatarUrl",
    "src",
    "url",
    "href",
    "image",
)
_IMAGE_URL_EXTENSIONS = (".apng", ".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp")
_SAFE_IMAGE_DATA_PATTERN = re.compile(r"^data:image/(?:apng|avif|gif|jpe?g|png|webp);", re.IGNORECASE)
_SVG_IMAGE_DATA_PATTERN = re.compile(r"^data:image/svg\+xml(?:[;,]|$)", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"</?\s*[a-zA-Z][a-zA-Z0-9:-]*(?:\s+[^<>]*)?>")
_ESCAPED_HTML_TAG_PATTERN = re.compile(r"&lt;/?\s*[a-zA-Z][a-zA-Z0-9:-]*")
_SENSITIVE_PARAM_TOKENS = (
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "otp",
    "passcode",
    "password",
    "secret",
    "token",
)


def humanize_runtime_key(value: str) -> str:
    """Return a generic operator label for one metadata key."""

    normalized = str(value or "").strip()
    if not normalized:
        return ""
    parts = [part for part in normalized.replace("-", "_").split(".") if part]
    rendered: list[str] = []
    for part in parts:
        tokens = [token for token in re.split(r"_+", part) if token]
        if not tokens:
            continue
        rendered.append(" ".join(_humanize_token(token) for token in tokens))
    return " / ".join(rendered)


def normalize_action_field(
    field: Mapping[str, Any],
    *,
    action: Mapping[str, Any] | None = None,
    default_resolver: Callable[[Mapping[str, Any] | None, Mapping[str, Any]], Any] | None = None,
    field_labeler: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Return one action field with generic labels, defaults, and placeholders filled."""

    payload = copy.deepcopy(dict(field))
    key = str(payload.get("key") or "").strip()
    if not key:
        return payload
    labeler = field_labeler or humanize_runtime_key
    if not str(payload.get("label") or "").strip():
        payload["label"] = labeler(key)
    if _is_blank(payload.get("default")) and default_resolver is not None:
        resolved_default = default_resolver(action, payload)
        if not _is_blank(resolved_default):
            payload["default"] = resolved_default
    if payload.get("required") and not str(payload.get("placeholder") or "").strip():
        payload["placeholder"] = f"Enter {payload['label']}"
    return payload


def apply_default_field_values(
    action: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    default_resolver: Callable[[Mapping[str, Any] | None, Mapping[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Apply field defaults to one action parameter payload."""

    resolved = dict(params or {})
    for field in action.get("fields") or []:
        normalized = normalize_action_field(
            field,
            action=action,
            default_resolver=default_resolver,
        )
        key = str(normalized.get("key") or "").strip()
        if not key or not _is_blank(resolved.get(key)):
            continue
        default = normalized.get("default")
        if _is_blank(default):
            continue
        resolved[key] = default
    return resolved


def missing_required_fields(
    action: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    default_resolver: Callable[[Mapping[str, Any] | None, Mapping[str, Any]], Any] | None = None,
    field_labeler: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    """Return normalized required fields still missing from one action payload."""

    missing: list[dict[str, Any]] = []
    for field in action.get("fields") or []:
        normalized = normalize_action_field(
            field,
            action=action,
            default_resolver=default_resolver,
            field_labeler=field_labeler,
        )
        if not normalized.get("required"):
            continue
        key = str(normalized.get("key") or "").strip()
        if not key or not _is_blank(normalized.get("default")):
            continue
        if _is_blank(params.get(key)):
            missing.append(normalized)
    return missing


def action_requires_confirmation(action: Mapping[str, Any]) -> bool:
    """Return whether one action should require operator confirmation."""

    if bool(action.get("confirmation_required")):
        return True
    risk = str(action.get("risk") or "").strip().lower()
    method = str(action.get("method") or "GET").strip().upper()
    return risk == "write" or (risk == "admin" and method != "GET")


def action_requires_reauth(action: Mapping[str, Any]) -> bool:
    """Return whether one action must pass a re-authentication challenge."""

    return bool(action.get("requires_password"))


def action_requires_audit(action: Mapping[str, Any]) -> bool:
    """Return whether one action must emit a canonical audit record."""

    if bool(action.get("audit_required")):
        return True
    risk = str(action.get("risk") or "").strip().lower()
    method = str(action.get("method") or "GET").strip().upper()
    return risk in {"write", "admin"} and method != "GET"


def build_runtime_action_result(
    action: Mapping[str, Any],
    view_model: Mapping[str, Any],
    *,
    status_code: int = 200,
    raw_response: Any | None = None,
    raw_available: bool | None = None,
    version: str = "tui-workbench.v2",
) -> dict[str, Any]:
    """Return the standard runtime action response envelope."""

    allow_raw = bool(action.get("raw_debug", True)) if raw_available is None else bool(raw_available)
    return {
        "version": version,
        "action": copy.deepcopy(dict(action)),
        "confirmation_required": False,
        "response": {"status_code": int(status_code)},
        "view_model": copy.deepcopy(dict(view_model)),
        "debug": {
            "raw_available": allow_raw,
            "raw_response": copy.deepcopy(raw_response) if allow_raw else None,
        },
    }


def build_password_challenge_required_result(
    action: Mapping[str, Any],
    *,
    message: str | None = None,
    challenge_id: str = "",
    version: str = "tui-workbench.v2",
) -> dict[str, Any]:
    """Return the standard re-authentication challenge contract."""

    action_title = str(action.get("label") or action.get("key") or "Action")
    resolved_message = message or f"{action_title} requires identity verification before execution."
    return {
        "version": version,
        "action": copy.deepcopy(dict(action)),
        "confirmation_required": False,
        "password_challenge_required": True,
        "password_challenge": {
            "challenge_id": challenge_id,
            "message": resolved_message,
            "field": {
                "key": "password",
                "label": "Password",
                "input_type": "password",
                "required": True,
            },
        },
        "response": {"status_code": 401},
        "view_model": {
            "kind": "message",
            "title": action_title,
            "status": "Password required",
            "message": resolved_message,
            "sections": [
                {
                    "title": "Identity verification",
                    "rows": [],
                    "body": [resolved_message],
                }
            ],
            "raw_hint": "No host action was executed before re-authentication.",
        },
        "debug": {"raw_available": False, "raw_response": None},
    }


def build_confirmation_required_result(
    action: Mapping[str, Any],
    *,
    message: str | None = None,
    view_model: Mapping[str, Any] | None = None,
    title: str = "Confirm action",
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    version: str = "tui-workbench.v2",
) -> dict[str, Any]:
    """Return the standard confirmation-required contract."""

    action_title = str(action.get("label") or action.get("key") or "Action")
    resolved_message = message or f"{action_title} changes system state and requires confirmation before execution."
    preview = copy.deepcopy(dict(view_model)) if view_model is not None else {
        "kind": "message",
        "title": action_title,
        "status": "Pending confirmation",
        "message": resolved_message,
        "sections": [
            {
                "title": "Review",
                "rows": [],
                "body": [resolved_message],
            }
        ],
        "raw_hint": "Raw responses remain available only after the confirmed run completes.",
    }
    return {
        "version": version,
        "action": copy.deepcopy(dict(action)),
        "confirmation_required": True,
        "confirmation": {
            "title": title,
            "message": resolved_message,
            "confirm_label": confirm_label,
            "cancel_label": cancel_label,
        },
        "response": {"status_code": 409},
        "view_model": preview,
        "debug": {"raw_available": False, "raw_response": None},
    }


def build_missing_fields_result(
    action: Mapping[str, Any],
    missing_fields: Sequence[Mapping[str, Any]],
    *,
    message: str | None = None,
    version: str = "tui-workbench.v2",
) -> dict[str, Any]:
    """Return the standard missing-required-fields contract."""

    action_title = str(action.get("label") or action.get("key") or "Action")
    labels = [
        str(field.get("label") or field.get("key") or "field")
        for field in missing_fields
    ]
    resolved_message = message or f"{action_title} requires additional input: {', '.join(labels)}."
    view_model = {
        "kind": "message",
        "title": action_title,
        "status": "Missing input",
        "message": resolved_message,
        "sections": [
            {
                "title": "Required fields",
                "rows": [
                    {
                        "label": str(field.get("label") or field.get("key") or "Field"),
                        "value": str(
                            field.get("placeholder")
                            or f"Enter {field.get('label') or field.get('key') or 'value'}"
                        ),
                    }
                    for field in missing_fields
                ],
                "body": [
                    "Complete the action form and run the task again.",
                ],
            }
        ],
        "raw_hint": "No host call was made because the required inputs are incomplete.",
    }
    return {
        "version": version,
        "action": copy.deepcopy(dict(action)),
        "confirmation_required": False,
        "response": {"status_code": 400},
        "view_model": view_model,
        "missing_fields": [copy.deepcopy(dict(field)) for field in missing_fields],
        "debug": {"raw_available": False, "raw_response": None},
    }


def build_audit_record(
    action: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    actor: str,
    outcome: str,
    confirmation_evidence: Mapping[str, Any] | None = None,
    reauth_evidence: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
    error: str = "",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Return one canonical append-only audit record payload."""

    response = result.get("response") if isinstance(result, Mapping) else {}
    status_code = response.get("status_code") if isinstance(response, Mapping) else None
    return {
        "schema_version": TUI_AUDIT_SCHEMA_VERSION,
        "occurred_at": occurred_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": str(actor or "anonymous"),
        "action_key": str(action.get("key") or ""),
        "action_label": str(action.get("label") or ""),
        "risk": str(action.get("risk") or "read"),
        "sensitive_level": str(action.get("sensitive_level") or "none"),
        "audit_required": bool(action_requires_audit(action)),
        "params": mask_sensitive_params(action, params),
        "confirmation": _audit_confirmation_payload(confirmation_evidence),
        "reauth": _audit_reauth_payload(reauth_evidence),
        "outcome": str(outcome),
        "result": {
            "status_code": status_code,
            "confirmation_required": bool(result.get("confirmation_required")) if isinstance(result, Mapping) else False,
            "password_challenge_required": bool(result.get("password_challenge_required")) if isinstance(result, Mapping) else False,
            "missing_fields": [
                str(field.get("key") or "")
                for field in (result.get("missing_fields") if isinstance(result, Mapping) else []) or []
                if isinstance(field, Mapping)
            ],
            "error": str(error or ""),
        },
    }


def mask_sensitive_params(action: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """Return params with credential-like fields masked for audit storage."""

    sensitive_keys = {
        str(field.get("key") or "")
        for field in action.get("fields") or []
        if isinstance(field, Mapping) and _is_sensitive_param_key(str(field.get("key") or ""))
    }
    masked: dict[str, Any] = {}
    for key, value in dict(params or {}).items():
        normalized_key = str(key)
        if normalized_key in sensitive_keys or _is_sensitive_param_key(normalized_key):
            masked[normalized_key] = "***"
            continue
        masked[normalized_key] = copy.deepcopy(value)
    return masked


class GovernedActionRunner:
    """Single no-bypass execution path for governed runtime actions."""

    def __init__(
        self,
        executor: Any,
        audit_sink: Any | None = None,
        reauth_verifier: Callable[[Mapping[str, Any], Mapping[str, Any], Any | None], bool] | None = None,
    ) -> None:
        self.executor = executor
        self.audit_sink = audit_sink
        self.reauth_verifier = reauth_verifier

    def execute(
        self,
        action: Mapping[str, Any],
        params: Mapping[str, Any],
        *,
        context: Any | None = None,
        actor: str = "",
        confirmed: bool = False,
        confirmation_evidence: Mapping[str, Any] | None = None,
        reauth_evidence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Enforce missing-fields, confirmation, re-auth, audit, then execute."""

        resolved_params = apply_default_field_values(action, params)
        missing = missing_required_fields(action, resolved_params)
        if missing:
            result = build_missing_fields_result(action, missing)
            self._audit(
                action,
                resolved_params,
                actor=actor,
                outcome="rejected_missing_fields",
                confirmation_evidence=confirmation_evidence,
                reauth_evidence=reauth_evidence,
                result=result,
            )
            return result

        if action_requires_confirmation(action) and not confirmed:
            result = build_confirmation_required_result(action)
            self._audit(
                action,
                resolved_params,
                actor=actor,
                outcome="blocked_confirmation_required",
                confirmation_evidence=confirmation_evidence,
                reauth_evidence=reauth_evidence,
                result=result,
            )
            return result

        if action_requires_reauth(action) and not self._reauth_verified(action, reauth_evidence, context):
            outcome = "blocked_reauth_required" if not reauth_evidence else "blocked_reauth_failed"
            result = build_password_challenge_required_result(action)
            self._audit(
                action,
                resolved_params,
                actor=actor,
                outcome=outcome,
                confirmation_evidence=confirmation_evidence,
                reauth_evidence=reauth_evidence,
                result=result,
            )
            return result

        if action_requires_reauth(action):
            reauth_evidence = _verified_reauth_evidence(reauth_evidence)
        self._ensure_audit_sink(action)
        try:
            result = self.executor.execute(
                method=str(action.get("method") or "GET").upper(),
                endpoint=str(action.get("endpoint") or ""),
                params=dict(resolved_params),
                body=dict(resolved_params),
                context=context,
            )
        except Exception as exc:
            self._audit(
                action,
                resolved_params,
                actor=actor,
                outcome="failed_exception",
                confirmation_evidence=confirmation_evidence,
                reauth_evidence=reauth_evidence,
                error=str(exc),
            )
            raise

        status_code = _result_status_code(result)
        self._audit(
            action,
            resolved_params,
            actor=actor,
            outcome="succeeded" if 200 <= status_code < 400 else "failed",
            confirmation_evidence=confirmation_evidence,
            reauth_evidence=reauth_evidence,
            result=result,
        )
        return result

    def _audit(
        self,
        action: Mapping[str, Any],
        params: Mapping[str, Any],
        *,
        actor: str,
        outcome: str,
        confirmation_evidence: Mapping[str, Any] | None = None,
        reauth_evidence: Mapping[str, Any] | None = None,
        result: Mapping[str, Any] | None = None,
        error: str = "",
    ) -> None:
        if not action_requires_audit(action):
            return
        self._ensure_audit_sink(action)
        self.audit_sink.append(
            build_audit_record(
                action,
                params,
                actor=actor,
                outcome=outcome,
                confirmation_evidence=confirmation_evidence,
                reauth_evidence=reauth_evidence,
                result=result,
                error=error,
            )
        )

    def _ensure_audit_sink(self, action: Mapping[str, Any]) -> None:
        if action_requires_audit(action) and self.audit_sink is None:
            raise RuntimeError(f"Audit sink is required for audit_required action: {action.get('key')}")

    def _reauth_verified(
        self,
        action: Mapping[str, Any],
        reauth_evidence: Mapping[str, Any] | None,
        context: Any | None,
    ) -> bool:
        if not action_requires_reauth(action):
            return True
        if not reauth_evidence or self.reauth_verifier is None:
            return False
        return bool(self.reauth_verifier(action, reauth_evidence, context))


def looks_like_password_challenge(status_code: int, payload: Any | None) -> bool:
    """Return whether one host response looks like a password challenge."""

    if int(status_code) != 401 or not isinstance(payload, dict):
        return False
    if bool(payload.get("requires_password")):
        return True
    for key in ("detail", "error", "message"):
        value = payload.get(key)
        if isinstance(value, str) and "password" in value.lower():
            return True
    return False


def normalize_runtime_metadata_payload(
    payload: Mapping[str, Any],
    *,
    redundant_screen_action_keys: Mapping[str, set[str]] | None = None,
    screen_patches: Mapping[str, Mapping[str, Any]] | None = None,
    action_patches: Mapping[str, Mapping[str, Any]] | None = None,
    hooks: Sequence[RuntimeMetadataHook] | None = None,
) -> dict[str, Any]:
    """Apply runtime-only screen/action pruning, patches, and hook-based normalization."""

    normalized = validate_tui_metadata(copy.deepcopy(dict(payload)))
    redundant_map = redundant_screen_action_keys or {}
    screen_patch_map = screen_patches or {}
    patches = action_patches or {}
    screen_action_keys = {str(action.get("key") or "") for action in normalized.get("actions") or []}
    patched_screens = 0

    if screen_patch_map:
        patched_screen_items: list[dict[str, Any]] = []
        for screen in normalized.get("screens") or []:
            screen_key = str(screen.get("key") or "")
            patch = screen_patch_map.get(screen_key)
            if patch:
                resolved_patch = _resolve_screen_patch(patch, screen_action_keys)
                updated = copy.deepcopy(screen)
                _deep_merge_runtime_patch(updated, resolved_patch)
                patched_screen_items.append(updated)
                if updated != screen:
                    patched_screens += 1
                continue
            patched_screen_items.append(screen)
        if patched_screens:
            normalized["screens"] = patched_screen_items

    kept_actions: list[dict[str, Any]] = []
    removed = 0
    patched = 0

    for action in normalized.get("actions") or []:
        screen_key = str(action.get("screen_key") or "")
        action_key = str(action.get("key") or "")
        if action_key in redundant_map.get(screen_key, set()):
            removed += 1
            continue
        patch = patches.get(action_key)
        if patch:
            updated, changed = _apply_runtime_action_patch(action, patch)
            kept_actions.append(updated)
            if changed:
                patched += 1
            continue
        kept_actions.append(action)

    if removed or patched or patched_screens:
        normalized["actions"] = kept_actions
        coverage = dict(normalized.get("coverage_summary") or {})
        if patched_screens:
            coverage["runtime_patched_screens"] = int(
                coverage.get("runtime_patched_screens", 0) or 0
            ) + patched_screens
        if removed:
            coverage["runtime_pruned_redundant_screen_actions"] = int(
                coverage.get("runtime_pruned_redundant_screen_actions", 0) or 0
            ) + removed
        if patched:
            coverage["runtime_patched_actions"] = int(
                coverage.get("runtime_patched_actions", 0) or 0
            ) + patched
        normalized["coverage_summary"] = coverage
        normalized = validate_tui_metadata(normalized)

    for hook in hooks or []:
        candidate = hook(copy.deepcopy(normalized))
        if not isinstance(candidate, dict):
            raise ValueError("Runtime metadata hook must return a metadata object")
        normalized = validate_tui_metadata(candidate)
    return normalized


def _resolve_screen_patch(patch: Mapping[str, Any], action_keys: set[str]) -> dict[str, Any]:
    resolved = copy.deepcopy(dict(patch))
    panels = patch.get("dashboard_panels")
    if not isinstance(panels, list):
        return resolved
    resolved["dashboard_panels"] = [
        panel
        for panel in panels
        if not isinstance(panel, Mapping)
        or str(panel.get("action_key") or "").strip() == ""
        or str(panel.get("action_key") or "").strip() in action_keys
    ]
    return resolved


class GenericRuntimeViewModelBuilder:
    """Infer generic runtime view models from host payloads and action metadata."""

    def __init__(
        self,
        *,
        field_labeler: Callable[[str], str] | None = None,
        password_challenge_hint: str = "Provide the required password and retry the action.",
        default_page_size: int = 20,
        allow_svg_data_images: bool = True,
    ) -> None:
        self.field_labeler = field_labeler or humanize_runtime_key
        self.password_challenge_hint = password_challenge_hint
        self.default_page_size = default_page_size
        self.allow_svg_data_images = allow_svg_data_images

    def infer(
        self,
        *,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
        request_params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Infer one renderable view model from a host payload."""

        data = self._unwrap_payload(payload)
        forced_kind = self._view_model_path(action, "kind")
        view_type = str(action.get("view_type") or "").strip()
        if isinstance(data, dict) and self._is_endpoint_directory(data):
            return self._endpoint_directory_model(action, data, status_code)
        if forced_kind == "chart":
            return self._chart_model(action, data, status_code)
        if forced_kind == "image" or view_type == "image":
            return self._image_model(action, data, status_code)
        if forced_kind == "kpi_trend":
            return self._kpi_trend_model(action, data, status_code)
        if forced_kind == "table_chart":
            return self._table_chart_model(action, data, status_code)
        if forced_kind == "host_slot":
            return self._host_slot_model(action, data, status_code)
        if forced_kind == "custom":
            return self._custom_model(action, data, status_code)
        if forced_kind == "detail" and isinstance(data, dict):
            return self._detail_model(action, data, status_code)
        if forced_kind == "message":
            return self._message_model(action, self._display_value(data), status_code)
        if forced_kind == "datagrid":
            if isinstance(data, list):
                return self._datagrid_model(action, data, status_code, request_params=request_params)
            if isinstance(data, dict):
                rows_path = self._view_model_path(action, "rows_path")
                if not rows_path and self._looks_like_detail_payload(data):
                    return self._detail_model(action, data, status_code)
                explicit = self._value_at_path(data, rows_path) if rows_path else None
                list_value = explicit if isinstance(explicit, list) else self._find_list_value(data)
                if list_value is not None:
                    return self._datagrid_model(
                        action,
                        list_value,
                        status_code,
                        envelope=data,
                        request_params=request_params,
                    )
        if isinstance(data, list):
            return self._datagrid_model(action, data, status_code, request_params=request_params)
        if isinstance(data, dict):
            html_text = self._dominant_html_text(data)
            if html_text:
                return self._message_model(action, html_text, status_code)
            if str(action.get("view_type") or "") in {"status", "detail", "queue_workbench"}:
                return self._detail_model(action, data, status_code)
            if str(action.get("view_type") or "") == "datagrid" and self._looks_like_detail_payload(data):
                return self._detail_model(action, data, status_code)
            rows_path = self._view_model_path(action, "rows_path")
            explicit = self._value_at_path(data, rows_path) if rows_path else None
            list_value = explicit if isinstance(explicit, list) else self._find_list_value(data)
            if list_value is not None:
                return self._datagrid_model(
                    action,
                    list_value,
                    status_code,
                    envelope=data,
                    request_params=request_params,
                )
            return self._detail_model(action, data, status_code)
        if isinstance(data, str) and self._looks_like_image_url(data, require_image_hint=True):
            return self._image_model(action, data, status_code)
        if self._looks_like_html(data):
            return self._message_model(action, self._html_to_text(str(data)), status_code)
        return self._message_model(action, self._display_value(data), status_code)

    def _action_title(self, action: Mapping[str, Any]) -> str:
        label = str(action.get("label") or "").strip()
        if label:
            return label
        return humanize_runtime_key(str(action.get("key") or "Result"))

    def _unwrap_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict) and "data" in payload and len(payload) <= 4:
            return payload.get("data")
        return payload

    def _view_model_path(self, action: Mapping[str, Any], key: str) -> str:
        view_model = action.get("view_model") or {}
        if not isinstance(view_model, dict):
            return ""
        return str(view_model.get(key) or "").strip()

    def _value_at_path(self, payload: Any, path: str) -> Any:
        if not path:
            return None
        current = payload
        for part in path.split("."):
            if not part:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if 0 <= index < len(current) else None
            else:
                return None
        return current

    def _find_list_value(self, payload: Mapping[str, Any]) -> list[Any] | None:
        candidates = self._list_candidates(payload)
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]

    def _list_candidates(self, value: Any, *, depth: int = 0) -> list[tuple[int, list[Any]]]:
        if depth > 3:
            return []
        if isinstance(value, list):
            return [(self._list_score(value, depth), value)]
        if not isinstance(value, dict):
            return []
        candidates: list[tuple[int, list[Any]]] = []
        for child in value.values():
            candidates.extend(self._list_candidates(child, depth=depth + 1))
        return candidates

    def _list_score(self, rows: list[Any], depth: int) -> int:
        if not rows:
            return 0
        sample = rows[:5]
        dict_rows = sum(1 for row in sample if isinstance(row, dict))
        scalar_rows = sum(1 for row in sample if not isinstance(row, (dict, list)))
        return dict_rows * 10 + scalar_rows * 4 + min(len(rows), 20) - (depth * 4)

    def _datagrid_model(
        self,
        action: Mapping[str, Any],
        rows: list[Any],
        status_code: int,
        envelope: Mapping[str, Any] | None = None,
        request_params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        message_list = self._message_list_text(rows)
        if message_list:
            return self._message_model(action, message_list, status_code)
        normalized_rows = [row if isinstance(row, dict) else {"value": row} for row in rows]
        columns = self._columns_for_rows(normalized_rows)
        pagination = action.get("pagination") if isinstance(action.get("pagination"), Mapping) else {}
        pagination_mode = str(pagination.get("mode") or "page")
        page_size_param = str(
            (pagination.get("limit_param") if pagination_mode == "offset" else pagination.get("page_size_param")) or ""
        ).strip()
        page_size = self._first_positive_int(
            self._int_from_path(action, envelope, "page_size_path", default=0),
            self._int_from_mapping_path(envelope, page_size_param),
            self._int_from_mapping_path(request_params, page_size_param),
            self.default_page_size,
        )
        total = int(self._int_from_path(action, envelope, "total_path", default=0) or len(normalized_rows))
        page = self._first_positive_int(
            self._int_from_path(action, envelope, "page_path", default=0),
            self._int_from_mapping_path(
                envelope,
                str(pagination.get("page_param") or "").strip() if pagination_mode == "page" else "",
            ),
            self._int_from_mapping_path(
                request_params,
                str(pagination.get("page_param") or "").strip() if pagination_mode == "page" else "",
            ),
            1,
        )
        offset = 0
        if pagination_mode == "offset":
            offset_param = str(pagination.get("offset_param") or "").strip()
            offset = max(
                0,
                self._first_int(
                    self._int_from_mapping_path(envelope, offset_param),
                    self._int_from_mapping_path(request_params, offset_param),
                    0,
                ),
            )
            page = max(1, (offset // page_size) + 1)
            has_previous = offset > 0
            has_next = offset + page_size < total
        else:
            has_previous = page > 1
            has_next = page * page_size < total
        return {
            "kind": "datagrid",
            "title": self._action_title(action),
            "status": self._status_label(status_code, envelope),
            "columns": columns,
            "rows": [
                self._datagrid_row_payload(row, columns)
                for row in normalized_rows[:page_size]
            ],
            "empty_message": "No rows available." if total == 0 else "This page has no rows.",
            "pager": {
                "page": page,
                "page_size": page_size,
                "offset": offset,
                "mode": pagination_mode,
                "total_rows": total,
                "total_pages": max(1, ceil(total / page_size)),
                "has_next": has_next,
                "has_previous": has_previous,
            },
        }

    def _datagrid_row_payload(
        self,
        row: Mapping[str, Any],
        columns: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for column in columns:
            key = str(column.get("key") or "")
            display_value = self._display_value_for_key(key, row.get(key), row)
            payload[key] = display_value
            raw_value = row.get(key)
            if self._should_preserve_raw_row_value(key, raw_value, display_value):
                payload[f"__raw_{key}"] = raw_value
        for key, value in row.items():
            normalized_key = str(key)
            if normalized_key.startswith("__"):
                normalized_key = normalized_key[2:]
            if normalized_key in payload or isinstance(value, (dict, list)):
                continue
            if not self._should_preserve_row_identifier(normalized_key):
                continue
            payload[normalized_key] = self._display_value_for_key(normalized_key, value, row)
        return payload

    def _chart_model(
        self,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
    ) -> dict[str, Any]:
        config = action.get("view_model") if isinstance(action.get("view_model"), Mapping) else {}
        data = self._list_from_config_path(payload, action, "data_path") or self._list_from_config_path(payload, action, "series_path")
        if data is None and isinstance(payload, list):
            data = payload
        if data is None and isinstance(payload, Mapping):
            data = self._find_list_value(payload)
        points = self._chart_points(action, data or [])
        return {
            "kind": "chart",
            "renderer": str(config.get("renderer") or config.get("chart_type") or "line"),
            "chart_type": str(config.get("chart_type") or config.get("renderer") or "line"),
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "series": [
                {
                    "name": self._action_title(action),
                    "points": points,
                }
            ],
            "empty_message": "No chart data available.",
        }

    def _kpi_trend_model(
        self,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
    ) -> dict[str, Any]:
        value_path = self._view_model_path(action, "value_path")
        label_path = self._view_model_path(action, "label_path")
        data = payload if isinstance(payload, Mapping) else {}
        value = self._value_at_path(data, value_path) if value_path and isinstance(data, Mapping) else None
        label = self._value_at_path(data, label_path) if label_path and isinstance(data, Mapping) else None
        trend_rows = self._list_from_config_path(payload, action, "data_path")
        points = self._chart_points(action, trend_rows or [])
        if value is None and points:
            value = points[-1]["value"]
        return {
            "kind": "kpi_trend",
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "label": str(label or self._action_title(action)),
            "value": self._display_value(value),
            "trend": points,
            "empty_message": "No KPI data available.",
        }

    def _image_model(
        self,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
    ) -> dict[str, Any]:
        config = action.get("view_model") if isinstance(action.get("view_model"), Mapping) else {}
        data = payload if isinstance(payload, Mapping) else None
        url = ""
        alt = ""
        caption = ""
        if isinstance(data, Mapping):
            url_path = str(config.get("url_path") or "").strip()
            alt_path = str(config.get("alt_path") or "").strip()
            caption_path = str(config.get("caption_path") or "").strip()
            if url_path:
                url = self._string_at_path(data, url_path)
            if alt_path:
                alt = self._string_at_path(data, alt_path)
            if caption_path:
                caption = self._string_at_path(data, caption_path)
            if not url:
                url = self._first_mapping_string(data, _IMAGE_URL_KEYS)
            if not alt:
                alt = self._first_mapping_string(data, ("alt", "alt_text", "altText", "title", "name", "label"))
            if not caption:
                caption = self._first_mapping_string(data, ("caption", "description", "summary", "title", "name", "label"))
        elif isinstance(payload, str):
            url = payload.strip()
        elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
            for item in payload:
                if isinstance(item, str) and self._looks_like_image_url(item, require_image_hint=True):
                    url = item.strip()
                    break
                if isinstance(item, Mapping):
                    url = self._first_mapping_string(item, _IMAGE_URL_KEYS)
                    if url:
                        alt = self._first_mapping_string(item, ("alt", "alt_text", "altText", "title", "name", "label"))
                        caption = self._first_mapping_string(item, ("caption", "description", "summary", "title", "name", "label"))
                        break
        return {
            "kind": "image",
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "url": url,
            "alt": alt or self._action_title(action),
            "caption": caption,
            "empty_message": "No image URL available.",
        }

    def _table_chart_model(
        self,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
    ) -> dict[str, Any]:
        rows = self._list_from_config_path(payload, action, "table_rows_path")
        if rows is None:
            rows = self._list_from_config_path(payload, action, "rows_path")
        if rows is None and isinstance(payload, list):
            rows = payload
        if rows is None and isinstance(payload, Mapping):
            rows = self._find_list_value(payload)
        table = self._datagrid_model(action, rows or [], status_code, envelope=payload if isinstance(payload, Mapping) else None)
        table_columns = self._list_from_config_path(payload, action, "table_columns_path")
        if table_columns and all(isinstance(column, Mapping) for column in table_columns):
            table["columns"] = [
                {
                    "key": str(column.get("key") or ""),
                    "label": str(column.get("label") or column.get("key") or ""),
                }
                for column in table_columns
                if str(column.get("key") or "")
            ]
        chart = self._chart_model(action, payload, status_code)
        return {
            "kind": "table_chart",
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "chart": chart,
            "table": table,
            "empty_message": "No table/chart data available.",
        }

    def _host_slot_model(
        self,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
    ) -> dict[str, Any]:
        config = action.get("view_model") if isinstance(action.get("view_model"), Mapping) else {}
        partial_path = str(config.get("partial_path") or "").strip()
        partial_html = ""
        if partial_path and isinstance(payload, Mapping):
            partial_value = self._value_at_path(payload, partial_path)
            partial_html = str(partial_value or "")
        elif isinstance(payload, Mapping):
            for key in ("partial_html", "html", "markup", "rendered", "content"):
                value = payload.get(key)
                if isinstance(value, str) and self._looks_like_html(value):
                    partial_html = value
                    break
        return {
            "kind": "host_slot",
            "renderer": str(config.get("renderer") or "host-slot"),
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "slot_key": str(config.get("slot_key") or action.get("key") or ""),
            "partial_html": partial_html,
            "fallback_message": str(config.get("fallback_message") or "Host slot content is controlled by the host application."),
        }

    def _custom_model(
        self,
        action: Mapping[str, Any],
        payload: Any,
        status_code: int,
    ) -> dict[str, Any]:
        config = action.get("view_model") if isinstance(action.get("view_model"), Mapping) else {}
        return {
            "kind": "custom",
            "renderer": str(config.get("renderer") or ""),
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "payload": copy.deepcopy(payload),
            "fallback_message": str(config.get("fallback_message") or "No renderer is registered for this custom view."),
        }

    def _list_from_config_path(
        self,
        payload: Any,
        action: Mapping[str, Any],
        key: str,
    ) -> list[Any] | None:
        path = self._view_model_path(action, key)
        if not path or not isinstance(payload, Mapping):
            return None
        value = self._value_at_path(payload, path)
        return value if isinstance(value, list) else None

    def _string_at_path(self, payload: Mapping[str, Any], path: str) -> str:
        value = self._value_at_path(payload, path)
        if value is None or isinstance(value, (dict, list)):
            return ""
        return str(value).strip()

    def _first_mapping_string(self, payload: Mapping[str, Any], keys: Sequence[str]) -> str:
        for key in keys:
            value = payload.get(key)
            if value is None or isinstance(value, (dict, list)):
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    def _chart_points(self, action: Mapping[str, Any], rows: Sequence[Any]) -> list[dict[str, Any]]:
        x_path = self._view_model_path(action, "x_path")
        y_path = self._view_model_path(action, "y_path")
        label_path = self._view_model_path(action, "label_path")
        value_path = self._view_model_path(action, "value_path")
        points: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if isinstance(row, Mapping):
                label = self._value_at_path(row, x_path or label_path) if (x_path or label_path) else None
                value = self._value_at_path(row, y_path or value_path) if (y_path or value_path) else None
                if label is None:
                    label = row.get("label") or row.get("date") or row.get("name") or row.get("x") or index + 1
                if value is None:
                    value = row.get("value") or row.get("y") or row.get("count") or row.get("total")
            else:
                label = index + 1
                value = row
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            points.append(
                {
                    "label": str(label),
                    "value": numeric_value,
                }
            )
        return points

    def _columns_for_rows(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
        keys: list[str] = []
        for row in rows[:12]:
            for key, value in row.items():
                if str(key).startswith("__"):
                    continue
                if key not in keys and not isinstance(value, (dict, list)):
                    keys.append(str(key))
        if not keys and rows:
            keys = [str(key) for key in rows[0].keys() if not str(key).startswith("__")][:6]
        return [{"key": key, "label": self.field_labeler(key)} for key in keys[:8]]

    def _should_preserve_row_identifier(self, key: str) -> bool:
        normalized = str(key or "").strip().lower().replace("-", "_")
        return normalized in _IDENTIFIER_FIELDS or normalized.endswith("_id")

    def _should_preserve_raw_row_value(
        self,
        key: str,
        raw_value: Any,
        display_value: str,
    ) -> bool:
        if _is_blank(raw_value) or isinstance(raw_value, (dict, list)):
            return False
        normalized = str(key or "").strip().lower().replace("-", "_")
        if not (
            self._should_preserve_row_identifier(normalized)
            or normalized == "code"
            or normalized.endswith("_code")
        ):
            return False
        return str(raw_value) != str(display_value)

    def _detail_model(
        self,
        action: Mapping[str, Any],
        payload: Mapping[str, Any],
        status_code: int,
    ) -> dict[str, Any]:
        fields = self._detail_fields(payload)
        if looks_like_password_challenge(status_code, payload):
            fields.append(
                {
                    "key": "next_step",
                    "label": "Next step",
                    "value": self.password_challenge_hint,
                }
            )
        nested = [
            {"key": key, "label": self.field_labeler(str(key)), "count": len(value)}
            for key, value in payload.items()
            if isinstance(value, list)
        ]
        return {
            "kind": "detail",
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "fields": fields,
            "nested": nested,
        }

    def _detail_fields(
        self,
        payload: Mapping[str, Any],
        *,
        prefix: str = "",
        depth: int = 0,
        limit: int = 24,
    ) -> list[dict[str, str]]:
        fields: list[dict[str, str]] = []
        for key, value in payload.items():
            if len(fields) >= limit:
                break
            field_key = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, list):
                continue
            if isinstance(value, dict):
                if depth < 1:
                    fields.extend(
                        self._detail_fields(
                            value,
                            prefix=field_key,
                            depth=depth + 1,
                            limit=limit - len(fields),
                        )
                    )
                else:
                    fields.append(
                        {
                            "key": field_key,
                            "label": self.field_labeler(field_key),
                            "value": f"{len(value)} fields",
                        }
                    )
                continue
            fields.append(
                {
                    "key": field_key,
                    "label": self.field_labeler(field_key),
                    "value": self._display_value_for_key(field_key, value, payload),
                }
            )
        return fields[:limit]

    def _message_model(
        self,
        action: Mapping[str, Any],
        message: str,
        status_code: int,
    ) -> dict[str, Any]:
        normalized_message = str(message or "").strip()
        return {
            "kind": "message",
            "title": self._action_title(action),
            "status": self._status_label(status_code, {"detail": normalized_message}),
            "message": normalized_message,
            "sections": self._message_sections(normalized_message),
            "raw_hint": "Raw responses are available in the debug drawer only.",
        }

    def _message_sections(self, message: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in str(message or "").splitlines() if line.strip()]
        if not lines:
            return []
        sections: list[dict[str, Any]] = []
        current = {"title": "Summary", "rows": [], "body": []}
        sections.append(current)
        for line in lines:
            if len(line) <= 40 and line.endswith(":"):
                current = {"title": line[:-1].strip() or "Summary", "rows": [], "body": []}
                sections.append(current)
                continue
            label, value = self._split_message_row(line)
            if label:
                current["rows"].append({"label": label, "value": value})
            else:
                current["body"].append(line)
        return sections[:12]

    def _split_message_row(self, line: str) -> tuple[str, str]:
        for separator in (":", " - "):
            if separator in line:
                label, value = line.split(separator, 1)
                if 1 <= len(label.strip()) <= 24 and value.strip():
                    return label.strip(), value.strip()
        return "", ""

    def _message_list_text(self, rows: Sequence[Any]) -> str:
        if not rows or len(rows) > 12:
            return ""
        if any(isinstance(row, (dict, list, tuple, set)) for row in rows):
            return ""
        messages = [str(row).strip() for row in rows if str(row).strip()]
        if len(messages) != len(rows):
            return ""
        if not any(len(message) >= 12 or ":" in message or " " in message for message in messages):
            return ""
        return "\n".join(messages)

    def _status_label(self, status_code: int, payload: Any | None = None) -> str:
        if 200 <= int(status_code) < 300:
            return "OK"
        if 300 <= int(status_code) < 400:
            return "Redirect"
        if looks_like_password_challenge(status_code, payload):
            return "Password required"
        if self._looks_like_empty_state(status_code, payload):
            return "No data"
        return "Error"

    def _looks_like_empty_state(self, status_code: int, payload: Any | None) -> bool:
        if int(status_code) != 404 or not isinstance(payload, dict):
            return False
        for key in ("detail", "error", "message"):
            value = payload.get(key)
            if not isinstance(value, str):
                continue
            normalized = value.strip().lower()
            if any(marker in normalized for marker in ("no ", "not found", "missing", "empty")):
                return True
        return False

    def _looks_like_detail_payload(self, payload: Mapping[str, Any]) -> bool:
        scalar_count = 0
        list_count = 0
        for value in payload.values():
            if isinstance(value, list):
                list_count += 1
            elif not isinstance(value, dict):
                scalar_count += 1
        return scalar_count > 0 and list_count == 0

    def _display_value_for_key(
        self,
        key: str,
        value: Any,
        row: Mapping[str, Any] | None = None,
    ) -> str:
        del key, row
        return self._display_value(value)

    def _display_value(self, value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return f"{len(value)} items"
        if isinstance(value, dict):
            return f"{len(value)} fields"
        text = str(value)
        if self._looks_like_html(text):
            return self._html_to_text(text)
        if self._is_internal_api_path(text):
            return "Internal API path (see debug drawer)"
        return text

    def _looks_like_html(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        text = value.strip()
        if not text:
            return False
        return bool(_HTML_TAG_PATTERN.search(text) or _ESCAPED_HTML_TAG_PATTERN.search(text))

    def _html_to_text(self, value: str) -> str:
        parser = _PlainTextHtmlParser()
        parser.feed(unescape(value))
        parser.close()
        text = parser.text()
        if not text:
            text = _HTML_TAG_PATTERN.sub(" ", unescape(value))
            text = re.sub(r"\s+", " ", text).strip()
        return text[:4000]

    def _dominant_html_text(self, payload: Mapping[str, Any]) -> str:
        html_keys = {"body", "content", "html", "markup", "partial", "rendered", "template"}
        html_values = [
            self._html_to_text(str(value))
            for key, value in payload.items()
            if not isinstance(value, (dict, list))
            and str(key).lower() in html_keys
            and self._looks_like_html(value)
        ]
        return "\n".join(value for value in html_values if value).strip()

    def _is_internal_api_path(self, value: str) -> bool:
        text = str(value or "").strip()
        if text.startswith("/api/") or text.startswith("api/"):
            return True
        parsed = urlparse(text)
        return parsed.path.startswith("/api/")

    def _looks_like_image_url(self, value: str, *, require_image_hint: bool = False) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        if _SAFE_IMAGE_DATA_PATTERN.match(text):
            return True
        if self.allow_svg_data_images and _SVG_IMAGE_DATA_PATTERN.match(text):
            return True
        parsed = urlparse(text)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return False
        if require_image_hint:
            path = parsed.path or text.split("?", 1)[0].split("#", 1)[0]
            return path.lower().endswith(_IMAGE_URL_EXTENSIONS)
        return bool(parsed.scheme in {"http", "https"} or text.startswith(("/", "./", "../")))

    def _is_endpoint_directory(self, payload: Mapping[str, Any]) -> bool:
        endpoints = payload.get("endpoints")
        if isinstance(endpoints, dict):
            values = [value for value in endpoints.values() if isinstance(value, str)]
            return bool(values) and all(self._is_internal_api_path(value) for value in values)
        if isinstance(endpoints, list):
            values = [value for value in endpoints if isinstance(value, str)]
            return bool(values) and all(self._is_internal_api_path(value) for value in values)
        return False

    def _endpoint_directory_model(
        self,
        action: Mapping[str, Any],
        payload: Mapping[str, Any],
        status_code: int,
    ) -> dict[str, Any]:
        raw_endpoints = payload.get("endpoints")
        if isinstance(raw_endpoints, dict):
            endpoint_count = len(raw_endpoints)
        elif isinstance(raw_endpoints, list):
            endpoint_count = len([value for value in raw_endpoints if isinstance(value, str)])
        else:
            endpoint_count = 0
        return {
            "kind": "detail",
            "title": self._action_title(action),
            "status": self._status_label(status_code, payload),
            "fields": [
                {
                    "key": "service",
                    "label": "Service",
                    "value": str(payload.get("message") or self._action_title(action)).strip(),
                },
                {
                    "key": "endpoint_count",
                    "label": "Registered endpoints",
                    "value": f"{endpoint_count} items",
                },
                {
                    "key": "operator_hint",
                    "label": "Operator hint",
                    "value": "Internal API paths stay in the debug drawer; navigate through published actions instead.",
                },
            ],
            "nested": [],
        }

    def _int_from_path(
        self,
        action: Mapping[str, Any],
        envelope: Mapping[str, Any] | None,
        key: str,
        *,
        default: int,
    ) -> int:
        if not envelope:
            return default
        path = self._view_model_path(action, key)
        value = self._value_at_path(envelope, path) if path else None
        try:
            return int(value) if not _is_blank(value) else default
        except (TypeError, ValueError):
            return default

    def _int_from_mapping_path(self, mapping: Mapping[str, Any] | None, path: str) -> int | None:
        if not mapping or not path:
            return None
        value = self._value_at_path(mapping, path)
        try:
            return int(value) if not _is_blank(value) else None
        except (TypeError, ValueError):
            return None

    def _first_positive_int(self, *values: int | None) -> int:
        for value in values:
            if isinstance(value, int) and value > 0:
                return value
        return 1

    def _first_int(self, *values: int | None) -> int:
        for value in values:
            if isinstance(value, int):
                return value
        return 0


class _PlainTextHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self._chunks.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"br", "p", "div", "li", "section", "article", "tr"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "section", "article", "tr"}:
            self._chunks.append("\n")

    def text(self) -> str:
        joined = " ".join(self._chunks)
        joined = re.sub(r"\s*\n\s*", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()


def _apply_runtime_action_patch(
    action: Mapping[str, Any],
    patch: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    updated = copy.deepcopy(dict(action))
    changed = False
    for key, value in patch.items():
        if key == "view_model":
            current_view_model = dict(updated.get("view_model") or {})
            merged_view_model = {**current_view_model, **dict(value or {})}
            if merged_view_model != current_view_model:
                changed = True
            updated["view_model"] = merged_view_model
            continue
        if updated.get(key) != value:
            changed = True
        updated[key] = copy.deepcopy(value)
    return updated, changed


def _deep_merge_runtime_patch(target: dict[str, Any], patch: Mapping[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_merge_runtime_patch(target[key], value)
            continue
        target[key] = copy.deepcopy(value)


def _humanize_token(token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return ""
    uppercase_tokens = {"api", "id", "ids", "url", "http", "https", "ip", "ui", "sdk"}
    if normalized.lower() in uppercase_tokens:
        return normalized.upper()
    return normalized.replace("-", " ").title()


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _is_sensitive_param_key(key: str) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_PARAM_TOKENS)


def _audit_confirmation_payload(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    if not evidence:
        return {"confirmed": False}
    return {
        "confirmed": bool(evidence.get("confirmed", True)),
        "confirmed_at": str(evidence.get("confirmed_at") or ""),
        "message": str(evidence.get("message") or ""),
    }


def _audit_reauth_payload(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    if not evidence:
        return {"verified": False}
    return {
        "verified": bool(evidence.get("verified", False)),
        "verified_at": str(evidence.get("verified_at") or ""),
        "method": str(evidence.get("method") or "password"),
        "challenge_id": str(evidence.get("challenge_id") or ""),
    }


def _verified_reauth_evidence(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(evidence or {})
    payload["verified"] = True
    payload.setdefault("verified_at", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    payload.setdefault("method", "password")
    return payload


def _result_status_code(result: Mapping[str, Any] | None) -> int:
    if not isinstance(result, Mapping):
        return 200
    response = result.get("response")
    if not isinstance(response, Mapping):
        return 200
    try:
        return int(response.get("status_code", 200))
    except (TypeError, ValueError):
        return 200
