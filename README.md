# AgomTUI

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

[中文说明](./README.zh-CN.md)

**把后端 API 和业务逻辑直接变成可用的前端操作台 TUI。**

AgomTUI is for system developers who already have backend APIs but still need an internal operations UI. It turns API and business evidence into metadata, then turns that metadata into a working frontend console.

The goal is simple: generate useful internal-tool UI with near-zero frontend coding and much less integration pain.

## Quick prompt

Give this repository URL to Codex / Claude Code so it can understand the project boundaries and contract before wiring your backend:

```text
Read https://github.com/guiyinan/AgomTUI and understand the AgomTUI metadata, runtime, compiler, and host adapter boundaries.
Using my backend repository/API, generate or integrate a working internal operations TUI that follows the AgomTUI contract, including the necessary tests and docs.
```

## Documentation

- [Development docs](docs/README.md)
- [Architecture notes](docs/architecture/README.md)
- [Development standards](docs/development/development-standards.md)
- [Testing](docs/development/testing.md)
- [CI guardrails](docs/development/ci-guardrails.md)

## What it does

AgomTUI gives you a full path from backend capability to usable UI:

1. Your existing API and business logic describe what the system can do.
2. AgomTUI generates runtime metadata from that evidence.
3. The browser runtime renders the UI from metadata.
4. Operators get screens for lists, details, filters, actions, confirmations, and debugging without a custom frontend page for every workflow.

The big value is not a single component library. It is a repeatable way to turn system capabilities into operator-facing tools.

## What this means for developers

- You keep your existing APIs and backend logic.
- You do not rebuild tables, forms, detail views, action panels, and confirmation flows for every internal tool.
- You can get a usable UI first, then refine metadata or host integration where the business really needs polish.
- You can run it standalone or mount the same runtime inside an existing system.

## How general is it?

AgomTUI is broadly reusable for API-driven internal tools, not for every possible frontend.

It works best when the product can be described as:

- data lists, detail pages, filters, and search
- operator actions with parameters and results
- confirmation, permission, audit, and re-authentication rules
- backend-owned business logic exposed through APIs or action executors

That makes it a good fit for operations consoles, admin tools, risk-control workbenches, review systems, governance panels, and internal data management surfaces.

It is less suitable as the primary UI system for consumer-facing product pages, marketing sites, visual editors, games, or highly bespoke interactive experiences. Those can still call the same APIs, but they usually need hand-designed frontend work instead of metadata-generated screens.

## Can the UI be extended?

Yes. AgomTUI should be treated as a generated baseline plus an extension system.

The expected customization layers are:

- metadata changes for screen names, grouping, ordering, field labels, and action placement
- host adapters for auth, permissions, action execution, audit storage, and deployment shape
- renderer extensions for new view types that are still metadata-driven
- theme and shell customization for product identity and host embedding
- manual override files for reviewed edits that must survive regeneration

The main rule is to keep business logic in the host system and keep the UI driven by metadata where possible. If a change is useful across many tools, it belongs in the runtime or metadata contract. If it is only for one host, it belongs in that host adapter or metadata override.

## Rich components and charts

Yes, AgomTUI should support richer components such as ECharts, Chart.js, HTMX partials, Mermaid, Markdown renderers, date pickers, and code editors. They should be added through extension points rather than hard-coded into every generated screen.

The classic AgomTradePro frontend already uses this pattern:

- ECharts for macro timelines, filter dashboards, equity detail charts, portfolio allocation/performance, and public share performance curves
- Chart.js for selected audit and valuation charts
- HTMX for server-rendered partial refreshes and interactive panels
- Flatpickr, SweetAlert2, and Alpine.js as lightweight page enhancers
- Mermaid, Marked, and CodeMirror for diagrams, Markdown rendering, and script editing

AgomTUI should carry that forward with three layers:

- native metadata renderers for common charts such as line, bar, pie, KPI trend, and table-plus-chart views
- custom renderer extensions for host-specific components, for example `renderer: "echarts"` or `renderer: "code-editor"`
- host slots for controlled server-rendered fragments, including HTMX partials when the host application is already using HTMX

HTMX is useful for host-mounted or server-rendered integrations, especially Django-style pages. For the standalone metadata runtime, the default path should still be API data plus runtime renderers. That keeps the core portable while allowing a host project to insert richer UI where metadata alone is not enough.

## Development guardrails

