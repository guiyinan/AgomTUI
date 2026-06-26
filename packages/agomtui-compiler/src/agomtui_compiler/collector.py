from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


KNOWN_OPENAPI_METHODS = ("get", "post", "put", "patch", "delete")
DJANGO_FIELD_VALUE_TYPE_MAP = {
    "AutoField": "integer",
    "BigAutoField": "integer",
    "BigIntegerField": "integer",
    "BooleanField": "boolean",
    "CharField": "string",
    "DateField": "date",
    "DateTimeField": "datetime",
    "DecimalField": "decimal",
    "DurationField": "string",
    "EmailField": "string",
    "FloatField": "float",
    "IntegerField": "integer",
    "JSONField": "object",
    "PositiveBigIntegerField": "integer",
    "PositiveIntegerField": "integer",
    "PositiveSmallIntegerField": "integer",
    "SmallIntegerField": "integer",
    "TextField": "string",
    "TimeField": "string",
    "UUIDField": "string",
}


@dataclass(frozen=True)
class CollectionContext:
    """Context visible to compile-time evidence collectors."""

    project_root: Path
    host_kind: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceItem:
    """One normalized piece of compile-time evidence."""

    source_type: str
    source_ref: str
    summary: str
    payload: dict[str, Any]


@dataclass
class EvidenceBundle:
    """Collected evidence grouped for downstream synthesis."""

    items: list[EvidenceItem] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, item: EvidenceItem) -> None:
        self.items.append(item)
        self.counts[item.source_type] = self.counts.get(item.source_type, 0) + 1

    def extend(self, items: list[EvidenceItem]) -> None:
        for item in items:
            self.add(item)

    def grouped_payload(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self.items:
            grouped.setdefault(item.source_type, []).append(
                {
                    "source_ref": item.source_ref,
                    "summary": item.summary,
                    "payload": item.payload,
                }
            )
        return grouped


class BaseCollector(Protocol):
    """Collector contract for one host-specific evidence source."""

    name: str

    def collect(self, context: CollectionContext) -> list[EvidenceItem]:
        """Collect normalized evidence from one source."""


class NullCollector:
    """No-op collector used by the first compiler skeleton."""

    name = "null"

    def collect(self, context: CollectionContext) -> list[EvidenceItem]:
        del context
        return []


class JsonEvidenceCollector:
    """Read already-normalized evidence items from one JSON file."""

    name = "json-evidence"

    def __init__(self, path: Path) -> None:
        self.path = path

    def collect(self, context: CollectionContext) -> list[EvidenceItem]:
        del context
        payload = _read_json_object(self.path)
        items = []
        for item in payload.get("items", []):
            items.append(
                EvidenceItem(
                    source_type=str(item["source_type"]),
                    source_ref=str(item["source_ref"]),
                    summary=str(item["summary"]),
                    payload=dict(item.get("payload") or {}),
                )
            )
        return items


class OpenApiSpecCollector:
    """Collect endpoint evidence directly from one OpenAPI JSON specification."""

    name = "openapi-spec"

    def __init__(self, path: Path) -> None:
        self.path = path

    def collect(self, context: CollectionContext) -> list[EvidenceItem]:
        del context
        payload = _read_json_object(self.path)
        items: list[EvidenceItem] = []
        for endpoint, path_item in sorted((payload.get("paths") or {}).items()):
            if not isinstance(path_item, dict):
                continue
            shared_parameters = path_item.get("parameters") or []
            for method in KNOWN_OPENAPI_METHODS:
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue
                operation_parameters = operation.get("parameters") or []
                source_ref = f"{endpoint}#{method.upper()}"
                summary = str(operation.get("summary") or operation.get("description") or f"{method.upper()} {endpoint}")
                items.append(
                    EvidenceItem(
                        source_type="openapi",
                        source_ref=source_ref,
                        summary=summary,
                        payload={
                            "endpoint": endpoint,
                            "method": method.upper(),
                            "operation_id": str(operation.get("operationId") or ""),
                            "tags": [str(tag) for tag in operation.get("tags") or []],
                            "risk": _infer_risk(method.upper()),
                            "parameters": [
                                _normalize_openapi_parameter(parameter)
                                for parameter in [*shared_parameters, *operation_parameters]
                                if isinstance(parameter, dict)
                            ],
                            "request_body_fields": _extract_request_body_fields(operation.get("requestBody") or {}),
                            "response": _extract_response_contract(operation.get("responses") or {}),
                        },
                    )
                )
        return items


class DjangoContractManifestCollector:
    """Collect Django model and aggregate evidence from one exported manifest."""

    name = "django-contract-manifest"

    def __init__(self, path: Path) -> None:
        self.path = path

    def collect(self, context: CollectionContext) -> list[EvidenceItem]:
        del context
        payload = _read_json_object(self.path)
        items: list[EvidenceItem] = []
        for model in payload.get("models", []):
            if not isinstance(model, dict):
                continue
            app_label = str(model.get("app_label") or "")
            model_name = str(model.get("model") or model.get("name") or "")
            if not model_name:
                continue
            source_ref = f"{app_label}.{model_name}" if app_label else model_name
            fields = [_normalize_django_field(field) for field in model.get("fields", []) if isinstance(field, dict)]
            items.append(
                EvidenceItem(
                    source_type="django-model",
                    source_ref=source_ref,
                    summary=f"Django model {source_ref} exposes {len(fields)} declared fields.",
                    payload={
                        "db_table": str(model.get("db_table") or ""),
                        "fields": fields,
                    },
                )
            )
        for aggregate in payload.get("aggregates", []):
            if not isinstance(aggregate, dict):
                continue
            aggregate_key = str(aggregate.get("key") or aggregate.get("name") or aggregate.get("class_name") or "")
            if not aggregate_key:
                continue
            fields = [_normalize_contract_field(field) for field in aggregate.get("fields", []) if isinstance(field, dict)]
            commands = [_normalize_aggregate_command(command) for command in aggregate.get("commands", []) if isinstance(command, dict)]
            items.append(
                EvidenceItem(
                    source_type="ddd-aggregate",
                    source_ref=aggregate_key,
                    summary=f"DDD aggregate {aggregate_key} declares {len(fields)} fields and {len(commands)} commands.",
                    payload={
                        "entity": str(aggregate.get("entity") or ""),
                        "fields": fields,
                        "commands": commands,
                    },
                )
            )
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            items.append(
                EvidenceItem(
                    source_type=str(item["source_type"]),
                    source_ref=str(item["source_ref"]),
                    summary=str(item["summary"]),
                    payload=dict(item.get("payload") or {}),
                )
            )
        return items


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Collector input must be a JSON object: {path}")
    return payload


def _infer_risk(method: str) -> str:
    if method == "GET":
        return "read"
    if method == "DELETE":
        return "unsafe"
    return "write"


def _extract_request_body_fields(request_body: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(request_body, dict):
        return []
    content = request_body.get("content") or {}
    if not isinstance(content, dict):
        return []
    media = content.get("application/json") or next(iter(content.values()), None)
    if not isinstance(media, dict):
        return []
    schema = media.get("schema") or {}
    return _extract_schema_fields(schema)


def _extract_schema_fields(schema: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return []
    required_fields = {str(item) for item in schema.get("required") or []}
    normalized = []
    for key, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        normalized.append(
            {
                "key": str(key),
                "required": key in required_fields,
                "value_type": _map_openapi_schema_value_type(field_schema),
                "raw_type": str(field_schema.get("type") or ""),
                "format": str(field_schema.get("format") or ""),
                "options": [option for option in field_schema.get("enum", [])],
            }
        )
        items_schema = field_schema.get("items") or {}
        if isinstance(items_schema, dict):
            normalized[-1]["item_type"] = _map_openapi_schema_value_type(items_schema)
            item_fields = _extract_schema_fields(items_schema)
            if item_fields:
                normalized[-1]["item_fields"] = item_fields
    return normalized


def _normalize_openapi_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    schema = parameter.get("schema") or {}
    if not isinstance(schema, dict):
        schema = {}
    normalized = {
        "key": str(parameter.get("name") or ""),
        "location": str(parameter.get("in") or ""),
        "required": bool(parameter.get("required", False)),
        "value_type": _map_openapi_schema_value_type(schema),
        "raw_type": str(schema.get("type") or ""),
        "format": str(schema.get("format") or ""),
    }
    if isinstance(schema.get("enum"), list):
        normalized["options"] = [option for option in schema.get("enum", [])]
    return normalized


def _extract_response_contract(responses: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(responses, dict):
        return {"status_codes": []}
    status_codes = [str(code) for code in responses.keys()]
    preferred = responses.get("200") or responses.get("201") or responses.get("default") or {}
    if not isinstance(preferred, dict):
        preferred = {}
    content = preferred.get("content") or {}
    media_types = [str(key) for key in content.keys()] if isinstance(content, dict) else []
    schema = {}
    if isinstance(content, dict):
        first_media = content.get("application/json") or next(iter(content.values()), {})
        if isinstance(first_media, dict) and isinstance(first_media.get("schema"), dict):
            schema = dict(first_media["schema"])
    return {
        "status_codes": status_codes,
        "media_types": media_types,
        "schema_type": str(schema.get("type") or ""),
        "schema_format": str(schema.get("format") or ""),
        "fields": _extract_schema_fields(schema),
        "item_fields": _extract_schema_fields(schema.get("items") or {}) if isinstance(schema.get("items"), dict) else [],
    }


def _map_openapi_schema_value_type(schema: dict[str, Any]) -> str:
    schema_type = str(schema.get("type") or "string")
    schema_format = str(schema.get("format") or "")
    if schema_type == "string" and schema_format == "date":
        return "date"
    if schema_type == "string" and schema_format == "date-time":
        return "datetime"
    if schema_type == "integer":
        return "integer"
    if schema_type == "number":
        return "float"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        return "list"
    if schema_type == "object":
        return "object"
    return "string"


def _normalize_django_field(field: dict[str, Any]) -> dict[str, Any]:
    raw_type = str(field.get("type") or field.get("field_class") or "")
    value_type = str(field.get("value_type") or _map_django_field_value_type(raw_type))
    normalized = {
        "key": str(field.get("name") or field.get("key") or ""),
        "label": str(field.get("label") or field.get("verbose_name") or field.get("name") or field.get("key") or ""),
        "raw_type": raw_type,
        "value_type": value_type,
        "required": not bool(field.get("null", False)) and not bool(field.get("blank", False)),
    }
    if isinstance(field.get("choices"), list):
        normalized["options"] = [choice for choice in field.get("choices", [])]
    if field.get("help_text"):
        normalized["help_text"] = str(field.get("help_text"))
    return normalized


def _normalize_contract_field(field: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "key": str(field.get("name") or field.get("key") or ""),
        "label": str(field.get("label") or field.get("name") or field.get("key") or ""),
        "value_type": str(field.get("value_type") or "string"),
        "required": bool(field.get("required", False)),
    }
    if field.get("description"):
        normalized["description"] = str(field.get("description"))
    if isinstance(field.get("options"), list):
        normalized["options"] = [option for option in field.get("options", [])]
    return normalized


def _normalize_aggregate_command(command: dict[str, Any]) -> dict[str, Any]:
    fields = [_normalize_contract_field(field) for field in command.get("fields", []) if isinstance(field, dict)]
    return {
        "key": str(command.get("key") or command.get("name") or ""),
        "method": str(command.get("method") or "POST").upper(),
        "endpoint": str(command.get("endpoint") or ""),
        "risk": str(command.get("risk") or _infer_risk(str(command.get("method") or "POST").upper())),
        "fields": fields,
    }


def _map_django_field_value_type(raw_type: str) -> str:
    return DJANGO_FIELD_VALUE_TYPE_MAP.get(raw_type, "string")
