# agomtui-runtime reference

This folder contains the first extracted runtime shell from AgomTradePro.

## What it is

- the current HTML/CSS/JS workbench shell
- runtime three-theme switching (`A / B / C`)
- keyboard-driven TUI layout and panel chrome

## What is still host-specific

- fetches `/api/tui/*` endpoints directly
- assumes the host returns Agom-style screen and action payloads
- still contains Agom-oriented inspector/help vocabulary

Treat this as the product baseline, not the final host-agnostic runtime.

## Upstream sync

The reference shell in this package is maintained through the `agomTradePro -> AgomTUI` one-way sync manifest:

- manifest: `sync/agomtradepro/runtime-shell.manifest.json`
- executor: `scripts/sync_from_agomtradepro.py`

Only the reference HTML/CSS/JS assets under `packages/agomtui-runtime/reference/` should move through that sync path.
