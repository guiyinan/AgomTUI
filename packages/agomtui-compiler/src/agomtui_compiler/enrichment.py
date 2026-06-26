from __future__ import annotations

import copy
from typing import Any

from .collector import EvidenceBundle

PAGE_KEYS = ("page", "pageNum", "page_num", "pageNo", "page_no")
PAGE_SIZE_KEYS = ("page_size", "pageSize", "limit", "size")
OFFSET_KEYS = ("offset", "start")
LIMIT_KEYS = ("limit", "page_size", "pageSize", "size")
CURSOR_KEYS = ("cursor", "next_cursor", "nextCursor")
ROW_KEYS = ("items", "results", "records", "rows", "data", "entries")
TOTAL_KEYS = ("total", "count", "total_count", "totalRows", "total_rows")


def enrich_metadata_from_evidence(payload: dict[str, Any], evidence: EvidenceBundle) -> dict[str, Any]:
    """Fill safe, schema-owned runtime hints from deterministic endpoint evidence."""

    enriched = copy.deepcopy(payload)
    endpoint_evidence = _openapi_evidence_by_endpoint(evidence)
    for action in enriched.get("actions") or []:
        if not isinstance(action, dict):
            continue
        endpoint = str(action.get("endpoint") or "")
        method = str(action.get("method") or "GET").upper()
        evidence_payload = endpoint_evidence.get((endpoint, method)) or endpoint_evidence.get((endpoint, "GET"))
        if not evidence_payload:
            continue
        _enrich_action(action, evidence_payload)
    return enriched


def _openapi_evidence_by_endpoint(evidence: EvidenceBundle) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for item in evidence.items:
        if item.source_type != "openapi":
            continue
        endpoint = str(item.payload.get("endpoint") or "")
        method = str(item.payload.get("method") or "GET").upper()
        if endpoint:
            indexed[(endpoint, method)] = item.payload
    return indexed


def _enrich_action(action: dict[str, Any], evidence_payload: dict[str, Any]) -> None:
    response = evidence_payload.get("response") if isinstance(evidence_payload.get("response"), dict) else {}
    fields = [field for field in response.get("fields") or [] if isinstance(field, dict)]
    rows_path = _array_field_path(fields)
    total_path = _field_key(fields, TOTAL_KEYS, value_types={"integer", "float", "decimal"})
    page_path = _field_key(fields, PAGE_KEYS, value_types={"integer"})
    page_size_path = _field_key(fields, PAGE_SIZE_KEYS, value_types={"integer"})

    pagination = _infer_pagination(evidence_payload)
    if pagination and "pagination" not in action:
        action["pagination"] = pagination

    has_list_contract = bool(rows_path and (pagination or total_path)) or response.get("schema_type") == "array"
    if not has_list_contract:
        return

    view_model = action.setdefault("view_model", {})
    if not isinstance(view_model, dict):
        return

    if str(action.get("view_type") or "auto") in {"auto", "detail", "status", "datagrid"}:
        action["view_type"] = "datagrid"
        view_model.setdefault("kind", "datagrid")

    if rows_path:
        view_model.setdefault("rows_path", rows_path)
    if total_path:
        view_model.setdefault("total_path", total_path)
    if page_path:
        view_model.setdefault("page_path", page_path)
    if page_size_path:
        view_model.setdefault("page_size_path", page_size_path)


def _infer_pagination(evidence_payload: dict[str, Any]) -> dict[str, str] | None:
    params = [
        param
        for param in evidence_payload.get("parameters") or []
        if isinstance(param, dict) and str(param.get("location") or "") == "query"
    ]
    keys = [str(param.get("key") or "") for param in params]
    offset_param = _candidate_key(keys, OFFSET_KEYS)
    limit_param = _candidate_key(keys, LIMIT_KEYS)
    if offset_param and limit_param:
        return {"mode": "offset", "offset_param": offset_param, "limit_param": limit_param}

    page_param = _candidate_key(keys, PAGE_KEYS)
    page_size_param = _candidate_key(keys, PAGE_SIZE_KEYS)
    if page_param and page_size_param:
        return {"mode": "page", "page_param": page_param, "page_size_param": page_size_param}

    cursor_param = _candidate_key(keys, CURSOR_KEYS)
    if cursor_param:
        return {"mode": "cursor", "cursor_param": cursor_param}
    return None


def _array_field_path(fields: list[dict[str, Any]]) -> str:
    array_fields = [
        str(field.get("key") or "")
        for field in fields
        if str(field.get("raw_type") or "") == "array" or str(field.get("value_type") or "") == "list"
    ]
    return _candidate_key(array_fields, ROW_KEYS) or (array_fields[0] if array_fields else "")


def _field_key(fields: list[dict[str, Any]], candidates: tuple[str, ...], *, value_types: set[str]) -> str:
    keys = [
        str(field.get("key") or "")
        for field in fields
        if str(field.get("value_type") or "") in value_types
    ]
    return _candidate_key(keys, candidates)


def _candidate_key(keys: list[str], candidates: tuple[str, ...]) -> str:
    normalized = {_normalize_key(key): key for key in keys if key}
    for candidate in candidates:
        match = normalized.get(_normalize_key(candidate))
        if match:
            return match
    return ""


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())