AgomTUI needs CI and development rules because its value depends on stable metadata, runtime contracts, governed actions, and adapter boundaries. The current standards live in [docs/development/development-standards.md](docs/development/development-standards.md), and the first CI gate is documented in [docs/development/ci-guardrails.md](docs/development/ci-guardrails.md).

## The problem it solves

Most internal tools stall in the same place:

- the data API exists, but the usable operator UI does not
- every new tool reimplements tables, detail views, filters, pagination, and action forms
- system developers have to spend frontend time describing screens that already exist implicitly in their APIs
- risky actions need confirmation and traceability, but those rules are rebuilt screen by screen
- some teams want to launch it first as a standalone console, while others want to plug the same workbench into an existing Django or internal system

AgomTUI is for that gap. Instead of hand-coding each table, detail panel, filter, form, and confirmation dialog, you let generated metadata describe the UI and only customize where the host system really needs it.

## Good fit

AgomTUI is a strong fit if you want to build:

- an internal operations console
- a risk-control or governance-heavy back-office tool
- a host-mounted TUI surface inside Django or another web app
- a reusable shell for teams that already have APIs but not a consistent operator experience

## Why it feels useful fast

With the demo alone, a user can immediately see:

- what the standalone workbench experience looks like
- how the same runtime can mount back into a host project
- how metadata, not ad hoc page code, drives navigation and action surfaces

## Demo

### Overview workspace

![AgomTUI overview workspace](docs/assets/demo-overview.png)

### Standalone runtime workbench

![AgomTUI standalone runtime](docs/assets/demo-standalone.png)

### Host-mounted runtime

![AgomTUI host-mounted runtime](docs/assets/demo-host-mounted.png)

## What you get

- a terminal-style runtime shell that already has navigation, inspector, filters, paging, action forms, modal confirmation, and raw-response debugging
- a metadata contract that lets generated metadata define screens and actions without rewriting the shell
- a compiler path for turning APIs and code-owned evidence into published runtime metadata
- a host-adapter model, so the same runtime can run standalone or under another application shell

## How it works at a high level

The technical path is intentionally small:

1. collect API or code evidence from the host system
2. compile it into AgomTUI runtime metadata
3. serve that metadata to the runtime shell
4. connect action execution, auth, and audit to the host system

The frontend is generated from metadata; the host keeps control of business logic and execution.

## Does it require Django or Python?

No. The frontend runtime framework is the browser shell plus the AgomTUI metadata/action contract. It does not have to be based on Django, and the runtime UI does not require a Python backend.

What is Python/Django in this repo:

- Python is the current implementation language for the schema helpers, compiler skeleton, tests, and demo servers.
- Django is the first host-adapter example because it is the first integration target.
- A non-Django host can use the same runtime as long as it can serve metadata, execute actions, and return the AgomTUI response contracts.

In other words: Django/Python are provided integration paths, not a frontend framework requirement. Future adapters can target FastAPI, Flask, Node services, Java services, or an OpenAPI-only backend.

## What is in this repo

- `packages/agomtui-core/`: schema, validator, runtime contracts, and generic server-side runtime helpers
- `packages/agomtui-runtime/`: extracted browser shell assets, renderer reference, and embeddable asset helpers
- `packages/agomtui-compiler/`: compile-time collector / AI synthesizer / validator / publisher skeleton
- `demo/`: runnable standalone demo, compiler walkthrough, integration demo, and migration pages
- `adapters/django/`: notes for the first host adapter
- `examples/metadata/`: minimal, rich-component, and generic-operations metadata fixtures
- `examples/hosts/`: host integration examples, including a non-Django standard-library host
- `docs/`: development docs, architecture notes, migration plan, and CI guardrails

## For builders

If you are evaluating whether this saves real work, the practical answer is:

- you keep your APIs
- you generate metadata from API/code evidence instead of hand-describing every screen
- you get useful UI with little or no frontend coding for standard internal-tool workflows
- you stop rebuilding the same operator UI primitives for every tool
- you get one shell that can serve many internal workflows
- you can start standalone and later mount into a host app without throwing the runtime away

## Reusable now

- metadata schema (`tui-metadata.v3`)
- metadata validation and compaction
- reviewed metadata override files for manual terminal edits that must survive regeneration
- generic server-side runtime helpers:
  - view-model inference
  - confirmation contract
  - missing-fields contract
  - password-challenge detection
  - no-bypass governed action runner
  - canonical audit record generation
  - runtime metadata normalization hooks
