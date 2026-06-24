# agomtui-runtime

This package contains the browser runtime shell plus small host helpers for embedding it.

## What it is

- the current HTML/CSS/JS workbench shell
- runtime three-theme switching (`A / B / C`)
- keyboard-driven TUI layout and panel chrome
- generic action groups, task cards, and confirmation flow
- governed action protocol handling for missing fields, confirmation, and password challenge responses
- generic datagrid / detail / message / dashboard renderers
- built-in rich metadata renderers for `chart`, `kpi_trend`, `table_chart`, and safe `host_slot` views
- renderer extension registration via `window.AgomTUIRenderers.register(name, rendererFn)` for host-owned renderers such as ECharts, CodeMirror, Mermaid, or Markdown
- row-fill, inspector, pager, filter, modal, and raw-debug drawer behaviors
- host-configurable API base via `window.__AGOMTUI_RUNTIME__.apiBase`
- optional host slot HTML insertion via `window.__AGOMTUI_RUNTIME__.allowHostHtmlSlots`; disabled by default

## Embedding helper

`agomtui_runtime` exposes two minimal helpers:

- `render_runtime_html(...)`: renders the reference workbench HTML with host-owned `api_base`, `asset_base`, title, brand label, and home link.
- `runtime_asset(relative)`: safely serves CSS / JS assets under the extracted `reference/static/` directory.

The helpers are intentionally small. The host still owns auth, routing, metadata repository, action execution, and audit storage.

See `examples/hosts/stdlib_host.py` for a non-Django host that uses only Python's standard library plus the AgomTUI core/runtime packages.

## What is still host-specific

- assumes the host returns the AgomTUI screen/action response contract
- may still carry demo-oriented copy and screen semantics in the reference assets
- may still reflect host payload conventions that should be normalized into public contracts over time

Treat this as the product baseline, not the final host-agnostic runtime.

## Governance protocol handling

The browser shell treats these response shapes as runtime protocol, not ordinary errors:

- `missing_fields`: renders a refill modal and replays the same action with completed params
- `confirmation_required`: renders the confirmation modal and replays with confirmation evidence
- `password_challenge_required`: renders a re-auth modal and replays with password challenge evidence

The server-side host adapter must still route the replayed request through `GovernedActionRunner`; browser state is convenience, not enforcement.

## What is intentionally not extracted here

This package does **not** carry over:

- product-specific business screen definitions
- published business metadata graphs
- Django route wiring, auth, session, or ORM registry logic
- classic page replacement strategy for a specific host app
- product-specific workflow ordering or business vocabulary rules

The target is the **runtime framework**, not a full business application surface.

## Upstream sync

The reference shell in this package may be refreshed through the repository's internal one-way sync workflow.

Only the reference HTML/CSS/JS assets under `packages/agomtui-runtime/reference/` should move through that sync path.
