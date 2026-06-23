# agomtui-runtime reference

This folder contains the first extracted runtime shell from AgomTradePro.

## What it is

- the current HTML/CSS/JS workbench shell
- runtime three-theme switching (`A / B / C`)
- keyboard-driven TUI layout and panel chrome
- generic action groups, task cards, and confirmation flow
- generic datagrid / detail / message / dashboard renderers
- row-fill, inspector, pager, filter, modal, and raw-debug drawer behaviors
- host-configurable API base via `window.__AGOMTUI_RUNTIME__.apiBase`

## What is still host-specific

- assumes the host returns the AgomTUI screen/action response contract
- still carries Agom-oriented copy and screen semantics in the reference assets
- still reflects the current host payload conventions that came from AgomTradePro

Treat this as the product baseline, not the final host-agnostic runtime.

## What is intentionally not extracted here

This package does **not** carry over:

- AgomTradePro business screen definitions
- published business metadata graphs
- Django route wiring, auth, session, or ORM registry logic
- classic page replacement strategy for a specific host app
- product-specific workflow ordering or business vocabulary rules

The extraction target is the **runtime framework**, not the full AgomTradePro TUI product surface.

## Upstream sync

The reference shell in this package is maintained through the `agomTradePro -> AgomTUI` one-way sync manifest:

- manifest: `sync/agomtradepro/runtime-shell.manifest.json`
- executor: `scripts/sync_from_agomtradepro.py`

Only the reference HTML/CSS/JS assets under `packages/agomtui-runtime/reference/` should move through that sync path.