- runtime shell layout, keyboard model, theme tokens
- generic renderers: dashboard, datagrid, detail, and message views
- generic action framework: task grouping, confirmation, row-fill, filter, pager, inspector, modal, raw drawer
- compiler boundaries for evidence-driven metadata synthesis
- generic repository / action-executor contracts

## Still host-specific

- business screen definitions and workflow ordering
- published business metadata graphs
- auth and login flow
- DB publish registry and audit storage
- internal API execution adapter
- host vocabulary and view-model translation
- compile-time harvesting heuristics

## Quick start

### 1. Run the demo stack

From the repository root:

```powershell
python demo\run_demo_stack.py
```

Open:

- `http://localhost:8020/` for the product overview
- `http://localhost:8020/standalone/` for the standalone runtime
- `http://localhost:8020/compiler/` for the compiler walkthrough
- `http://localhost:8020/integration/` for the host integration contract demo
- `http://localhost:8020/migration/` for the migration checklist
- `http://localhost:8030/` for the Django host page
- `http://localhost:8030/tui/` for the Django-mounted runtime

If you only want the standalone surface:

```powershell
python demo\standalone_server.py
```

If you want the Django host separately:

```powershell
python demo\django_host\manage.py runserver 127.0.0.1:8030 --noreload
```

If you want a non-Django host example:

```powershell
python examples\hosts\stdlib_host.py
```

Then open `http://127.0.0.1:8040/`.

### 2. Run tests

The local test and metadata validation commands are maintained in [docs/development/testing.md](docs/development/testing.md). The same checks run in GitHub Actions as the first CI guardrail.

## Product boundary

AgomTUI is not a Django template split. The durable product boundary is:

1. schema-first metadata core
2. compile-time metadata generator / promotion pipeline
3. runtime TUI shell and host adapters

Suggested package line:

- `agomtui-core`: schema, validator, runtime contracts
- `agomtui-runtime`: browser shell and renderer
- `agomtui-compiler`: evidence collectors and publish pipeline
- `agomtui-adapters-*`: host integrations such as Django / FastAPI / OpenAPI-only

## AI skill path

The intended generation path is:

1. collectors read code-owned evidence
2. `agomtui-compiler skill-request` emits a schema-constrained prompt payload
3. an external AI skill returns one `candidate_payload`
4. `agomtui-compiler compile-skill-result` validates, compacts, and publishes the approved artifact

The extracted skill should target host-agnostic runtime metadata first. It should not assume one product's page splits, workflow ordering, or business prose unless those structures are explicitly present in the evidence bundle.

## Published metadata edits

Published metadata is an artifact, not the source of truth. Re-running the compiler against the same publish path overwrites that file. If an operator or developer needs a terminal manual edit to survive regeneration, put it in a reviewed override file and pass it during compile:

```powershell
agomtui-compile compile-static --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --candidate-file examples\metadata\minimal.tui_operation_graph.json --override-file examples\metadata\minimal.override.json --output tmp\published.override.json --evidence-output tmp\evidence.override.json
```

For dry-run validation without publishing:

```powershell
agomtui-compile validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
agomtui-compile compact-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json --output tmp\published.compact.json
```

Action governance fields are schema-validated: `risk`, `confirmation_required`, `requires_password`, `audit_required`, `sensitive_level`, and `executor`. Write actions and non-GET admin actions cannot disable required confirmation or audit.

## Governance-first runtime

AgomTUI treats confirmation, missing-field recovery, re-authentication, and audit as a runtime protocol, not per-screen UI decoration. A governed action should go through one enforced path:

1. missing required fields are returned as a `missing_fields` contract and the shell renders a refill prompt
2. confirmation-required actions are stopped before execution and replayed only with confirmation evidence
3. password-challenge actions are stopped until the host verifies re-authentication
4. audit-required actions cannot reach the executor unless an audit sink is present
5. success, failure, blocked, and rejected attempts all emit `tui-audit.v1` records

The core audit schema covers actor, action key, masked params, timestamp, confirmation evidence, re-auth evidence, and execution result. Hosts own storage, but should store audit records append-only or tamper-evidently.

## Start here

- read `docs/README.md` for the documentation map
- read `docs/architecture/product-split.md` for the extraction boundary
- read `docs/architecture/compiler-architecture.md` for the compile-time architecture
- open `packages/agomtui-runtime/reference/tui_workbench.reference.html` for the current shell reference
