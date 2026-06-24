# Runtime Shell Sync Boundary

This directory documents the repository's internal one-way sync boundary for runtime shell reference assets.

## Directory Convention

- the manifest in this directory is the allowlist of upstream source files and local targets
- the repository sync script executes the transfer and refuses to write outside the allowed target prefixes
- machine-specific paths belong in the local config file, not in the committed manifest

## What May Sync

Only runtime shell reference assets may move through this mechanism:

- `packages/agomtui-runtime/reference/tui_workbench.reference.html`
- `packages/agomtui-runtime/reference/static/css/tui-workbench.css`
- `packages/agomtui-runtime/reference/static/js/tui-workbench.js`

## What May Not Sync

Do not pull these areas through this mechanism:

- `packages/agomtui-core/`
- `packages/agomtui-compiler/`
- `adapters/`
- `demo/`
- `docs/`

Those areas are the independent AgomTUI product boundary.

## Source Resolution

The sync executor resolves source material in this order:

1. configured local working tree
2. configured git ref from a readable repository
3. optional remote fetch cache

That means local uncommitted runtime-shell changes can be reviewed before falling back to a git snapshot or remote cache.

## Usage

Use the sync script from the repository root.

Recommended flow:

1. run a dry check
2. create a local config from the example if needed
3. apply the sync
4. compare against the configured baseline when reviewing larger updates
5. list the resolved source configuration when debugging local setup

## Review Rule

Every sync is expected to be:

1. run through the manifest
2. reviewed as a normal diff
3. followed by demo and test verification

