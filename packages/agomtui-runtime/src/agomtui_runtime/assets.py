from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RuntimeAssetError(Exception):
    """Base error for runtime asset helper failures."""


class RuntimeAssetNotFound(RuntimeAssetError, FileNotFoundError):
    """Raised when a requested runtime asset is missing or unsafe."""


@dataclass(frozen=True)
class RuntimeAsset:
    body: bytes
    content_type: str


def runtime_reference_dir() -> Path:
    """Return the extracted runtime reference directory for this source checkout."""

    return Path(__file__).resolve().parents[2] / "reference"


def render_runtime_html(
    *,
    title: str,
    home_href: str,
    brand_label: str,
    api_base: str,
    asset_base: str,
    allow_svg_data_images: bool = True,
    runtime_config: dict[str, Any] | None = None,
    reference_dir: Path | None = None,
) -> bytes:
    """Render the reference workbench HTML for a host-owned route.

    Hosts provide their own route URLs and API base. The shell assets stay in
    the extracted reference directory so upstream sync remains one-way.
    """

    root = reference_dir or runtime_reference_dir()
    source = (root / "tui_workbench.reference.html").read_text(encoding="utf-8")
    normalized_asset_base = asset_base.rstrip("/")
    config = {"apiBase": api_base, "allowSvgDataImages": bool(allow_svg_data_images)}
    if runtime_config:
        config.update(runtime_config)
    runtime_config_tag = (
        f"<script>window.__AGOMTUI_RUNTIME__ = {json.dumps(config, ensure_ascii=False)};</script>"
    )
    css_version = int((root / "static" / "css" / "tui-workbench.css").stat().st_mtime)
    js_version = int((root / "static" / "js" / "tui-workbench.js").stat().st_mtime)
    core_js_version = int(
        (root / "static" / "js" / "agomtui-runtime-core.js").stat().st_mtime
    )

    source = source.replace('href="/tui/"', f'href="{html.escape(home_href, quote=True)}"')
    source = source.replace(">AgomTUI<", f">{html.escape(brand_label)}<")
    source = source.replace(
        "./static/css/tui-workbench.css",
        f"{normalized_asset_base}/css/tui-workbench.css?v={css_version}",
    )
    source = source.replace(
        "./static/js/agomtui-runtime-core.js",
        f"{normalized_asset_base}/js/agomtui-runtime-core.js?v={core_js_version}",
    )
    source = source.replace(
        '<script src="./static/js/tui-workbench.js"></script>',
        f'{runtime_config_tag}\n    <script src="{normalized_asset_base}/js/tui-workbench.js?v={js_version}"></script>',
    )
    source = source.replace("<title>AgomTUI Workbench</title>", f"<title>{html.escape(title)}</title>")
    return source.encode("utf-8")


def runtime_asset(relative: str, *, reference_dir: Path | None = None) -> RuntimeAsset:
    """Read one CSS/JS runtime asset by safe path relative to `static/`."""

    normalized = relative.replace("\\", "/").lstrip("/")
    if ".." in Path(normalized).parts:
        raise RuntimeAssetNotFound(relative)

    root = reference_dir or runtime_reference_dir()
    asset_path = root / "static" / normalized
    try:
        resolved_asset = asset_path.resolve(strict=True)
        resolved_static = (root / "static").resolve(strict=True)
    except FileNotFoundError as error:
        raise RuntimeAssetNotFound(relative) from error
    if resolved_static not in resolved_asset.parents or not resolved_asset.is_file():
        raise RuntimeAssetNotFound(relative)

    mime = "text/plain; charset=utf-8"
    if resolved_asset.suffix == ".css":
        mime = "text/css; charset=utf-8"
    elif resolved_asset.suffix == ".js":
        mime = "application/javascript; charset=utf-8"
    return RuntimeAsset(body=resolved_asset.read_bytes(), content_type=mime)
