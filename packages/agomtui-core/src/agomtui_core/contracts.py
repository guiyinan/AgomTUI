from __future__ import annotations

from typing import Any, Protocol


class MetadataRepository(Protocol):
    """Published metadata source for the AgomTUI runtime."""

    def load_published(self, registry_key: str = "default") -> dict[str, Any]:
        """Return one validated published TUI metadata payload."""


class ActionExecutor(Protocol):
    """Execute one host action for the AgomTUI runtime."""

    def execute(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any],
        body: dict[str, Any],
        context: Any | None = None,
    ) -> dict[str, Any]:
        """Return a serializable result payload."""


class AuditSink(Protocol):
    """Append-only audit destination owned by the host adapter."""

    def append(self, record: dict[str, Any]) -> None:
        """Persist one canonical audit record without mutating prior records."""


class CapabilityCollector(Protocol):
    """Compile-time capability source for metadata generation."""

    def collect(self) -> list[dict[str, Any]]:
        """Return normalized capability records."""
