from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "sync" / "agomtradepro" / "runtime-shell.manifest.json"
DEFAULT_CONFIG = REPO_ROOT / "sync" / "agomtradepro" / "runtime-shell.config.json"


class SyncError(RuntimeError):
    pass


@dataclass
class SyncEntry:
    entry_id: str
    description: str
    source_relpath: str
    target: Path
    transform: str


@dataclass
class RawSource:
    text: str
    mode: str
    identifier: str


@dataclass
class SourceConfig:
    local_root: Path | None
    git_repo_root: Path | None
    source_ref: str | None
    baseline_ref: str | None
    remote_url: str | None
    remote_fetch_ref: str | None
    cache_dir: Path | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize allowed AgomTradePro runtime shell assets into AgomTUI. "
            "Resolution order: local worktree first, then git ref fallback, then optional remote fetch cache."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="Path to the sync manifest JSON file.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to the optional local sync config JSON file.",
    )
    parser.add_argument(
        "--source-root",
        help="Path to the local agomTradePro working tree. Defaults to AGOMTRADEPRO_ROOT or the manifest hint.",
    )
    parser.add_argument(
        "--git-repo-root",
        help="Path to an agomTradePro git repository used for git-ref fallback. Defaults to the local source root or the manifest hint.",
    )
    parser.add_argument(
        "--source-ref",
        help="Git ref used when the local working tree source file is unavailable. Defaults to AGOMTRADEPRO_SOURCE_REF or the manifest fallback ref.",
    )
    parser.add_argument(
        "--baseline-ref",
        help="Git ref used for baseline comparison. Defaults to AGOMTRADEPRO_BASELINE_REF or the manifest baseline ref.",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Compare the preferred source material against the configured baseline ref after transforms.",
    )
    parser.add_argument(
        "--remote-url",
        help="Optional git remote URL used when neither the local working tree nor a local git repo is available.",
    )
    parser.add_argument(
        "--remote-fetch-ref",
        help="Ref to fetch from the remote URL when remote fallback is needed. Defaults to AGOMTRADEPRO_REMOTE_FETCH_REF or the manifest value.",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory for the optional remote fetch cache. Defaults to the manifest cache dir.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write synchronized files into the current repository.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when any allowed target differs from the transformed preferred source.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the resolved source configuration and sync mappings, then exit.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyncError(f"Manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SyncError(f"Manifest is not valid JSON: {path}: {exc}") from exc


def load_optional_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SyncError(f"Config is not valid JSON: {path}: {exc}") from exc


def env_or_value(*values: str | None) -> str | None:
    for value in values:
        if value is None:
            continue
        stripped = str(value).strip()
        if stripped:
            return stripped
    return None


def resolve_existing_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    if path.exists():
        return path.resolve()
    return None


def resolve_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path.resolve()


def ensure_within_repo(path: Path) -> None:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise SyncError(f"Refusing to write outside repository root: {path}") from exc


def load_entries(manifest: dict[str, Any]) -> list[SyncEntry]:
    allowed_prefixes = manifest.get("boundary", {}).get("allowed_target_prefixes", [])
    entries: list[SyncEntry] = []
    for raw in manifest.get("entries", []):
        target = (REPO_ROOT / raw["target"]).resolve()
        ensure_within_repo(target)
        target_relative = target.relative_to(REPO_ROOT.resolve()).as_posix()
        if not any(
            target_relative.startswith(prefix.rstrip("/") + "/") or target_relative == prefix.rstrip("/")
            for prefix in allowed_prefixes
        ):
            raise SyncError(f"Target is outside allowed sync prefixes: {target_relative}")
        entries.append(
            SyncEntry(
                entry_id=raw["id"],
                description=raw.get("description", ""),
                source_relpath=str(raw["source"]).replace("\\", "/"),
                target=target,
                transform=raw.get("transform", "copy"),
            )
        )
    if not entries:
        raise SyncError("Manifest has no sync entries.")
    return entries


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SyncError(f"Expected exactly one match for {label}, found {count}.")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, repl: str, label: str) -> str:
    replaced, count = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise SyncError(f"Expected exactly one regex match for {label}, found {count}.")
    return replaced


def transform_django_template_to_reference_html(text: str) -> str:
    text = replace_regex_once(text, r"^\s*\{% load static %\}\r?\n", "", "remove Django static loader")
    text = replace_once(text, "<title>TUI Workbench - AgomTradePro</title>", "<title>AgomTUI Workbench</title>", "reference title")
    text = replace_regex_once(
        text,
        r"""<link rel="stylesheet" href="\{% static 'css/tui-workbench\.css' %\}(?:\?[^"]*)?">""",
        '<link rel="stylesheet" href="./static/css/tui-workbench.css">',
        "reference stylesheet path",
    )
    text = replace_once(
        text,
        'aria-label="AgomTradePro TUI workbench"',
        'aria-label="AgomTUI workbench"',
        "reference aria label",
    )
    text = replace_once(
        text,
        '<a class="tui-brand" href="/tui/">AgomTradePro TUI</a>',
        '<a class="tui-brand" href="/tui/">AgomTUI</a>',
        "reference brand label",
    )
    text = replace_once(
        text,
        "<span>用户: {{ request.user.username }}</span>",
        "<span>用户: operator</span>",
        "reference user label",
    )
    text = replace_regex_once(
        text,
        r"""<div class="tui-system-location">\s*<label for="tui-location-input">位置:</label>\s*<input\s+id="tui-location-input"\s+data-current-location\s+type="text"\s+spellcheck="false"\s+autocomplete="off"\s+value="screen:boot"\s+title="输入 screen:<screen_key> 后按 Enter 跳转"\s+aria-label="输入 TUI screen 地址后跳转"\s*>\s*</div>""",
        """<div class="tui-system-location">\n                <span>位置:</span>\n                <code data-current-location title="当前 metadata 地址，可用于输入和定位">screen:boot</code>\n            </div>""",
        "reference location block",
    )
    text = replace_regex_once(
        text,
        r"""<script src="\{% static 'js/tui-workbench\.js' %\}(?:\?[^"]*)?"></script>""",
        '<script src="./static/js/tui-workbench.js"></script>',
        "reference script path",
    )
    return ensure_trailing_newline(text)


def transform_agomtradepro_runtime_js_to_reference(text: str) -> str:
    helper_block = """    const runtimeConfig = window.__AGOMTUI_RUNTIME__ || {};
    const apiBase = String(runtimeConfig.apiBase || "/api/tui").replace(/\\/+$/, "");

    function catalogUrl() {
        return `${apiBase}/catalog/`;
    }

    function screenUrl(screenKey) {
        return `${apiBase}/screens/${encodeURIComponent(screenKey)}/`;
    }

    function actionRunUrl(actionKey) {
        return `${apiBase}/actions/${encodeURIComponent(actionKey)}/run/`;
    }

"""
    if "window.__AGOMTUI_RUNTIME__" not in text:
        text = replace_once(
            text,
            "    function escapeHtml(value) {",
            helper_block + "    function escapeHtml(value) {",
            "runtime config helper insertion",
        )
    text = replace_once(
        text,
        'fetchJson(`/api/tui/actions/${encodeURIComponent(panel.action_key)}/run/`, {',
        "fetchJson(actionRunUrl(panel.action_key), {",
        "dashboard panel action endpoint",
    )
    text = replace_once(
        text,
        'fetchJson(`/api/tui/screens/${encodeURIComponent(screenKey)}/`);',
        "fetchJson(screenUrl(screenKey));",
        "screen endpoint",
    )
    text = replace_once(
        text,
        'fetchJson(`/api/tui/actions/${encodeURIComponent(actualActionKey)}/run/`, {',
        "fetchJson(actionRunUrl(actualActionKey), {",
        "action endpoint",
    )
    text = replace_once(
        text,
        'fetchJson("/api/tui/catalog/");',
        "fetchJson(catalogUrl());",
        "catalog endpoint",
    )
    return ensure_trailing_newline(text)


def ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


TRANSFORMS: dict[str, Callable[[str], str]] = {
    "copy": ensure_trailing_newline,
    "django_template_to_reference_html": transform_django_template_to_reference_html,
    "agomtradepro_runtime_js_to_reference": transform_agomtradepro_runtime_js_to_reference,
}


def digest_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()[:12]


def git_safe_path(path: Path) -> str:
    return path.resolve().as_posix()


def run_git(repo_root: Path, args: list[str]) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={git_safe_path(repo_root)}",
        "-C",
        str(repo_root),
        *args,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or f"git exited {result.returncode}"
        raise SyncError(f"Git command failed in {repo_root}: {' '.join(args)}: {message}")
    return result.stdout


def git_path_exists(repo_root: Path, ref: str, relpath: str) -> bool:
    command = [
        "git",
        "-c",
        f"safe.directory={git_safe_path(repo_root)}",
        "-C",
        str(repo_root),
        "cat-file",
        "-e",
        f"{ref}:{relpath}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    return result.returncode == 0


def git_show_text(repo_root: Path, ref: str, relpath: str) -> RawSource:
    text = run_git(repo_root, ["show", f"{ref}:{relpath}"])
    return RawSource(
        text=text,
        mode="git-ref",
        identifier=f"{repo_root}:{ref}:{relpath}",
    )


def ensure_remote_cache(cache_dir: Path, remote_url: str) -> Path:
    git_dir = cache_dir / ".git"
    if git_dir.exists():
        run_git(cache_dir, ["remote", "set-url", "origin", remote_url])
        return cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    run_git(cache_dir, ["init"])
    run_git(cache_dir, ["remote", "add", "origin", remote_url])
    return cache_dir


def remote_fetch_text(cache_dir: Path, remote_url: str, fetch_ref: str, relpath: str) -> RawSource:
    repo_root = ensure_remote_cache(cache_dir, remote_url)
    run_git(repo_root, ["fetch", "--depth", "1", "origin", fetch_ref])
    text = run_git(repo_root, ["show", f"FETCH_HEAD:{relpath}"])
    return RawSource(
        text=text,
        mode="remote-fetch",
        identifier=f"{remote_url}@{fetch_ref}:{relpath}",
    )


def resolve_source_config(
    manifest: dict[str, Any],
    local_config: dict[str, Any],
    args: argparse.Namespace,
) -> SourceConfig:
    git_source = manifest.get("git_source") or {}
    config_source = local_config.get("source") or {}
    local_root = resolve_existing_path(
        env_or_value(
            args.source_root,
            os.environ.get("AGOMTRADEPRO_ROOT"),
            config_source.get("local_root"),
        )
    )
    git_repo_root = resolve_existing_path(
        env_or_value(
            args.git_repo_root,
            os.environ.get("AGOMTRADEPRO_GIT_ROOT"),
            local_root.as_posix() if local_root else None,
            config_source.get("git_repo_root"),
        )
    )
    source_ref = env_or_value(
        args.source_ref,
        os.environ.get("AGOMTRADEPRO_SOURCE_REF"),
        config_source.get("source_ref"),
        git_source.get("fallback_ref"),
        git_source.get("baseline_ref"),
        "HEAD",
    )
    baseline_ref = env_or_value(
        args.baseline_ref,
        os.environ.get("AGOMTRADEPRO_BASELINE_REF"),
        config_source.get("baseline_ref"),
        git_source.get("baseline_ref"),
        "HEAD",
    )
    remote_url = env_or_value(
        args.remote_url,
        os.environ.get("AGOMTRADEPRO_REMOTE_URL"),
        config_source.get("remote_url"),
        git_source.get("remote_url"),
    )
    remote_fetch_ref = env_or_value(
        args.remote_fetch_ref,
        os.environ.get("AGOMTRADEPRO_REMOTE_FETCH_REF"),
        config_source.get("remote_fetch_ref"),
        git_source.get("remote_fetch_ref"),
        source_ref,
        baseline_ref,
        "HEAD",
    )
    cache_dir = resolve_path(
        env_or_value(
            args.cache_dir,
            os.environ.get("AGOMTRADEPRO_CACHE_DIR"),
            config_source.get("cache_dir"),
            git_source.get("cache_dir"),
        )
    )
    return SourceConfig(
        local_root=local_root,
        git_repo_root=git_repo_root,
        source_ref=source_ref,
        baseline_ref=baseline_ref,
        remote_url=remote_url,
        remote_fetch_ref=remote_fetch_ref,
        cache_dir=cache_dir,
    )


def preferred_source(entry: SyncEntry, config: SourceConfig) -> RawSource:
    if config.local_root is not None:
        local_path = (config.local_root / entry.source_relpath).resolve()
        if local_path.exists():
            return RawSource(
                text=local_path.read_text(encoding="utf-8"),
                mode="local-worktree",
                identifier=str(local_path),
            )
    if config.git_repo_root is not None and config.source_ref and git_path_exists(
        config.git_repo_root, config.source_ref, entry.source_relpath
    ):
        return git_show_text(config.git_repo_root, config.source_ref, entry.source_relpath)
    if config.remote_url and config.remote_fetch_ref and config.cache_dir:
        return remote_fetch_text(
            config.cache_dir,
            config.remote_url,
            config.remote_fetch_ref,
            entry.source_relpath,
        )
    raise SyncError(
        "Could not resolve preferred source. Checked local worktree, git-ref fallback, and remote fallback."
    )


def baseline_source(entry: SyncEntry, config: SourceConfig) -> RawSource:
    if not config.baseline_ref:
        raise SyncError("Baseline comparison requested but no baseline ref is configured.")
    if config.git_repo_root is not None and git_path_exists(
        config.git_repo_root, config.baseline_ref, entry.source_relpath
    ):
        return git_show_text(config.git_repo_root, config.baseline_ref, entry.source_relpath)
    if config.remote_url and config.cache_dir:
        return remote_fetch_text(
            config.cache_dir,
            config.remote_url,
            config.baseline_ref,
            entry.source_relpath,
        )
    raise SyncError(
        f"Could not resolve baseline source for ref {config.baseline_ref!r}. "
        "Provide a readable git repo root or a remote URL + cache dir."
    )


def render_entry(entry: SyncEntry) -> str:
    return f"{entry.entry_id}: {entry.source_relpath} -> {entry.target.relative_to(REPO_ROOT).as_posix()} [{entry.transform}]"


def render_source_config(config: SourceConfig, *, config_path: Path) -> list[str]:
    return [
        f"Config file: {config_path if config_path.exists() else '(not found)'}",
        f"Local worktree: {config.local_root or '(not found)'}",
        f"Git repo root: {config.git_repo_root or '(not found)'}",
        f"Fallback source ref: {config.source_ref or '(unset)'}",
        f"Baseline ref: {config.baseline_ref or '(unset)'}",
        f"Remote URL: {config.remote_url or '(unset)'}",
        f"Remote fetch ref: {config.remote_fetch_ref or '(unset)'}",
        f"Remote cache dir: {config.cache_dir or '(unset)'}",
    ]


def transformed_text(entry: SyncEntry, raw_text: str) -> str:
    transform = TRANSFORMS.get(entry.transform)
    if transform is None:
        raise SyncError(f"Unknown transform: {entry.transform}")
    return transform(raw_text)


def sync_entry(entry: SyncEntry, config: SourceConfig, apply: bool) -> tuple[str, str]:
    source = preferred_source(entry, config)
    expected_text = transformed_text(entry, source.text)
    current_text = entry.target.read_text(encoding="utf-8") if entry.target.exists() else ""
    if current_text == expected_text:
        return f"UNCHANGED [{source.mode}]", digest_text(expected_text)
    if apply:
        entry.target.parent.mkdir(parents=True, exist_ok=True)
        with entry.target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(expected_text)
        return f"UPDATED [{source.mode}]", digest_text(expected_text)
    return f"DIFF [{source.mode}]", digest_text(expected_text)


def compare_entry_to_baseline(entry: SyncEntry, config: SourceConfig) -> tuple[str, str, str]:
    source = preferred_source(entry, config)
    baseline = baseline_source(entry, config)
    source_text = transformed_text(entry, source.text)
    baseline_text = transformed_text(entry, baseline.text)
    if source_text == baseline_text:
        return "BASELINE_SAME", digest_text(source_text), baseline.identifier
    return "BASELINE_DIFF", digest_text(source_text), baseline.identifier


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    manifest = load_manifest(manifest_path)
    local_config = load_optional_config(config_path)
    config = resolve_source_config(manifest, local_config, args)
    entries = load_entries(manifest)

    if args.list:
        for line in render_source_config(config, config_path=config_path):
            print(line)
        print("")
        for entry in entries:
            print(render_entry(entry))
        return 0

    changed = False
    for entry in entries:
        status, digest = sync_entry(entry, config, apply=args.apply)
        changed = changed or status.startswith("DIFF") or status.startswith("UPDATED")
        print(f"{status:18} {entry.target.relative_to(REPO_ROOT).as_posix()}  sha={digest}")

    if args.compare_baseline:
        print("")
        for entry in entries:
            status, digest, baseline_id = compare_entry_to_baseline(entry, config)
            print(
                f"{status:18} {entry.target.relative_to(REPO_ROOT).as_posix()}  "
                f"sha={digest}  baseline={baseline_id}"
            )

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
