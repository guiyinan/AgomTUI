# AgomTradePro Sync Boundary

This directory is the single source of truth for **one-way sync** from `agomTradePro` into `AgomTUI`.

## Directory convention

- `sync/agomtradepro/runtime-shell.manifest.json`
  - allowlist of upstream source files and local targets
  - defines which transforms are permitted
- `scripts/sync_from_agomtradepro.py`
  - executes the sync
  - refuses to write outside the allowed target prefixes

## What may sync

Only runtime shell reference assets may sync from `agomTradePro`:

- `packages/agomtui-runtime/reference/tui_workbench.reference.html`
- `packages/agomtui-runtime/reference/static/css/tui-workbench.css`
- `packages/agomtui-runtime/reference/static/js/tui-workbench.js`

## What may not sync

Do not pull these areas across from `agomTradePro` through this mechanism:

- `packages/agomtui-core/`
- `packages/agomtui-compiler/`
- `adapters/`
- `demo/`
- `docs/`

Those areas are the independent product boundary for `AgomTUI`.

## Configuration

Machine-specific paths do not belong in the committed manifest.

Use a local config file instead:

- template: `sync/agomtradepro/runtime-shell.config.example.json`
- local override: `sync/agomtradepro/runtime-shell.config.json`

The local override file is intentionally gitignored.

## Source resolution

The sync executor resolves source material in this order:

1. local `agomTradePro` working tree
2. git ref from a readable `agomTradePro` repository
3. optional remote fetch cache

That means:

- if you have local uncommitted TUI changes, sync reads those first
- if you do not have the local file, it falls back to a git snapshot
- if you do not have a local repo path, you can provide a remote URL and fetch ref

## Usage

Dry run:

```powershell
python scripts\sync_from_agomtradepro.py --check
```

Create a local config first:

```powershell
Copy-Item sync\agomtradepro\runtime-shell.config.example.json sync\agomtradepro\runtime-shell.config.json
```

Apply:

```powershell
python scripts\sync_from_agomtradepro.py --apply
```

Override the upstream path when needed:

```powershell
python scripts\sync_from_agomtradepro.py --source-root D:\githv\agomTradePro --apply
```

Compare the preferred source against a baseline ref:

```powershell
python scripts\sync_from_agomtradepro.py --compare-baseline --baseline-ref HEAD
```

Use a remote fallback when no local checkout is available:

```powershell
python scripts\sync_from_agomtradepro.py `
  --remote-url https://github.com/your-org/agomTradePro.git `
  --remote-fetch-ref dev/next-development `
  --baseline-ref dev/next-development `
  --compare-baseline
```

List the resolved source configuration:

```powershell
python scripts\sync_from_agomtradepro.py --list
```

## Review rule

Every sync is expected to be:

1. run through the manifest
2. reviewed as a normal diff
3. followed by demo and test verification
